"""Surgical manifest updates that preserve unrelated comments and sections."""
from __future__ import annotations

import re
from typing import Any

import yaml

from .repository import RepositoryContext

_TOP_LEVEL_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*(?:#.*)?$")
_SECTION_SEPARATOR = re.compile(r"^# -{20,}\s*$")


def scenario_block(
    scenario_id: str,
    *,
    no_retrieval: bool,
    agent_type: str = "hosted-agent",
    implementation_pattern: str = "custom-workflow",
    orchestration_pattern: str = "supervisor-routing",
    application_shell: str = "workbench",
) -> dict[str, Any]:
    leaf = scenario_id.replace("-", "_")
    agent_id = (
        "primary"
        if agent_type == "prompt-agent" or implementation_pattern == "harness"
        else "supervisor"
    )
    foundry_name = f"accel-{scenario_id}-{agent_id}"
    experience_kind = {
        "none": "api",
        "existing-app": "dashboard",
        "workbench": "form-report",
        "custom": "api",
    }.get(application_shell, "api")
    block: dict[str, Any] = {
        "id": scenario_id,
        "package": f"src.scenarios.{leaf}",
        "request_schema": "schema:ScenarioRequest",
        "response_schema": "schema:ScenarioResponse",
        "workflow_factory": "workflow:build_workflow",
        "endpoint": {"path": f"/{leaf}/stream"},
        "experience": {
            "kind": experience_kind,
            "title": scenario_id.replace("-", " ").title(),
            "description": "",
            "output_sections": [
                {"key": "result", "label": "Result", "layout": "record"}
            ],
        },
        "implementation": {
            "agent_type": agent_type,
            "implementation_pattern": implementation_pattern,
            "orchestration_pattern": orchestration_pattern,
            "application_shell": application_shell,
        },
        "architecture_diagram": {
            "path": (
                f"docs/assets/diagrams/{scenario_id}-architecture.svg"
            ),
            "provenance": (
                f"docs/assets/diagrams/{scenario_id}-architecture.mcp.json"
            ),
            "generator": "azure-architecture-diagram-builder-mcp",
            "version": "1.0.0",
            "tools": [
                "list_services",
                "validate_architecture",
                "render_diagram",
            ],
        },
        "agents": [{"id": agent_id, "foundry_name": foundry_name}],
        "evals": {
            "quality_dataset": "evals/quality/golden_cases.jsonl",
            "redteam_dataset": "evals/redteam/cases.jsonl",
        },
    }
    if not no_retrieval and implementation_pattern != "harness":
        block["agents"][0]["retrieval"] = {
            "mode": "foundry_tool",
            "index": leaf,
            "top_k": 5,
            "query_type": "vector_semantic_hybrid",
        }
        block["retrieval"] = {
            "indexes": [
                {
                    "name": leaf,
                    "seed": f"data/samples/{leaf}.json",
                    "schema": "retrieval:index_definition",
                }
            ]
        }
    return block


def render_scenario_yaml(block: dict[str, Any]) -> str:
    return yaml.safe_dump(
        {"scenario": block},
        sort_keys=False,
        allow_unicode=False,
    ).rstrip() + "\n"


def render_architecture_yaml(block: dict[str, Any]) -> str:
    return yaml.safe_dump(
        {"architecture": block},
        sort_keys=False,
        allow_unicode=False,
    ).rstrip() + "\n"


def replace_scenario(
    context: RepositoryContext,
    block: dict[str, Any],
    *,
    apply: bool,
) -> tuple[str, str]:
    path = context.manifest_path
    original = path.read_text(encoding="utf-8")
    updated = _replace_top_level_block(original, "scenario", render_scenario_yaml(block))
    if apply:
        path.write_text(updated, encoding="utf-8")
    return original, updated


def replace_architecture(
    context: RepositoryContext,
    block: dict[str, Any],
    *,
    apply: bool,
) -> tuple[str, str]:
    path = context.manifest_path
    original = path.read_text(encoding="utf-8")
    updated = _replace_top_level_block(
        original,
        "architecture",
        render_architecture_yaml(block),
    )
    if apply:
        path.write_text(updated, encoding="utf-8")
    return original, updated


def _replace_top_level_block(text: str, key: str, replacement: str) -> str:
    lines = text.splitlines(keepends=True)
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.rstrip("\r\n") == f"{key}:"
        ),
        None,
    )
    if start is None:
        prefix = text.rstrip() + "\n\n" if text.strip() else ""
        return prefix + replacement

    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].rstrip("\r\n")
        if _SECTION_SEPARATOR.match(stripped):
            end = index
            break
        if not stripped.startswith((" ", "\t", "#")) and _TOP_LEVEL_KEY.match(stripped):
            end = index
            break
    before = "".join(lines[:start])
    after = "".join(lines[end:])
    separator = "\n" if after and not replacement.endswith("\n\n") else ""
    return before + replacement + separator + after
