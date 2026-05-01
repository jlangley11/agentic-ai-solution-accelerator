"""Validate evidence_retriever output shape + groundedness constraint.

The evidence_retriever is the primary RAG worker for the
supplier-risk scenario, so the validator is strict about citations and
about hallucinated URLs (cross-checked against the Foundry tool trace
populated by the workflow).
"""
from __future__ import annotations

from typing import Any

from src.accelerator_baseline.citations import (
    assert_no_hallucinated_urls,
    require_citations,
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "evidence_pack",
    "coverage_gaps",
    "sources",
)

FORBIDDEN_FIELDS: tuple[str, ...] = (
    "intake_summary",
    "missing_required_inputs",
    "risk_scorecard",
    "recommended_next_actions",
    "tool_previews",
    "executive_summary",
)

_VALID_SOURCE_SYSTEMS: frozenset[str] = frozenset({
    "sharepoint",
    "azure_sql",
    "dynamics_365_finance",
    "servicenow",
    "blob_storage",
})


def _is_evidence_item(item: Any) -> tuple[bool, str]:
    if not isinstance(item, dict):
        return False, "evidence_pack entries must be objects"
    for f in ("summary", "source", "source_system"):
        v = item.get(f)
        if not isinstance(v, str) or not v.strip():
            return False, f"evidence_pack item missing required field: {f}"
    if item["source_system"] not in _VALID_SOURCE_SYSTEMS:
        return False, (
            f"evidence_pack item has invalid source_system: "
            f"{item['source_system']!r} "
            f"(must be one of {sorted(_VALID_SOURCE_SYSTEMS)})"
        )
    return True, ""


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

    pack = response["evidence_pack"]
    if not isinstance(pack, list):
        return False, "evidence_pack must be a list"
    for item in pack:
        ok, msg = _is_evidence_item(item)
        if not ok:
            return False, msg

    gaps = response["coverage_gaps"]
    if not isinstance(gaps, list) or not all(
        isinstance(s, str) for s in gaps
    ):
        return False, "coverage_gaps must be a list of strings"

    # If the agent returned at least one evidence item, sources must be
    # non-empty (the citation contract for this worker). Empty pack +
    # empty sources is OK provided coverage_gaps explains why.
    ok, msg = require_citations(
        response, when_fields_present=("evidence_pack",), field="sources",
    )
    if not ok:
        return False, msg
    if not pack and not gaps:
        return False, (
            "evidence_pack is empty but coverage_gaps does not explain "
            "why -- partner must list missing sources"
        )

    sources = response["sources"]
    if not isinstance(sources, list):
        return False, "sources must be a list"
    for s in sources:
        if not (
            isinstance(s, dict)
            and isinstance(s.get("source_system"), str)
            and isinstance(s.get("source"), str)
        ):
            return False, (
                "each sources entry must be {source_system, source}"
            )

    # Foundry tool-trace groundedness: when the workflow stamps
    # ``_retrieved_uris`` onto the response, reject any cited URL whose
    # host wasn't actually retrieved. Fails open on empty trace -- unit
    # tests + ungrounded scenarios don't break.
    retrieved = response.get("_retrieved_uris", []) or []
    citation_objs = [
        {"url": s.get("source")}
        for s in sources if isinstance(s, dict)
    ]
    ok, msg = assert_no_hallucinated_urls(citation_objs, retrieved)
    if not ok:
        return False, msg
    return True, ""
