"""Validate intake_validator output shape.

The intake_validator never makes factual claims (it only echoes
analyst-provided fields and flags missing inputs), so the
``citations`` groundedness rule from
``src.accelerator_baseline.citations`` does not apply here. Instead we
enforce the structural contract: required fields present, list-typed
fields actually lists, and forbidden cross-agent fields absent.
"""
from __future__ import annotations

from typing import Any

REQUIRED_FIELDS: tuple[str, ...] = (
    "intake_summary",
    "missing_required_inputs",
    "data_quality_warnings",
    "sources",
)

# Fields owned by other workers in this scenario; their presence here
# means cross-agent contamination (the model leaked downstream content
# into intake validation).
FORBIDDEN_FIELDS: tuple[str, ...] = (
    "evidence_pack",
    "risk_scorecard",
    "recommended_next_actions",
    "tool_previews",
    "executive_summary",
)

_INTAKE_KEYS: frozenset[str] = frozenset({
    "supplier_name",
    "supplier_id",
    "review_reason",
    "category",
    "country",
    "annual_spend_usd",
    "due_date",
    "requested_by",
    "evidence_packet_uri",
})


def validate_response(response: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(response, dict):
        return False, "response must be a JSON object"
    for f in REQUIRED_FIELDS:
        if f not in response:
            return False, f"missing field: {f}"
    for f in FORBIDDEN_FIELDS:
        if f in response:
            return False, (
                f"cross-agent contamination: {f!r} belongs to another worker"
            )
    summary = response.get("intake_summary")
    if not isinstance(summary, dict):
        return False, "intake_summary must be an object"
    extra_keys = set(summary.keys()) - _INTAKE_KEYS
    if extra_keys:
        return False, (
            f"intake_summary has unexpected keys: {sorted(extra_keys)}"
        )
    if not isinstance(response["missing_required_inputs"], list):
        return False, "missing_required_inputs must be a list"
    if not all(isinstance(s, str) for s in response["missing_required_inputs"]):
        return False, "missing_required_inputs entries must be strings"
    if not isinstance(response["data_quality_warnings"], list):
        return False, "data_quality_warnings must be a list"
    if not all(isinstance(s, str) for s in response["data_quality_warnings"]):
        return False, "data_quality_warnings entries must be strings"
    if response["sources"] != []:
        return False, (
            "intake_validator must emit empty sources; it does not "
            "retrieve evidence"
        )
    return True, ""
