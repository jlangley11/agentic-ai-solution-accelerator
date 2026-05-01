"""Normalise case_drafter output to the canonical dict shape.

Coerces the action list, the tool_previews dict, and the sources list
into stable types. The downstream HITL driver consumes ``tool_previews``
verbatim, so any out-of-allow-list tool is dropped here at transform
time -- the validator then enforces the contract.
"""
from __future__ import annotations

import json
from typing import Any

ALLOWED_TOOLS: frozenset[str] = frozenset({
    "create_supplier_risk_case",
    "update_supplier_review_status",
})

_VALID_SOURCE_SYSTEMS: frozenset[str] = frozenset({
    "sharepoint",
    "azure_sql",
    "dynamics_365_finance",
    "servicenow",
    "blob_storage",
})


def _parse(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}


def _coerce_actions(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [s.strip() for s in raw if isinstance(s, str) and s.strip()]


def _coerce_tool_previews(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for tool_name, kwargs in raw.items():
        if tool_name not in ALLOWED_TOOLS:
            # Drop out-of-allow-list previews here so the downstream
            # HITL driver never sees them. The validator still rejects
            # forbidden tool names so partners notice the regression.
            continue
        if not isinstance(kwargs, dict):
            continue
        out[tool_name] = kwargs
    return out


def _dedupe_sources(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        ss = s.get("source_system")
        src = s.get("source")
        if not (
            isinstance(ss, str) and ss in _VALID_SOURCE_SYSTEMS
            and isinstance(src, str) and src.strip()
        ):
            continue
        key = (ss, src)
        if key in seen:
            continue
        seen.add(key)
        out.append({"source_system": ss, "source": src.strip()})
    return out


def transform_response(response: str | dict[str, Any]) -> dict[str, Any]:
    data = _parse(response)
    return {
        "recommended_next_actions": _coerce_actions(
            data.get("recommended_next_actions"),
        ),
        "recommendation_summary": (
            data.get("recommendation_summary") or ""
        ).strip()
        if isinstance(data.get("recommendation_summary"), str)
        else "",
        "hitl_decision_prompt": (
            data.get("hitl_decision_prompt") or ""
        ).strip()
        if isinstance(data.get("hitl_decision_prompt"), str)
        else "",
        "tool_previews": _coerce_tool_previews(data.get("tool_previews")),
        "sources": _dedupe_sources(data.get("sources")),
    }
