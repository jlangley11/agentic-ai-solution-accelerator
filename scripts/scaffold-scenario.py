"""Materialize a new scenario skeleton under ``src/scenarios/<package>/``.

Usage::

    python scripts/scaffold-scenario.py <scenario-id> --display "Human Name"
    python scripts/scaffold-scenario.py order-triage --display "Order Triage"

Creates:
- ``src/scenarios/<package>/__init__.py``
- ``src/scenarios/<package>/schema.py``         (request BaseModel stub)
- ``src/scenarios/<package>/workflow.py``       (BaseWorkflow + build_workflow factory)
- ``src/scenarios/<package>/retrieval.py``      (FoundryIQ-shaped index_definition)
- ``src/scenarios/<package>/agents/__init__.py``
- ``src/scenarios/<package>/agents/supervisor/{__init__,prompt,transform,validate}.py``
- ``docs/agent-specs/accel-<scenario-id>-supervisor.md`` (spec stub)
- ``data/samples/<package>.json``               (empty seed)

Behaviour:
- Fails fast if any target path already exists (no accidental overwrites).
- On failure mid-run, removes paths it created in this invocation (best-effort
  rollback; existing files are left untouched).
- Does NOT edit ``accelerator.yaml`` automatically; prints the ``scenario:``
  block to paste in manually so operator review is explicit.
- Defaults the printed ``scenario:`` snippet to FoundryIQ-shape grounding
  (``mode: foundry_tool`` on the supervisor, AI Search index underneath
  with vectorizer + semantic + HNSW). FoundryIQ is the consolidated
  enterprise knowledge layer and the recommended starting point for every
  scenario; partners on read-only-from-input scenarios can pass
  ``--no-retrieval`` to omit the retrieval blocks.

Guardrails:
- Scenario IDs may contain hyphens (``order-triage``); package dirs are
  auto-converted to underscores (``order_triage``) because Python imports
  require it.
- Rejects IDs that aren't lowercase alphanumerics (with hyphens).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parent.parent
_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def _package_leaf(scenario_id: str) -> str:
    return scenario_id.replace("-", "_")


def _supervisor_foundry_name(scenario_id: str) -> str:
    return f"accel-{scenario_id}-supervisor"


TEMPLATES: dict[str, Callable[[str, str], str]] = {
    "__init__.py": lambda sid, leaf: (
        f'"""Scenario: {sid}.\n\n'
        f"Exports are intentionally empty — the scenario is consumed via\n"
        f":mod:`src.workflow.registry` which resolves ``schema:`` and\n"
        f'``workflow_factory:`` by module path from ``accelerator.yaml``.\n"""\n'
    ),
    "schema.py": lambda sid, leaf: (
        '"""Request schema for the {sid} scenario."""\n'
        'from __future__ import annotations\n\n'
        'from typing import Any\n\n'
        'from pydantic import BaseModel, Field\n\n\n'
        'class ScenarioRequest(BaseModel):\n'
        '    """Inputs the scenario accepts. Extend as needed."""\n'
        '    query: str\n\n\n'
        'class ScenarioResponse(BaseModel):\n'
        '    """Validated final response rendered by generated clients."""\n'
        '    result: dict[str, Any] = Field(default_factory=dict)\n'
    ).format(sid=sid),
    "retrieval.py": lambda sid, leaf: (
        '"""Index definitions for the {sid} scenario (FoundryIQ pattern).\n\n'
        'The ``schema`` callable is referenced from ``accelerator.yaml`` and is\n'
        'the single source of truth for the AI Search index shape that sits\n'
        'underneath the FoundryIQ Knowledge Source + Knowledge Base. The\n'
        'index is created by ``src/bootstrap.py`` at FastAPI startup; at\n'
        'runtime the application code does not need the schema -- agents\n'
        'query the index transparently through the FoundryIQ MCPTool.\n\n'
        'The vectorizer + semantic + HNSW shape mirrors the flagship so a\n'
        'scaffolded scenario is FoundryIQ-ready out of the box. Partners\n'
        'extend ``fields`` with domain-specific filterables / facetables;\n'
        'the embedding wiring is intentionally not partner-tunable.\n'
        '"""\n'
        'from __future__ import annotations\n\n'
        'import os\n\n'
        'from azure.search.documents.indexes.models import (\n'
        '    AzureOpenAIVectorizer,\n'
        '    AzureOpenAIVectorizerParameters,\n'
        '    HnswAlgorithmConfiguration,\n'
        '    SearchableField,\n'
        '    SearchField,\n'
        '    SearchIndex,\n'
        '    SemanticConfiguration,\n'
        '    SemanticField,\n'
        '    SemanticPrioritizedFields,\n'
        '    SemanticSearch,\n'
        '    SimpleField,\n'
        '    VectorSearch,\n'
        '    VectorSearchProfile,\n'
        ')\n\n'
        '# text-embedding-3-small. Changing this invalidates every stored\n'
        '# vector in the index -- not a partner-tunable parameter.\n'
        'EMBEDDING_DIMENSIONS = 1536\n\n'
        'ALGORITHM_NAME = "accel-hnsw"\n'
        'VECTORIZER_NAME = "accel-aoai"\n'
        'PROFILE_NAME = "accel-vector-profile"\n\n\n'
        'def index_definition(name: str) -> SearchIndex:\n'
        '    """Return the FoundryIQ-shaped index for this scenario.\n\n'
        '    Reads two env vars wired by ``infra/modules/container-app.bicep``:\n'
        '        - ``AZURE_AI_FOUNDRY_OPENAI_ENDPOINT``\n'
        '        - ``AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT``\n'
        '    The Search service authenticates as its SystemAssigned MI\n'
        '    (Cognitive Services OpenAI User on the Foundry account, granted\n'
        '    in ``main.bicep``); no keys.\n'
        '    """\n'
        '    aoai_endpoint = os.environ.get(\n'
        '        "AZURE_AI_FOUNDRY_OPENAI_ENDPOINT", ""\n'
        '    )\n'
        '    embedding_deployment = os.environ.get(\n'
        '        "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT",\n'
        '        "text-embedding-3-small",\n'
        '    )\n\n'
        '    return SearchIndex(\n'
        '        name=name,\n'
        '        fields=[\n'
        '            SimpleField(\n'
        '                name="id", type="Edm.String", key=True\n'
        '            ),\n'
        '            SearchableField(\n'
        '                name="content", type="Edm.String"\n'
        '            ),\n'
        '            SearchField(\n'
        '                name="contentVector",\n'
        '                type="Collection(Edm.Single)",\n'
        '                searchable=True,\n'
        '                vector_search_dimensions=EMBEDDING_DIMENSIONS,\n'
        '                vector_search_profile_name=PROFILE_NAME,\n'
        '            ),\n'
        '            SimpleField(\n'
        '                name="source",\n'
        '                type="Edm.String",\n'
        '                filterable=True,\n'
        '            ),\n'
        '            # TODO: add domain-specific filterable / facetable fields here.\n'
        '        ],\n'
        '        vector_search=VectorSearch(\n'
        '            algorithms=[\n'
        '                HnswAlgorithmConfiguration(name=ALGORITHM_NAME)\n'
        '            ],\n'
        '            profiles=[\n'
        '                VectorSearchProfile(\n'
        '                    name=PROFILE_NAME,\n'
        '                    algorithm_configuration_name=ALGORITHM_NAME,\n'
        '                    vectorizer_name=VECTORIZER_NAME,\n'
        '                )\n'
        '            ],\n'
        '            vectorizers=[\n'
        '                AzureOpenAIVectorizer(\n'
        '                    vectorizer_name=VECTORIZER_NAME,\n'
        '                    parameters=AzureOpenAIVectorizerParameters(\n'
        '                        resource_url=aoai_endpoint,\n'
        '                        deployment_name=embedding_deployment,\n'
        '                        model_name="text-embedding-3-small",\n'
        '                        auth_identity=None,\n'
        '                    ),\n'
        '                )\n'
        '            ],\n'
        '        ),\n'
        '        semantic_search=SemanticSearch(\n'
        '            configurations=[\n'
        '                SemanticConfiguration(\n'
        '                    name="default",\n'
        '                    prioritized_fields=SemanticPrioritizedFields(\n'
        '                        content_fields=[\n'
        '                            SemanticField(field_name="content")\n'
        '                        ],\n'
        '                    ),\n'
        '                )\n'
        '            ]\n'
        '        ),\n'
        '    )\n'
    ).format(sid=sid),
    "workflow.py": lambda sid, leaf: (
        '"""Workflow for the {sid} scenario.\n\n'
        'Skeleton supervisor + workers shape, scaffold-managed. The\n'
        '``WORKERS`` dict and the ``from .agents import (...)`` block are\n'
        'the canonical attachment points that ``scripts/scaffold-agent.py``\n'
        'edits when partners run ``/add-worker-agent``. Keep both in the\n'
        'tuple form; hand edits whose shape doesn\'t match flip the file\n'
        'to "no longer scaffold-managed" and break future automation.\n'
        '"""\n'
        'from __future__ import annotations\n\n'
        'from typing import Any, AsyncIterator\n\n'
        'from src.accelerator_baseline.killswitch import assert_enabled\n'
        'from src.accelerator_baseline.telemetry import Event, emit_event\n'
        'from src.workflow.base import BaseWorkflow\n'
        'from src.workflow.supervisor import WorkerSpec\n\n'
        'from .agents import (\n'
        '    supervisor,\n'
        ')\n\n\n'
        '# WORKERS is the supervisor DAG attachment point. ``scaffold-agent.py``\n'
        '# inserts new ``"<agent_id>": WorkerSpec(...)`` entries here. Until at\n'
        '# least one worker is scaffolded, the workflow runs the supervisor\n'
        '# alone (echo behaviour below).\n'
        'WORKERS: dict[str, WorkerSpec] = {{\n'
        '}}\n\n\n'
        'class {class_name}Workflow:\n'
        '    """Minimal scenario workflow. Replace the echo body below once the\n'
        '    supervisor + workers DAG is wired. The ``WORKERS`` dict above is\n'
        '    the attachment point ``scaffold-agent.py`` edits.\n'
        '    """\n\n'
        '    def __init__(self, *, primary_index_name: str = "") -> None:\n'
        '        self._primary_index_name = primary_index_name\n\n'
        '    async def stream(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:\n'
        '        assert_enabled("workflow")\n'
        '        emit_event(Event(name="request.received"))\n'
        '        yield {{"type": "status", "stage": "supervisor.planning"}}\n'
        '        # TODO: invoke supervisor + workers here. Until then, echo\n'
        '        # the request so the endpoint streams something deterministic.\n'
        '        emit_event(Event(name="response.returned", ok=True))\n'
        '        yield {{"type": "final", "briefing": {{"result": {{"echo": request}}}}}}\n\n\n'
        'def build_workflow(context: Any) -> BaseWorkflow:\n'
        '    indexes = getattr(context, "retrieval_indexes", ()) or ()\n'
        '    primary = indexes[0].name if indexes else ""\n'
        '    return {class_name}Workflow(primary_index_name=primary)\n'
    ).format(sid=sid, class_name="".join(p.title() for p in leaf.split("_"))),
    "agents/__init__.py": lambda sid, leaf: (
        f'"""Agent registry for {sid}. Add workers here as they scaffold in.\n\n'
        f'The ``from . import (...)`` block and ``__all__`` list are\n'
        f'scaffold-managed in tuple form; ``scripts/scaffold-agent.py``\n'
        f'inserts new agent ids alphabetically into both. Hand-edits that\n'
        f'collapse this to a single-name import flip the file to "no longer\n'
        f'scaffold-managed" and break ``/add-worker-agent``.\n"""\n'
        f"from . import (\n"
        f"    supervisor,\n"
        f")\n\n"
        f'__all__ = [\n'
        f'    "supervisor",\n'
        f']\n'
    ),
    "agents/supervisor/__init__.py": lambda sid, leaf: (
        f'"""Supervisor agent for {sid}."""\n'
        f"from .prompt import build_prompt\n"
        f"from .transform import transform_response\n"
        f"from .validate import validate_response\n\n"
        f'AGENT_NAME = "{_supervisor_foundry_name(sid)}"\n'
        f'__all__ = ["AGENT_NAME", "build_prompt", "transform_response", '
        f'"validate_response"]\n'
    ),
    "agents/supervisor/prompt.py": lambda sid, leaf: (
        '"""Supervisor prompt builder - pure function, no side effects."""\n'
        'from __future__ import annotations\n\n'
        'from typing import Any\n\n\n'
        'def build_prompt(request: dict[str, Any]) -> str:\n'
        '    return (\n'
        '        "You are the supervisor. Plan the workers and synthesise the final "\n'
        '        f"briefing.\\nREQUEST:\\n{request}\\n"\n'
        '    )\n'
    ),
    "agents/supervisor/transform.py": lambda sid, leaf: (
        '"""Normalise supervisor output to a dict."""\n'
        'from __future__ import annotations\n\n'
        'import json\n'
        'from typing import Any\n\n\n'
        'def transform_response(raw: str) -> dict[str, Any]:\n'
        '    if not raw:\n'
        '        return {}\n'
        '    try:\n'
        '        return json.loads(raw)\n'
        '    except Exception:\n'
        '        return {"text": raw}\n'
    ),
    "agents/supervisor/validate.py": lambda sid, leaf: (
        '"""Validate supervisor output shape."""\n'
        'from __future__ import annotations\n\n'
        'from typing import Any\n\n\n'
        'def validate_response(data: dict[str, Any]) -> tuple[bool, str]:\n'
        '    if not isinstance(data, dict):\n'
        '        return False, "supervisor output must be a JSON object"\n'
        '    return True, ""\n'
    ),
}


SPEC_TEMPLATE = """# {agent_name}

> **This file IS your agent's system instructions.** The `## Instructions`
> section below is synced **verbatim** to the Foundry portal by
> `src/bootstrap.py` (run inside the Container App at FastAPI startup) on
> every `azd up` / `azd deploy`. **Edit this file to change agent behaviour.**
> Never put agent system instructions in Python code — `prompt.py` builds
> *per-request* input, not system instructions.

Foundry agent spec for the {sid} scenario's supervisor. The model comes
from ``AZURE_AI_FOUNDRY_MODEL`` (emitted by Bicep) - do NOT add a
``**Model:**`` field here (the lint blocks it).

## Instructions

You are the supervisor agent for the {sid} scenario. **Replace this
paragraph with the real system instructions for your scenario** — describe
the agent's role, the exact JSON output contract, grounding rules, and any
HITL-related obligations. Your job is to plan which worker agents to invoke
for each request, and to synthesise their outputs into a single final
briefing. Follow the accelerator's HITL + grounding policies; never call
side-effect tools directly.
"""


MANIFEST_SNIPPET_FOUNDRYIQ = """# Paste this under the existing `scenario:` block, or replace the current one.
scenario:
  id: {sid}
  package: src.scenarios.{leaf}
  request_schema: schema:ScenarioRequest
  response_schema: schema:ScenarioResponse
  workflow_factory: workflow:build_workflow
  endpoint:
    path: /{leaf}/stream
  experience:
    kind: form-report
    title: {sid}
    description: ""
    output_sections:
      - {{ key: result, label: Result, layout: record }}
  agents:
    - id: supervisor
      foundry_name: {agent_name}
      retrieval:
        # FoundryIQ Knowledge Base pattern (default; recommended starting point).
        # Bootstrap creates a Knowledge Source + Knowledge Base on the AI Search
        # index below, then wires the agent with an MCPTool pointing at the
        # Bicep-provisioned RemoteTool MCP connection. AI Search appears under
        # the agent's **Knowledge** section in the Foundry portal. The workflow
        # does NOT inject Python grounding into the prompt for this agent --
        # the agent retrieves through the MCPTool when the model decides to.
        mode: foundry_tool
        index: {leaf}
        # top_k / query_type are advisory descriptors today (FoundryIQ MCPTool
        # does not yet consume them at runtime). Keep them documented so the
        # intent is visible; they will be honoured once the MCPTool surface
        # exposes per-call tuning.
        top_k: 5
        query_type: vector_semantic_hybrid
  retrieval:
    indexes:
      - name: {leaf}
        seed: data/samples/{leaf}.json
        schema: retrieval:index_definition
  evals:
    quality_dataset: evals/quality/golden_cases.jsonl
    redteam_dataset: evals/redteam/cases.jsonl
"""


MANIFEST_SNIPPET_NO_RETRIEVAL = """# Paste this under the existing `scenario:` block, or replace the current one.
# `--no-retrieval`: scenario operates on input only; no AI Search / FoundryIQ.
scenario:
  id: {sid}
  package: src.scenarios.{leaf}
  request_schema: schema:ScenarioRequest
  response_schema: schema:ScenarioResponse
  workflow_factory: workflow:build_workflow
  endpoint:
    path: /{leaf}/stream
  experience:
    kind: form-report
    title: {sid}
    description: ""
    output_sections:
      - {{ key: result, label: Result, layout: record }}
  agents:
    - {{ id: supervisor, foundry_name: {agent_name} }}
  evals:
    quality_dataset: evals/quality/golden_cases.jsonl
    redteam_dataset: evals/redteam/cases.jsonl
"""


def _plan(scenario_id: str, *, no_retrieval: bool = False) -> list[tuple[pathlib.Path, str]]:
    leaf = _package_leaf(scenario_id)
    pkg_root = ROOT / "src" / "scenarios" / leaf
    agent_name = _supervisor_foundry_name(scenario_id)
    files: list[tuple[pathlib.Path, str]] = []
    for rel, tmpl in TEMPLATES.items():
        # Skip retrieval.py when --no-retrieval; the manifest won't reference it.
        if no_retrieval and rel == "retrieval.py":
            continue
        files.append((pkg_root / rel, tmpl(scenario_id, leaf)))
    files.append((
        ROOT / "docs" / "agent-specs" / f"{agent_name}.md",
        SPEC_TEMPLATE.format(agent_name=agent_name, sid=scenario_id),
    ))
    files.append((
        ROOT / "data" / "samples" / f"{leaf}.json",
        "[]\n",
    ))
    return files


def _golden_cases_stub(scenario_id: str) -> str:
    """One-line JSONL stub case exercising only the supervisor.

    `scaffold-agent.py` appends each new worker id to the case's ``exercises``
    array as workers are added, so by the time the partner runs `/implement-
    workers` the file is well-formed and the ``agent_has_golden_case`` lint
    rule passes. Partner refines the case body (``query``, ``expected``) when
    they wire the real evaluator. The stub deliberately uses ``must_cite:
    false`` so the case doesn't require grounding before the workers exist.
    """
    case = {
        "case_id": "q-001",
        "scenario": scenario_id,
        "query": (
            f"TODO: replace with a representative {scenario_id} request. "
            "Refine `expected` to encode the success criteria from your "
            "discovery brief."
        ),
        "expected": {"must_cite": False},
        "exercises": ["supervisor"],
    }
    return json.dumps(case, separators=(",", ":")) + "\n"


def _rollback(created: list[pathlib.Path]) -> None:
    for p in reversed(created):
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                # only remove if empty
                try:
                    p.rmdir()
                except OSError:
                    pass
        except Exception as exc:
            print(f"::warning::rollback could not remove {p}: {exc}",
                  file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("scenario_id",
                    help="slug (lowercase; hyphens ok). E.g. 'order-triage'.")
    ap.add_argument("--display", default="",
                    help="(reserved) human-readable display name")
    ap.add_argument("--no-retrieval", action="store_true",
                    help="emit a scenario without grounding (no retrieval.py "
                         "and no scenario.retrieval.indexes block in the "
                         "printed manifest snippet). Default is FoundryIQ "
                         "grounding -- the recommended starting point.")
    ap.add_argument("--no-evals", action="store_true",
                    help="skip rewriting evals/quality/golden_cases.jsonl. "
                         "By default, the file is replaced with a one-case "
                         "stub exercising the supervisor only; scaffold-agent.py "
                         "extends each case's `exercises` array as workers are "
                         "added, so `agent_has_golden_case` lint stays green "
                         "during scaffold. Use this flag if you've already "
                         "authored the file and want to preserve it.")
    args = ap.parse_args()

    sid = args.scenario_id.strip()
    if not _ID_RE.match(sid):
        print(f"::error::invalid scenario id {sid!r}; must match "
              f"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", file=sys.stderr)
        return 2

    plan = _plan(sid, no_retrieval=args.no_retrieval)
    conflicts = [p for p, _ in plan if p.exists()]
    if conflicts:
        print("::error::targets already exist; refusing to overwrite:",
              file=sys.stderr)
        for p in conflicts:
            print(f"  {p}", file=sys.stderr)
        return 2

    created: list[pathlib.Path] = []
    golden_cases_path = ROOT / "evals" / "quality" / "golden_cases.jsonl"
    golden_cases_backup: str | None = None
    try:
        for path, content in plan:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Track the directory chain so rollback is complete.
            for anc in reversed(path.parents):
                if anc == ROOT or anc in created:
                    continue
                if anc.exists() and anc.is_dir() and not any(anc.iterdir()):
                    created.append(anc)
            path.write_text(content, encoding="utf-8")
            created.append(path)

        # Replace golden_cases.jsonl with a fresh stub so the new scenario
        # starts with a passing `agent_has_golden_case` lint floor. Snapshot
        # the original first so any failure rolls back cleanly.
        if not args.no_evals:
            if golden_cases_path.exists():
                golden_cases_backup = golden_cases_path.read_text(
                    encoding="utf-8"
                )
            else:
                golden_cases_path.parent.mkdir(parents=True, exist_ok=True)
                created.append(golden_cases_path)
            golden_cases_path.write_text(
                _golden_cases_stub(sid), encoding="utf-8"
            )

        leaf = _package_leaf(sid)
        agent_name = _supervisor_foundry_name(sid)
        snippet = (
            MANIFEST_SNIPPET_NO_RETRIEVAL if args.no_retrieval
            else MANIFEST_SNIPPET_FOUNDRYIQ
        )
        print(f"scaffolded scenario: src/scenarios/{leaf}/")
        if args.no_retrieval:
            print("(no retrieval -- scenario operates on input only)")
        else:
            print("(default: FoundryIQ grounding -- AI Search underneath, "
                  "MCPTool wired by bootstrap)")
        if not args.no_evals:
            print("(seeded evals/quality/golden_cases.jsonl with a "
                  "supervisor-only stub case; scaffold-agent.py extends "
                  "`exercises` per worker)")
        print("")
        print("Next step — paste this into accelerator.yaml:")
        print("")
        print(snippet.format(sid=sid, leaf=leaf, agent_name=agent_name))
        return 0
    except Exception as exc:
        print(f"::error::scaffold failed: {exc}", file=sys.stderr)
        # Restore golden_cases.jsonl first, then unwind created paths.
        if golden_cases_backup is not None:
            try:
                golden_cases_path.write_text(
                    golden_cases_backup, encoding="utf-8"
                )
            except Exception as restore_exc:
                print(f"::warning::could not restore golden_cases.jsonl: "
                      f"{restore_exc}", file=sys.stderr)
        _rollback(created)
        print("::error::rolled back partially-created paths.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
