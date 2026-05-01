"""In-app deploy-time bootstrap — replaces the postprovision azd hook.

Runs synchronously inside the FastAPI ``lifespan`` startup phase. The container
does not accept requests until this completes, so:

- A healthy ``/healthz`` from the container app proves bootstrap finished.
- ACA's ``startupProbe`` (configured in infra/modules/container-app.bicep) is
  the deployment readiness gate; if bootstrap exhausts its retry budget the
  exception propagates → uvicorn exits → ACA marks the revision unhealthy →
  ``azd up`` exits non-zero. This is the loud failure semantic the previous
  postprovision hook had, just centralized inside the workload image.

What it does (idempotent — safe to re-run on container restart):

1. **Foundry agents** — for every ``scenario.agents[]`` entry in
   ``accelerator.yaml``, read ``docs/agent-specs/<foundry_name>.md``, parse
   the ``## Instructions`` body, and create-or-update the Foundry agent
   bound to the slug-resolved model deployment.

2. **AI Search indexes** — for every ``scenario.retrieval.indexes[]`` entry,
   call the resolved schema callable to get a ``SearchIndex`` and
   create-or-update it. If a ``seed`` JSON file exists, upload the documents.

Inputs (env, set by Bicep outputs / Container App env block):
- ``AZURE_AI_FOUNDRY_ENDPOINT``         required
- ``AZURE_AI_FOUNDRY_MODEL``            required (default deployment name)
- ``AZURE_AI_FOUNDRY_MODEL_MAP``        optional JSON object (slug -> deployment)
- ``AZURE_AI_SEARCH_ENDPOINT``          required
- ``BOOTSTRAP_SKIP=1``                  optional; bypass entirely (local dev / tests)
- ``BOOTSTRAP_RETRY_BUDGET_SECONDS``    optional; default 600 (10 minutes)

Auth: ``DefaultAzureCredential`` only. The Bicep modules grant the workload MI:
- ``Azure AI Developer`` on the Foundry project (agent CRUD)
- ``Cognitive Services OpenAI User`` on the account (model invoke)
- ``Search Service Contributor`` + ``Search Index Data Contributor`` on Search
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import re
import time
import uuid
from typing import Any, Awaitable, Callable

from .workflow.registry import ROOT, ScenarioAgent, ScenarioBundle, ScenarioIndex

logger = logging.getLogger("accelerator.bootstrap")

# Search RBAC roles granted to each Foundry agent's instance MI so its
# retrieval calls can resolve the AI Search index at query time.
# Must match the ABAC condition allow-list in infra/main.bicep
# (workloadAssignsSearchRoles role assignment).
_AGENT_SEARCH_ROLES: dict[str, str] = {
    "Search Index Data Reader": "1407120a-92aa-4202-b7e9-c0e197c71c8f",
    "Search Index Data Contributor": "8ebe5a00-799e-43f5-93ac-243d3dce84a7",
    "Search Service Contributor": "7ca78c08-252a-4471-8644-bb5ff32d4ba0",
}

SPECS_DIR = ROOT / "docs" / "agent-specs"

_INSTRUCTIONS_RE = re.compile(
    r"^##\s+Instructions\s*\n(.*?)(?=^##\s|\Z)", re.DOTALL | re.MULTILINE
)
_MODEL_RE = re.compile(r"^\s*\*\*Model:\*\*", re.MULTILINE)


def _retry_budget_seconds() -> float:
    raw = os.environ.get("BOOTSTRAP_RETRY_BUDGET_SECONDS", "600")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 600.0


def _parse_model_map() -> dict[str, str]:
    """Resolve slug -> deployment_name from env (Bicep output AZURE_AI_FOUNDRY_MODEL_MAP).

    Falls back to ``{"default": AZURE_AI_FOUNDRY_MODEL}`` when the map env is
    absent (i.e. a manifest with no ``models:`` block — only the default
    deployment exists).
    """
    default_dep = os.environ.get("AZURE_AI_FOUNDRY_MODEL", "")
    raw = os.environ.get("AZURE_AI_FOUNDRY_MODEL_MAP", "").strip()
    if not raw:
        return {"default": default_dep} if default_dep else {}
    try:
        mapping = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"AZURE_AI_FOUNDRY_MODEL_MAP is not valid JSON: {exc}. It should "
            "be the Bicep output AZURE_AI_FOUNDRY_MODEL_MAP."
        ) from exc
    if not isinstance(mapping, dict):
        raise RuntimeError(
            "AZURE_AI_FOUNDRY_MODEL_MAP must be a JSON object (slug -> "
            "deployment_name)"
        )
    return {str(k): str(v) for k, v in mapping.items()}


def _parse_spec(path: pathlib.Path) -> str:
    """Return the ``## Instructions`` body of the spec file.

    The Foundry agent's model is set from the resolved model map (Bicep
    output) — the spec must NOT carry a ``**Model:**`` field.
    """
    txt = path.read_text(encoding="utf-8")
    if _MODEL_RE.search(txt):
        raise RuntimeError(
            f"{path.name}: spec contains a '**Model:**' field, which is no "
            "longer allowed. The deployed model is authoritative."
        )
    m = _INSTRUCTIONS_RE.search(txt)
    if not m:
        raise RuntimeError(f"{path.name}: missing '## Instructions' section")
    return m.group(1).strip()


async def _retry(
    fn: Callable[[], Awaitable[Any]],
    *,
    name: str,
    budget_seconds: float,
    base: float = 2.0,
) -> Any:
    """Exponential-backoff retry around an awaitable factory.

    Retries on every exception except hard configuration errors (which are
    re-raised unwrapped). The intent is to absorb RBAC role-assignment
    propagation lag — Bicep finishes the role assignment but the Foundry /
    Search data planes can take several minutes to reflect it. After the
    budget is exhausted, the last exception propagates so the FastAPI
    lifespan fails and ACA marks the revision unhealthy.
    """
    deadline = time.monotonic() + budget_seconds
    attempt = 0
    while True:
        attempt += 1
        try:
            return await fn()
        except (RuntimeError, ValueError, FileNotFoundError):
            # Configuration / contract errors — never retry.
            raise
        except Exception as exc:  # noqa: BLE001  # broad on purpose: retry transient infra errors
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.error(
                    "bootstrap.%s: retry budget exhausted after %d attempts (%s)",
                    name, attempt, exc,
                )
                raise
            sleep = min(remaining, base ** min(attempt, 6))
            logger.warning(
                "bootstrap.%s: attempt %d failed (%s); retrying in %.1fs (%.1fs left)",
                name, attempt, exc, sleep, remaining,
            )
            await asyncio.sleep(sleep)


# ---------------------------------------------------------------------------
# FoundryIQ Knowledge Base bootstrap (preview REST API)
#
# Creates a Knowledge Source + Knowledge Base on AI Search, then wires each
# retrieval-mode agent with an MCPTool pointing at the Bicep-provisioned
# RemoteTool MCP connection.  Uses direct REST calls against the AI Search
# ``2025-11-01-preview`` API so we stay inside the GA-only SDK constraint
# (azure-search-documents <11.6.0) while using preview retrieval features.
# ---------------------------------------------------------------------------

_KB_API_VERSION = "2025-11-01-preview"


async def _rest_put(
    url: str, body: dict, token: str, *, label: str,
) -> dict:
    """Idempotent PUT against an Azure REST endpoint. Returns JSON body."""
    import aiohttp

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.put(url, json=body, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(
                    f"{label}: PUT {url} returned {resp.status}: {text}"
                )
            return json.loads(text) if text else {}


async def _bootstrap_knowledge(bundle: ScenarioBundle) -> None:
    """Create a Knowledge Source + Knowledge Base on AI Search.

    Uses the ``2025-11-01-preview`` REST API directly (no preview SDK).
    Idempotent — both PUT endpoints are create-or-update.

    The Knowledge Base name is deterministic from ``AZURE_AI_FOUNDRY_KB_NAME``
    (set by Bicep) and must match the MCP connection target URL that Bicep
    provisioned.
    """
    foundry_tool_agents = [
        a for a in bundle.agents
        if a.retrieval is not None and a.retrieval.mode == "foundry_tool"
    ]
    if not foundry_tool_agents:
        logger.info("bootstrap.knowledge: no retrieval agents; skipping")
        return

    search_endpoint = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "").rstrip("/")
    kb_name = os.environ.get("AZURE_AI_FOUNDRY_KB_NAME", "")
    aoai_endpoint = os.environ.get("AZURE_AI_FOUNDRY_OPENAI_ENDPOINT", "")
    model_deployment = os.environ.get("AZURE_AI_FOUNDRY_MODEL", "")

    if not search_endpoint:
        raise RuntimeError("AZURE_AI_SEARCH_ENDPOINT is not set")
    if not kb_name:
        raise RuntimeError(
            "AZURE_AI_FOUNDRY_KB_NAME is not set — Bicep should export "
            "the deterministic knowledge base name."
        )

    from azure.identity.aio import DefaultAzureCredential

    cred = DefaultAzureCredential()
    try:
        # Collect unique index names from retrieval agents, plus the
        # index entry that declares them (so we know each index's
        # `sourceDataFields`). Order-stable for deterministic logs.
        seen_indexes: list[str] = []
        idx_to_entry: dict[str, ScenarioIndex] = {
            i.name: i for i in bundle.retrieval_indexes
        }
        for agent in foundry_tool_agents:
            assert agent.retrieval is not None
            idx_name = agent.retrieval.index
            if idx_name and idx_name not in seen_indexes:
                seen_indexes.append(idx_name)

        # ---- 1. Create Knowledge Source(s) per search index ----
        ks_names: list[str] = []
        for idx_name in seen_indexes:
            ks_name = f"{idx_name}-ks"
            ks_url = (
                f"{search_endpoint}/knowledgesources/{ks_name}"
                f"?api-version={_KB_API_VERSION}"
            )
            # Resolve sourceDataFields from the manifest entry. Defaults to
            # ("source",) -- every scaffolded scenario has that field.
            entry = idx_to_entry.get(idx_name)
            sdf = entry.source_data_fields if entry else ("source",)
            ks_body: dict[str, Any] = {
                "name": ks_name,
                "kind": "searchIndex",
                "description": (
                    f"Knowledge source wrapping AI Search index '{idx_name}'."
                ),
                "searchIndexParameters": {
                    "searchIndexName": idx_name,
                    "sourceDataFields": [{"name": n} for n in sdf],
                },
            }

            async def _create_ks(
                _url=ks_url, _body=ks_body, _ks=ks_name,
            ) -> dict:
                t = (await cred.get_token(
                    "https://search.azure.com/.default"
                )).token
                return await _rest_put(_url, _body, t, label=f"ks.{_ks}")

            await _retry(
                _create_ks,
                name=f"knowledge_source.{ks_name}",
                budget_seconds=_retry_budget_seconds(),
            )
            ks_names.append(ks_name)
            logger.info("bootstrap.knowledge: knowledge source OK: %s", ks_name)

        # ---- 2. Create Knowledge Base referencing all sources ----
        kb_url = (
            f"{search_endpoint}/knowledgebases/{kb_name}"
            f"?api-version={_KB_API_VERSION}"
        )
        kb_body: dict[str, Any] = {
            "name": kb_name,
            "description": (
                "FoundryIQ knowledge base for the accelerator. "
                "Orchestrates agentic retrieval over AI Search indexes."
            ),
            "knowledgeSources": [{"name": ks} for ks in ks_names],
            "retrievalReasoningEffort": {"kind": "low"},
        }
        # Wire the LLM model if AOAI endpoint + deployment are available.
        if aoai_endpoint and model_deployment:
            kb_body["models"] = [{
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": aoai_endpoint.rstrip("/"),
                    "deploymentId": model_deployment,
                    "modelName": model_deployment,
                },
            }]

        async def _create_kb() -> dict:
            t = (await cred.get_token(
                "https://search.azure.com/.default"
            )).token
            return await _rest_put(kb_url, kb_body, t, label=f"kb.{kb_name}")

        await _retry(
            _create_kb,
            name=f"knowledge_base.{kb_name}",
            budget_seconds=_retry_budget_seconds(),
        )
        logger.info(
            "bootstrap.knowledge: knowledge base OK: %s (%d source(s))",
            kb_name, len(ks_names),
        )
    finally:
        await cred.close()


def _build_mcp_tool(agent: ScenarioAgent) -> Any | None:
    """Construct an ``MCPTool`` for a retrieval-mode agent, or ``None``.

    Uses the FoundryIQ knowledge base MCP connection provisioned by Bicep.
    The ``project_connection_id`` is the connection **name** (not ARM ID).
    """
    if agent.retrieval is None or agent.retrieval.mode != "foundry_tool":
        return None

    mcp_conn_name = os.environ.get("AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME")
    search_endpoint = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "").rstrip("/")
    kb_name = os.environ.get("AZURE_AI_FOUNDRY_KB_NAME", "")

    if not mcp_conn_name:
        raise RuntimeError(
            "AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME is not set — Bicep "
            "should export the RemoteTool MCP connection name."
        )
    if not search_endpoint or not kb_name:
        raise RuntimeError(
            "AZURE_AI_SEARCH_ENDPOINT and AZURE_AI_FOUNDRY_KB_NAME must "
            "be set for MCPTool construction."
        )

    from azure.ai.projects.models import MCPTool

    mcp_url = (
        f"{search_endpoint}/knowledgebases/{kb_name}"
        f"/mcp?api-version={_KB_API_VERSION}"
    )
    return MCPTool(
        server_label="knowledge-base",
        server_url=mcp_url,
        require_approval="never",
        allowed_tools=["knowledge_base_retrieve"],
        project_connection_id=mcp_conn_name,
    )


def _tool_fingerprint(tool: Any | None) -> tuple:
    """Order-stable fingerprint of an agent tool for idempotency diff."""
    if tool is None:
        return ()
    tool_type = getattr(tool, "type", None)
    if tool_type == "mcp":
        return (
            "mcp",
            getattr(tool, "server_label", "") or "",
            getattr(tool, "project_connection_id", "") or "",
        )
    # Legacy AzureAISearchTool fallback — handles readback of agents that
    # were created before the MCPTool migration (prior versions on server).
    res = getattr(tool, "azure_ai_search", None)
    if res is not None:
        indexes = getattr(res, "indexes", None) or []
        parts: list[tuple] = []
        for ix in indexes:
            parts.append((
                getattr(ix, "project_connection_id", None)
                or getattr(ix, "index_asset_id", None) or "",
                getattr(ix, "index_name", None) or "",
                str(getattr(ix, "query_type", "") or ""),
                int(getattr(ix, "top_k", 0) or 0),
            ))
        return ("azure_ai_search", tuple(parts))
    return ("unknown",)


def _existing_tools_fingerprint(definition: Any) -> tuple:
    """Fingerprint the ``tools`` field on a returned PromptAgentDefinition.

    Kept for backward compatibility with the single-tool readback path. New
    code should prefer :func:`_kb_tool_present` to support agents that carry
    partner-attached catalog tools alongside the bootstrap-managed KB tool.
    """
    if definition is None:
        return ()
    tools = getattr(definition, "tools", None) or []
    if not tools:
        return ()
    if len(tools) != 1:
        return ("__unknown_count__", len(tools))
    return _tool_fingerprint(tools[0])


def _agent_definition_unchanged(
    cur_model: Any,
    cur_instr: Any,
    desired_model: str,
    desired_instr: str,
) -> bool:
    """Decide whether ``create_version`` can be skipped.

    Bootstrap owns model + instructions; tools are preserved/merged
    separately (see :func:`_merge_preserved_tools`). Comparing tool
    fingerprints here would force a fresh version every time a partner
    attaches a catalog tool in the Foundry portal, even though the
    accelerator has nothing new to write — that would silently nuke
    portal-attached tools on every ``azd deploy``.
    """
    return cur_model == desired_model and cur_instr == desired_instr


def _merge_preserved_tools(
    existing_tools: list[Any] | None,
    desired_managed: Any | None,
) -> list[Any] | None:
    """Build the final ``tools`` list, preserving partner-attached tools.

    Bootstrap "owns" exactly one tool — the FoundryIQ Knowledge Base MCP
    tool whose fingerprint matches ``_tool_fingerprint(desired_managed)``.
    Any other tool on the existing definition was attached out-of-band
    (Foundry portal catalog, partner script) and must survive
    ``azd deploy``.

    Behaviour:
    - ``desired_managed is None``: bootstrap doesn't manage a tool for this
      agent (``retrieval.mode: none``). Existing tools pass through
      unchanged.
    - Otherwise: drop any existing tool whose fingerprint matches the
      managed one (so we refresh it rather than duplicate), then append the
      managed tool last.

    Returns ``None`` when the resulting list would be empty so the caller
    can omit the ``tools`` kwarg entirely.
    """
    existing = list(existing_tools or [])
    if desired_managed is None:
        return existing or None
    desired_fp = _tool_fingerprint(desired_managed)
    preserved = [t for t in existing if _tool_fingerprint(t) != desired_fp]
    merged = preserved + [desired_managed]
    return merged or None


def _kb_tool_present(definition: Any, desired_fp: tuple) -> bool:
    """Return True if a tool matching ``desired_fp`` is on the definition.

    Used by the readback canary after ``create_version`` to confirm the
    bootstrap-managed KB tool round-tripped, without forcing equality on
    the full tools list (which may include partner-attached catalog
    tools).
    """
    if definition is None or not desired_fp:
        return False
    tools = getattr(definition, "tools", None) or []
    return any(_tool_fingerprint(t) == desired_fp for t in tools)


async def _grant_agent_search_access(
    principal_id: str, agent_name: str, cred: Any,
) -> None:
    """Idempotently grant Search RBAC to a Foundry agent's instance MI.

    Each Foundry agent (PromptAgent) is created with its own
    ``instance_identity.principal_id`` — a fresh service principal not known
    at Bicep time. Without explicit RBAC, the agent's Knowledge Base
    retrieval fails at query time with ``tool_user_error: Access denied``.

    Bootstrap closes the loop: after ``create_version`` returns, we read the
    instance principalId off the version envelope and assign the three
    Search roles below on the search service. The role-assignment GUIDs are
    derived deterministically (uuid5 over scope|principal|role) so re-runs
    are idempotent — 409 RoleAssignmentExists is treated as success.

    Authorization for THIS write comes from a workload-MI role assignment
    in ``infra/main.bicep`` (``workloadAssignsSearchRoles``): Role Based
    Access Control Administrator at the search-service scope, ABAC-conditioned
    so only the three Search role IDs can be granted. Minimum-privilege.

    Skips silently when ``AZURE_AI_SEARCH_RESOURCE_ID`` is unset (local dev,
    tests, or non-Bicep installs).
    """
    if not principal_id:
        logger.warning(
            "bootstrap.foundry: %s has no instance_identity.principal_id; "
            "skipping per-agent Search RBAC", agent_name,
        )
        return
    search_resource_id = os.environ.get("AZURE_AI_SEARCH_RESOURCE_ID", "")
    if not search_resource_id:
        logger.info(
            "bootstrap.foundry: AZURE_AI_SEARCH_RESOURCE_ID not set; "
            "skipping per-agent Search RBAC for %s", agent_name,
        )
        return

    from azure.core.exceptions import HttpResponseError, ResourceExistsError
    from azure.mgmt.authorization.aio import (  # pyright: ignore[reportMissingImports]  # azure-mgmt-authorization ships no type stubs
        AuthorizationManagementClient,
    )

    parts = [p for p in search_resource_id.split("/") if p]
    try:
        sub_id = parts[parts.index("subscriptions") + 1]
    except (ValueError, IndexError):
        logger.warning(
            "bootstrap.foundry: AZURE_AI_SEARCH_RESOURCE_ID=%r is malformed; "
            "skipping per-agent Search RBAC for %s",
            search_resource_id, agent_name,
        )
        return

    auth = AuthorizationManagementClient(
        credential=cred, subscription_id=sub_id,
    )
    try:
        for role_name, role_id in _AGENT_SEARCH_ROLES.items():
            ra_name = str(uuid.uuid5(
                uuid.NAMESPACE_OID,
                f"{search_resource_id}|{principal_id}|{role_id}",
            ))
            params: dict[str, Any] = {
                "properties": {
                    "roleDefinitionId": (
                        f"/subscriptions/{sub_id}/providers/"
                        f"Microsoft.Authorization/roleDefinitions/{role_id}"
                    ),
                    "principalId": principal_id,
                    "principalType": "ServicePrincipal",
                    "description": (
                        f"Bootstrap-managed: Foundry agent {agent_name} "
                        f"-> {role_name} on AI Search."
                    ),
                },
            }
            try:
                await auth.role_assignments.create(
                    scope=search_resource_id,
                    role_assignment_name=ra_name,
                    parameters=params,  # type: ignore[arg-type]
                )
                logger.info(
                    "bootstrap.foundry: granted '%s' to %s "
                    "(agent=%s, principal=%s)",
                    role_name, search_resource_id.rsplit("/", 1)[-1],
                    agent_name, principal_id,
                )
            except ResourceExistsError:
                # Already granted — idempotent success.
                continue
            except HttpResponseError as exc:
                if getattr(exc, "status_code", None) == 409:
                    continue
                # 403 here means the workload MI is missing the
                # workloadAssignsSearchRoles assignment from main.bicep —
                # log loudly and continue (other roles may still apply).
                logger.error(
                    "bootstrap.foundry: failed to grant '%s' to %s "
                    "(agent=%s): %s",
                    role_name, principal_id, agent_name, exc,
                )
    finally:
        await auth.close()


async def _bootstrap_foundry(bundle: ScenarioBundle) -> None:
    endpoint = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_AI_FOUNDRY_ENDPOINT is not set")

    model_map = _parse_model_map()
    if "default" not in model_map or not model_map["default"]:
        raise RuntimeError(
            "no default Foundry model deployment resolved. Set "
            "AZURE_AI_FOUNDRY_MODEL (Bicep output) or include a `models:` "
            "block with `default: true` in accelerator.yaml."
        )

    # Pre-resolve specs and tools so we fail fast on missing files / asset
    # mismatches BEFORE touching the control plane.
    work: list[tuple[ScenarioAgent, str, str, Any | None]] = []
    for agent in bundle.agents:
        spec_path = SPECS_DIR / f"{agent.foundry_name}.md"
        if not spec_path.exists():
            raise RuntimeError(
                f"{agent.foundry_name}: missing spec file {spec_path}"
            )
        instructions = _parse_spec(spec_path)
        deployment = model_map.get("default", "")
        tool = _build_mcp_tool(agent)
        work.append((agent, deployment, instructions, tool))

    # SDK contract (GA-only — enforced by scripts/accelerator-lint.py
    # `sdks_pinned_to_ga` against ga-versions.yaml):
    #
    #   azure-ai-projects >=2.0.0,<3.0.0 -> AIProjectClient.agents
    #     The *new* Foundry "Agents (versions)" surface. Each instructions
    #     edit is a new version; "latest" is the active one. Methods used:
    #       agents.list()                 — enumerate agents in the project
    #       agents.get_version(name, ver) — fetch latest definition
    #       agents.create_version(name, definition=PromptAgentDefinition(
    #           model=..., instructions=...))
    #     The first create_version() implicitly creates the agent envelope.
    #
    #   azure-ai-agents >=1.0.0,<2.0.0  -> AgentsClient
    #     The *legacy* Foundry Assistants surface. Kept as a transitive dep
    #     of agent-framework, and used here only to delete any orphaned
    #     Assistants left over from earlier accelerator versions so the
    #     portal stops showing the "Update your agents" migration banner.
    #
    # If a future SDK bump moves these methods, update both this comment and
    # ga-versions.yaml in the same change so the lint stays honest.
    from azure.ai.projects.aio import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.core.exceptions import (
        HttpResponseError,
        ResourceNotFoundError,
    )
    from azure.identity.aio import DefaultAzureCredential

    desired_names = {agent.foundry_name for agent, _, _, _ in work}

    cred = DefaultAzureCredential()
    try:
        proj = AIProjectClient(endpoint=endpoint, credential=cred)
        try:
            existing_names: set[str] = set()

            async def _list() -> None:
                async for a in proj.agents.list():
                    if a.name:
                        existing_names.add(a.name)

            await _retry(
                _list,
                name="foundry.agents.list",
                budget_seconds=_retry_budget_seconds(),
            )

            for agent, deployment, instructions, tool in work:
                name = agent.foundry_name
                desired_tool_fp = _tool_fingerprint(tool)
                # Force tool use for retrieval-mode agents so gpt-5-mini
                # cannot skip the AI Search call. Server may reject the
                # string form on some preview surfaces — wrapper handles
                # the fallback below.
                desired_tool_choice = (
                    "required" if tool is not None else None
                )

                # Decide whether a fresh version is needed: skip the write
                # when the latest version's (model, instructions) tuple
                # already matches what we want. Tools are preserved /
                # merged separately so partner-attached portal catalog
                # tools survive across deploys.
                needs_new_version = True
                latest: Any = None
                cur_existing_tools: list[Any] = []
                if name in existing_names:
                    try:
                        latest = await proj.agents.get_version(name, "latest")
                        defn = getattr(latest, "definition", None)
                        cur_model = getattr(defn, "model", None)
                        cur_instr = getattr(defn, "instructions", None)
                        cur_existing_tools = list(
                            getattr(defn, "tools", None) or []
                        )
                        if _agent_definition_unchanged(
                            cur_model, cur_instr, deployment, instructions,
                        ):
                            needs_new_version = False
                    except ResourceNotFoundError:
                        # Envelope exists but no version yet — still need
                        # to create one.
                        needs_new_version = True
                    except HttpResponseError as exc:
                        # Some Foundry preview surfaces reject the "latest"
                        # alias with invalid_parameters / 404 instead of a
                        # ResourceNotFoundError. In that case fall back to
                        # creating a fresh version — the server treats
                        # create_version as upsert by name+monotonic version.
                        logger.info(
                            "bootstrap.foundry: %s get_version(latest) "
                            "failed (%s); will create new version",
                            name, getattr(exc, "status_code", "?"),
                        )
                        needs_new_version = True

                if not needs_new_version:
                    logger.info(
                        "bootstrap.foundry: %s up-to-date (model=%s, tool=%s)",
                        name, deployment,
                        "yes" if tool is not None else "no",
                    )
                    # Even when the agent definition is up-to-date we re-run
                    # the per-agent Search RBAC grant for retrieval-mode
                    # agents — the helper is idempotent (409 = success) and
                    # this self-heals if a partner manually deletes a role
                    # assignment, or if a previous bootstrap landed before
                    # the workload MI got the RBAC-admin grant.
                    if tool is not None:
                        try:
                            principal_id = getattr(
                                getattr(latest, "instance_identity", None),
                                "principal_id", None,
                            )
                            await _grant_agent_search_access(
                                principal_id or "", name, cred,
                            )
                        except Exception as exc:  # pragma: no cover
                            logger.warning(
                                "bootstrap.foundry: %s Search RBAC refresh "
                                "skipped: %s", name, exc,
                            )
                    continue

                # Merge: preserve any partner-attached tools (Foundry
                # portal catalog, partner scripts) and refresh the
                # bootstrap-managed KB tool. ``cur_existing_tools`` is
                # empty for new agents.
                desired_tools = _merge_preserved_tools(
                    cur_existing_tools, tool,
                )

                async def _create_version(
                    _name=name,
                    _dep=deployment,
                    _ins=instructions,
                    _tools=desired_tools,
                    _tc=desired_tool_choice,
                ) -> Any:
                    kwargs: dict[str, Any] = {
                        "model": _dep,
                        "instructions": _ins,
                    }
                    if _tools is not None:
                        kwargs["tools"] = _tools
                    if _tc is not None:
                        kwargs["tool_choice"] = _tc
                    try:
                        return await proj.agents.create_version(
                            agent_name=_name,
                            definition=PromptAgentDefinition(**kwargs),
                        )
                    except Exception as exc:  # noqa: BLE001  # see fallback below
                        # tool_choice="required" can be rejected on some
                        # preview server builds; retry once without it so
                        # the agent still gets the tool wired (model
                        # decides per-turn whether to call it).
                        if _tc is None or "tool_choice" not in str(exc):
                            raise
                        logger.warning(
                            "bootstrap.foundry: %s rejected tool_choice=%r "
                            "(%s); retrying without tool_choice",
                            _name, _tc, exc,
                        )
                        kwargs.pop("tool_choice", None)
                        return await proj.agents.create_version(
                            agent_name=_name,
                            definition=PromptAgentDefinition(**kwargs),
                        )

                verb = "updated" if name in existing_names else "created"
                created_version = await _retry(
                    _create_version,
                    name=f"foundry.{verb}.{name}",
                    budget_seconds=_retry_budget_seconds(),
                )
                created_version_id = getattr(
                    created_version, "version", None,
                )
                logger.info(
                    "bootstrap.foundry: %s %s "
                    "(model=%s, tool=%s, version=%s)",
                    verb, name, deployment,
                    "yes" if tool is not None else "no",
                    created_version_id or "?",
                )

                # Readback canary — for retrieval-mode agents, fetch the
                # version we just wrote and confirm the KB tool round-
                # tripped. We check membership (not equality) so partner-
                # attached catalog tools merged in above don't trip the
                # canary. Catches silent server-side strip of fields we
                # don't have visibility into yet. Cheap (~1 GET).
                if tool is not None and created_version_id:
                    try:
                        verified = await proj.agents.get_version(
                            name, created_version_id,
                        )
                        v_defn = getattr(verified, "definition", None)
                        if not _kb_tool_present(v_defn, desired_tool_fp):
                            raise RuntimeError(
                                f"foundry.foundry: {name} readback "
                                f"missing KB tool fingerprint "
                                f"{desired_tool_fp!r} — tool not attached"
                            )
                        # Grant Search RBAC to the agent's instance MI now
                        # that the version exists. The principal id is
                        # stable across versions of the same agent name, so
                        # this is a one-time setup cost per agent — but the
                        # helper is idempotent so re-runs are 409 → noop.
                        principal_id = getattr(
                            getattr(verified, "instance_identity", None),
                            "principal_id", None,
                        )
                        await _grant_agent_search_access(
                            principal_id or "", name, cred,
                        )
                    except ResourceNotFoundError as exc:
                        raise RuntimeError(
                            f"foundry.foundry: {name} disappeared right "
                            f"after create_version: {exc}"
                        ) from exc
                    except HttpResponseError as exc:
                        # Some preview surfaces 400 on get_version while
                        # the create above succeeded — log and continue
                        # rather than blocking bootstrap on a verifier.
                        logger.warning(
                            "bootstrap.foundry: %s readback "
                            "get_version(%s) returned %s; "
                            "skipping fingerprint check",
                            name, created_version_id,
                            getattr(exc, "status_code", "?"),
                        )
        finally:
            await proj.close()

        # ---- legacy cleanup pass ----------------------------------------
        # Delete any orphaned legacy Assistants (created by earlier
        # accelerator versions via azure-ai-agents.AgentsClient) whose
        # name collides with one of our desired agents. On a fresh
        # subscription this is a no-op. Failures are logged but not fatal
        # — provisioning succeeded above and the runtime targets the new
        # versioned surface, so an orphaned Assistant is at worst a
        # cosmetic portal nag.
        try:
            from azure.ai.agents.aio import AgentsClient

            legacy = AgentsClient(endpoint=endpoint, credential=cred)
            try:
                async for a in legacy.list_agents():
                    if a.name in desired_names and a.id:
                        try:
                            await legacy.delete_agent(agent_id=a.id)
                            logger.info(
                                "bootstrap.foundry: deleted legacy Assistant %s",
                                a.name,
                            )
                        except Exception as exc:  # pragma: no cover - best effort
                            logger.warning(
                                "bootstrap.foundry: could not delete legacy "
                                "Assistant %s: %s", a.name, exc,
                            )
            finally:
                await legacy.close()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("bootstrap.foundry: legacy cleanup skipped: %s", exc)
    finally:
        await cred.close()


async def _embed_seed_docs(
    docs: list[dict],
    aoai_endpoint: str,
    deployment: str,
    cred: Any,
) -> list[dict]:
    """Add a `contentVector` field to each seed doc by calling AOAI.

    Bootstrap-time embedding for the initial corpus. At query time the
    AzureOpenAIVectorizer attached to the index handles vectorization
    automatically — partners adding new docs via SearchClient.upload_documents
    on an existing deployment must do the same (call AOAI, set contentVector).
    """
    if not aoai_endpoint or not deployment:
        raise RuntimeError(
            "AZURE_AI_FOUNDRY_OPENAI_ENDPOINT and "
            "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT must be set to embed seeds"
        )

    from azure.identity.aio import get_bearer_token_provider
    from openai import AsyncAzureOpenAI

    token_provider = get_bearer_token_provider(
        cred, "https://cognitiveservices.azure.com/.default"
    )
    client = AsyncAzureOpenAI(
        azure_endpoint=aoai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )
    try:
        out: list[dict] = []
        # Embed in small batches to stay well under per-request token caps.
        batch_size = 16
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            inputs = [d.get("content", "") for d in batch]
            resp = await client.embeddings.create(
                model=deployment, input=inputs
            )
            for d, item in zip(batch, resp.data, strict=True):
                merged = dict(d)
                merged["contentVector"] = item.embedding
                out.append(merged)
        return out
    finally:
        await client.close()


async def _bootstrap_search(bundle: ScenarioBundle) -> None:
    if not bundle.retrieval_indexes:
        logger.info("bootstrap.search: no retrieval indexes declared; skipping")
        return

    endpoint = os.environ.get("AZURE_AI_SEARCH_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_AI_SEARCH_ENDPOINT is not set")

    aoai_endpoint = os.environ.get("AZURE_AI_FOUNDRY_OPENAI_ENDPOINT", "")
    embedding_deployment = os.environ.get(
        "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT", ""
    )

    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity.aio import DefaultAzureCredential
    from azure.search.documents.aio import SearchClient
    from azure.search.documents.indexes.aio import SearchIndexClient

    cred = DefaultAzureCredential()
    try:
        ic = SearchIndexClient(endpoint=endpoint, credential=cred)
        try:
            for entry in bundle.retrieval_indexes:
                index = entry.schema_callable(entry.name)
                wants_vector = any(
                    getattr(f, "vector_search_dimensions", None)
                    for f in (index.fields or [])
                )

                # Schema-mismatch detection. If an existing `accounts` index
                # is missing the contentVector field that the new schema
                # requires, delete it so create_or_update_index lays down
                # the new vector schema cleanly. Pre-share testing context;
                # no partner data preservation concern.
                if wants_vector:
                    try:
                        existing = await ic.get_index(entry.name)
                    except ResourceNotFoundError:
                        existing = None
                    if existing is not None:
                        existing_field_names = {
                            f.name for f in (existing.fields or [])
                        }
                        if "contentVector" not in existing_field_names:
                            logger.info(
                                "bootstrap.search: index %s lacks contentVector; "
                                "deleting and recreating with vector schema",
                                entry.name,
                            )
                            await ic.delete_index(entry.name)

                async def _create_index(_ix=index) -> None:
                    await ic.create_or_update_index(_ix)

                await _retry(
                    _create_index,
                    name=f"search.index.{entry.name}",
                    budget_seconds=_retry_budget_seconds(),
                )
                logger.info("bootstrap.search: index ok: %s", entry.name)

                seed_path = ROOT / entry.seed
                if not seed_path.exists():
                    logger.warning(
                        "bootstrap.search: seed file %s missing; skipping seeding",
                        seed_path,
                    )
                    continue

                docs = json.loads(seed_path.read_text(encoding="utf-8"))
                if not docs:
                    continue

                # Embed seeds for vector indexes so the initial corpus
                # has populated contentVector. Query-time vectorization
                # for new docs flows through the index's AzureOpenAIVectorizer.
                if wants_vector:
                    docs = await _embed_seed_docs(
                        docs, aoai_endpoint, embedding_deployment, cred
                    )

                sc = SearchClient(
                    endpoint=endpoint, index_name=entry.name, credential=cred,
                )
                try:
                    async def _upload(_sc=sc, _docs=docs) -> list[Any]:
                        return await _sc.upload_documents(documents=_docs)

                    result = await _retry(
                        _upload,
                        name=f"search.upload.{entry.name}",
                        budget_seconds=_retry_budget_seconds(),
                    )
                    failed = [r for r in result if not r.succeeded]
                    if failed:
                        raise RuntimeError(
                            f"{len(failed)} seed docs failed to upload into "
                            f"{entry.name}"
                        )
                    logger.info(
                        "bootstrap.search: seeded %d docs into %s",
                        len(docs), entry.name,
                    )
                finally:
                    await sc.close()
        finally:
            await ic.close()
    finally:
        await cred.close()


async def _canary_query(bundle: ScenarioBundle) -> None:
    """Synthetic prompt against each retrieval-using agent.

    Drives one ``agent.run()`` per foundry_tool agent through the
    ``agent_framework.azure.AzureAIClient`` SDK and asserts the response
    references at least one citation (URL or doc id) — the cheapest signal
    that the model actually invoked its attached Knowledge Base MCPTool.

    Only runs when ``BOOTSTRAP_CANARY=1`` because each call costs a model
    + Search round-trip. Failure raises so ACA marks the revision unhealthy
    if the gpt-5-mini + MCPTool retrieval combo regresses.
    """
    if os.environ.get("BOOTSTRAP_CANARY") != "1":
        return
    foundry_tool_agents = [
        a for a in bundle.agents
        if a.retrieval is not None and a.retrieval.mode == "foundry_tool"
    ]
    if not foundry_tool_agents:
        return

    try:
        # GA SDK rename: agent_framework.azure.AzureAIClient → agent_framework.foundry.FoundryAgent.
        from agent_framework.foundry import FoundryAgent  # type: ignore
    except Exception as exc:
        logger.warning(
            "bootstrap.canary: agent-framework-foundry not importable (%s); "
            "skipping canary", exc,
        )
        return

    endpoint = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT")
    if not endpoint:
        logger.warning(
            "bootstrap.canary: AZURE_AI_FOUNDRY_ENDPOINT not set; skipping",
        )
        return

    canary_prompt = (
        "Profile the account: Microsoft (microsoft.com). Use your attached "
        "AI Search knowledge tool to retrieve facts and include at least "
        "one citation. Output JSON only."
    )
    from azure.identity.aio import DefaultAzureCredential
    cred = DefaultAzureCredential()
    try:
        for agent in foundry_tool_agents:
            runner = FoundryAgent(
                project_endpoint=endpoint,
                credential=cred,
                agent_name=agent.foundry_name,
                allow_preview=True,
            )
            try:
                result = await runner.run(canary_prompt)
            except Exception as exc:
                raise RuntimeError(
                    f"bootstrap.canary: {agent.foundry_name} run failed: {exc}"
                ) from exc
            text = (getattr(result, "text", "") or "").lower()
            if "http" not in text and "url" not in text and "citations" not in text:
                raise RuntimeError(
                    f"bootstrap.canary: {agent.foundry_name} returned no "
                    f"citation marker — tool likely not invoked. "
                    f"First 400 chars: {text[:400]!r}"
                )
            logger.info(
                "bootstrap.canary: %s ok (%d chars)",
                agent.foundry_name, len(text),
            )
    finally:
        try:
            await cred.close()
        except Exception:  # noqa: S110
            pass


async def bootstrap(bundle: ScenarioBundle) -> None:
    """Run the full deploy-time bootstrap. Idempotent.

    Skipped entirely when ``BOOTSTRAP_SKIP=1`` (local dev / unit tests).
    Any unrecoverable error propagates — callers (the FastAPI lifespan) should
    let it abort process startup so ACA marks the revision unhealthy.
    """
    if os.environ.get("BOOTSTRAP_SKIP") == "1":
        logger.info("bootstrap: BOOTSTRAP_SKIP=1; skipping")
        return

    logger.info("bootstrap: starting (budget=%.0fs)", _retry_budget_seconds())
    started = time.monotonic()
    # Order is load-bearing:
    # 1. AI Search vector index — must exist before anything can query it.
    # 2. Knowledge Source + Knowledge Base (FoundryIQ) — REST API calls on
    #    AI Search that wrap the index into FoundryIQ's agentic retrieval.
    # 3. Foundry agents — wired with MCPTool pointing at the Bicep-
    #    provisioned RemoteTool MCP connection (shows under **Knowledge**
    #    in the Foundry portal).
    await _bootstrap_search(bundle)
    await _bootstrap_knowledge(bundle)
    await _bootstrap_foundry(bundle)
    await _canary_query(bundle)
    logger.info(
        "bootstrap: complete in %.1fs (%d agents, %d index(es))",
        time.monotonic() - started,
        len(bundle.agents),
        len(bundle.retrieval_indexes),
    )
