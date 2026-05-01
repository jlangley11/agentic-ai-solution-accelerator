"""Normalise intake_validator output to the canonical dict shape.

Coerces the four contract fields into stable types so the downstream
workers and validators don't need to defend against optional fields or
``None`` values.
"""
from __future__ import annotations

import json
from typing import Any

# Mirrors src/scenarios/contoso_supplier_risk/schema.py and the brief §5c
# UX inputs table. Keep in sync if the schema changes.
_INTAKE_FIELDS: tuple[str, ...] = (
    "supplier_name",
    "supplier_id",
    "review_reason",
    "category",
    "country",
    "annual_spend_usd",
    "due_date",
    "requested_by",
    "evidence_packet_uri",
)


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


def _coerce_str_list(raw: Any, *, max_items: int | None = None) -> list[str]:
    if not isinstance(raw, list):
        return []
    cleaned = [s for s in raw if isinstance(s, str) and s.strip()]
    return cleaned[:max_items] if max_items else cleaned


def transform_response(response: str | dict[str, Any]) -> dict[str, Any]:
    data = _parse(response)
    summary_raw = data.get("intake_summary") or {}
    if not isinstance(summary_raw, dict):
        summary_raw = {}
    intake_summary = {f: summary_raw.get(f) for f in _INTAKE_FIELDS}
    return {
        "intake_summary": intake_summary,
        "missing_required_inputs": _coerce_str_list(
            data.get("missing_required_inputs"),
        ),
        "data_quality_warnings": _coerce_str_list(
            data.get("data_quality_warnings"), max_items=3,
        ),
        "sources": [],
    }
