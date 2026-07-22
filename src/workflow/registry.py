"""Scenario registry — parses ``accelerator.yaml`` and returns a bundle.

Responsibilities (enforced at process startup):
- Require a top-level ``scenario:`` block.
- Validate ``scenario.package`` leaf uses underscores (Python-importable).
- Resolve ``request_schema`` to a Pydantic ``BaseModel`` subclass.
- Resolve ``workflow_factory`` to a callable that returns a ``BaseWorkflow``.
- Parse ``endpoint.path``, ``agents[]``, ``retrieval.indexes[]``, ``evals``.

The registry imports scenario modules. ``scripts/accelerator-lint.py`` does
AST-only validation of the same manifest so CI can catch mis-wiring without
executing any code.
"""
from __future__ import annotations

import importlib
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from .base import BaseWorkflow

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_MANIFEST = ROOT / "accelerator.yaml"

_IMPORT_REF_RE = re.compile(
    r"^[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*:[A-Za-z_][\w]*$"
)


@dataclass(frozen=True)
class AgentRetrieval:
    """How an individual agent gets grounding facts.

    - ``none``: the agent doesn't use retrieval. Default.
    - ``python_injected``: the supervisor calls ``_retrieve`` and stuffs
      ``grounding_chunks`` into the worker's input dict; the prompt builder
      copies them into the system prompt. Backward-compat path; suitable for
      scenarios where you want the orchestrator to control retrieval.
    - ``foundry_tool``: the Foundry agent has an MCPTool attached that
      points at the FoundryIQ Knowledge Base via a Bicep-provisioned
      RemoteTool MCP connection. AI Search handles vector + semantic
      retrieval server-side; ``_retrieve`` is skipped for this worker.
    """

    mode: str  # 'none' | 'python_injected' | 'foundry_tool'
    index: str = ""
    top_k: int = 5
    query_type: str = "vector_semantic_hybrid"


@dataclass(frozen=True)
class ScenarioAgent:
    id: str
    foundry_name: str
    retrieval: AgentRetrieval | None = None


@dataclass(frozen=True)
class ScenarioExperience:
    kind: str = "api"
    title: str = ""
    description: str = ""
    output_sections: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class ScenarioIndex:
    name: str
    seed: str
    schema_callable: Callable[[str], Any]
    # FoundryIQ Knowledge Source `sourceDataFields` — the per-document
    # metadata fields the agent receives as citations alongside content.
    # Defaults to ("source",) which exists in every scaffolded scenario.
    # Flagship adds richer metadata (e.g. company_name, industry).
    source_data_fields: tuple[str, ...] = ("source",)


@dataclass(frozen=True)
class ScenarioContext:
    """Passed to ``workflow_factory`` - everything except the workflow itself."""

    id: str
    package: str
    request_schema: type[BaseModel]
    endpoint_path: str
    agents: tuple[ScenarioAgent, ...]
    retrieval_indexes: tuple[ScenarioIndex, ...]
    evals_quality: str
    evals_redteam: str
    response_schema: type[BaseModel] | None = None
    experience: ScenarioExperience | None = None


@dataclass(frozen=True)
class ScenarioBundle:
    """Final loaded scenario - fully wired, safe to serve."""

    id: str
    package: str
    request_schema: type[BaseModel]
    workflow: BaseWorkflow
    endpoint_path: str
    agents: tuple[ScenarioAgent, ...]
    retrieval_indexes: tuple[ScenarioIndex, ...]
    evals_quality: str
    evals_redteam: str
    response_schema: type[BaseModel] | None = None
    experience: ScenarioExperience | None = None


def _load_yaml(path: pathlib.Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _validate_ref(ref: str, package: str, field: str) -> tuple[str, str]:
    if not isinstance(ref, str) or not _IMPORT_REF_RE.match(ref):
        raise ValueError(
            f"scenario.{field}: expected 'module:attr' form, got {ref!r}"
        )
    module_suffix, attr = ref.split(":")
    return module_suffix, attr


def _resolve_attr(package: str, ref: str, field: str) -> Any:
    module_suffix, attr = _validate_ref(ref, package, field)
    full_module = f"{package}.{module_suffix}"
    try:
        mod = importlib.import_module(full_module)
    except ImportError as exc:
        raise ValueError(
            f"scenario.{field}: cannot import {full_module!r}: {exc}"
        ) from exc
    try:
        return getattr(mod, attr)
    except AttributeError as exc:
        raise ValueError(
            f"scenario.{field}: {full_module} has no attribute {attr!r}"
        ) from exc


def _require_keys(d: dict, keys: list[str], where: str) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"{where}: missing required keys {missing}")


def load_scenario(manifest_path: pathlib.Path | None = None) -> ScenarioBundle:
    """Parse ``accelerator.yaml`` and return the wired ``ScenarioBundle``.

    Raises ``ValueError`` on any manifest error with a path-prefixed message.
    """
    path = manifest_path or DEFAULT_MANIFEST
    data = _load_yaml(path)
    scenario = data.get("scenario")
    if not scenario:
        raise ValueError(
            f"{path}: missing top-level 'scenario' block (required since D2). "
            "See docs/getting-started/setup-and-prereqs.md for the manifest shape."
        )

    _require_keys(
        scenario,
        ["id", "package", "request_schema", "workflow_factory",
         "endpoint", "agents"],
        f"{path}:scenario",
    )

    package = scenario["package"]
    if not isinstance(package, str) or not package:
        raise ValueError("scenario.package must be a non-empty dotted string")
    leaf = package.split(".")[-1]
    if "-" in leaf or not leaf.isidentifier():
        raise ValueError(
            f"scenario.package leaf must be a Python identifier "
            f"(underscores, no hyphens): {leaf!r}"
        )

    # request_schema
    schema_cls = _resolve_attr(package, scenario["request_schema"], "request_schema")
    if not (isinstance(schema_cls, type) and issubclass(schema_cls, BaseModel)):
        raise ValueError(
            "scenario.request_schema must resolve to a pydantic BaseModel subclass"
        )

    response_schema_cls: type[BaseModel] | None = None
    response_schema_ref = scenario.get("response_schema")
    if response_schema_ref is not None:
        resolved_response = _resolve_attr(
            package,
            response_schema_ref,
            "response_schema",
        )
        if not (
            isinstance(resolved_response, type)
            and issubclass(resolved_response, BaseModel)
        ):
            raise ValueError(
                "scenario.response_schema must resolve to a pydantic "
                "BaseModel subclass"
            )
        response_schema_cls = resolved_response

    # workflow_factory
    factory = _resolve_attr(package, scenario["workflow_factory"], "workflow_factory")
    if not callable(factory):
        raise ValueError("scenario.workflow_factory must resolve to a callable")

    # endpoint
    endpoint = scenario.get("endpoint") or {}
    endpoint_path = endpoint.get("path")
    if not isinstance(endpoint_path, str) or not endpoint_path.startswith("/"):
        raise ValueError(
            "scenario.endpoint.path must be a string starting with '/'"
        )

    # agents
    agents_raw = scenario.get("agents") or []
    if not isinstance(agents_raw, list) or not agents_raw:
        raise ValueError("scenario.agents must be a non-empty list")
    agents: list[ScenarioAgent] = []
    valid_modes = {"none", "python_injected", "foundry_tool"}
    for i, a in enumerate(agents_raw):
        if not isinstance(a, dict) or "id" not in a or "foundry_name" not in a:
            raise ValueError(
                f"scenario.agents[{i}]: each entry needs 'id' and 'foundry_name'"
            )
        retrieval_raw = a.get("retrieval")
        retrieval: AgentRetrieval | None = None
        if retrieval_raw is not None:
            if not isinstance(retrieval_raw, dict):
                raise ValueError(
                    f"scenario.agents[{i}].retrieval must be a mapping"
                )
            mode = retrieval_raw.get("mode", "none")
            if mode not in valid_modes:
                raise ValueError(
                    f"scenario.agents[{i}].retrieval.mode must be one of "
                    f"{sorted(valid_modes)}, got {mode!r}"
                )
            retrieval = AgentRetrieval(
                mode=mode,
                index=str(retrieval_raw.get("index", "")),
                top_k=int(retrieval_raw.get("top_k", 5)),
                query_type=str(
                    retrieval_raw.get("query_type", "vector_semantic_hybrid")
                ),
            )
        agents.append(ScenarioAgent(
            id=a["id"], foundry_name=a["foundry_name"], retrieval=retrieval,
        ))

    # retrieval.indexes (optional)
    retrieval_section = scenario.get("retrieval") or {}
    idx_raw = retrieval_section.get("indexes") or []
    indexes: list[ScenarioIndex] = []
    for i, entry in enumerate(idx_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"scenario.retrieval.indexes[{i}] must be a mapping")
        _require_keys(
            entry, ["name", "seed", "schema"],
            f"scenario.retrieval.indexes[{i}]",
        )
        schema_fn = _resolve_attr(
            package, entry["schema"], f"retrieval.indexes[{i}].schema"
        )
        if not callable(schema_fn):
            raise ValueError(
                f"scenario.retrieval.indexes[{i}].schema must resolve to a callable"
            )
        sdf_raw = entry.get("source_data_fields")
        if sdf_raw is None:
            sdf_tuple: tuple[str, ...] = ("source",)
        elif isinstance(sdf_raw, list) and all(isinstance(x, str) for x in sdf_raw):
            sdf_tuple = tuple(sdf_raw) or ("source",)
        else:
            raise ValueError(
                f"scenario.retrieval.indexes[{i}].source_data_fields must be "
                "a list of strings (or omit it for the default ['source'])"
            )
        indexes.append(ScenarioIndex(
            name=entry["name"], seed=entry["seed"], schema_callable=schema_fn,
            source_data_fields=sdf_tuple,
        ))

    evals = scenario.get("evals") or {}
    quality_dataset = evals.get("quality_dataset", "")
    redteam_dataset = evals.get("redteam_dataset", "")
    experience_raw = scenario.get("experience")
    experience: ScenarioExperience | None = None
    if experience_raw is not None:
        if not isinstance(experience_raw, dict):
            raise ValueError("scenario.experience must be a mapping")
        output_sections_raw = experience_raw.get("output_sections") or []
        if not isinstance(output_sections_raw, list) or not all(
            isinstance(item, dict) for item in output_sections_raw
        ):
            raise ValueError("scenario.experience.output_sections must be a list")
        experience = ScenarioExperience(
            kind=str(experience_raw.get("kind") or "api"),
            title=str(experience_raw.get("title") or scenario["id"]),
            description=str(experience_raw.get("description") or ""),
            output_sections=tuple(
                {
                    str(key): str(value)
                    for key, value in item.items()
                    if isinstance(key, str)
                }
                for item in output_sections_raw
            ),
        )

    ctx = ScenarioContext(
        id=scenario["id"],
        package=package,
        request_schema=schema_cls,
        endpoint_path=endpoint_path,
        agents=tuple(agents),
        retrieval_indexes=tuple(indexes),
        evals_quality=quality_dataset,
        evals_redteam=redteam_dataset,
        response_schema=response_schema_cls,
        experience=experience,
    )

    workflow = factory(ctx)
    if not hasattr(workflow, "stream") or not callable(
        workflow.stream  # pyright: ignore[reportAttributeAccessIssue]  # checked via hasattr above
    ):
        raise ValueError(
            "workflow_factory must return an object with an async 'stream' method"
        )

    return ScenarioBundle(
        id=ctx.id,
        package=ctx.package,
        request_schema=ctx.request_schema,
        workflow=workflow,  # pyright: ignore[reportArgumentType]  # duck-typed BaseWorkflow; hasattr check above is the contract
        endpoint_path=ctx.endpoint_path,
        agents=ctx.agents,
        retrieval_indexes=ctx.retrieval_indexes,
        evals_quality=ctx.evals_quality,
        evals_redteam=ctx.evals_redteam,
        response_schema=ctx.response_schema,
        experience=ctx.experience,
    )


def read_scenario_raw(
    manifest_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Return the raw ``scenario:`` block without resolving imports.

    Used by callers (e.g. evals, scaffolding helpers, ``src.provisioning``)
    that need the declared values without booting the whole app. Raises
    ``ValueError`` if the block is missing or the manifest is unreadable.
    """
    path = manifest_path or DEFAULT_MANIFEST
    data = _load_yaml(path)
    scenario = data.get("scenario")
    if not scenario:
        raise ValueError(f"{path}: missing top-level 'scenario' block")
    return scenario
