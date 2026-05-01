"""Validate risk_scorer output shape + groundedness constraint.

Every factor MUST cite at least one source -- via ``citation_indices``
into the upstream evidence pack OR via ``supplemental_citations`` the
agent fetched directly from the FoundryIQ knowledge tool. The workflow
threads ``_evidence_pack_size`` (an int) into the response before
calling this validator so we can bound-check ``citation_indices``.
"""
from __future__ import annotations

from typing import Any

from src.accelerator_baseline.citations import (
    assert_no_hallucinated_urls,
    require_citations,
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "risk_scorecard",
    "unresolved_questions",
    "sources",
)

FORBIDDEN_FIELDS: tuple[str, ...] = (
    "intake_summary",
    "missing_required_inputs",
    "evidence_pack",
    "recommended_next_actions",
    "tool_previews",
    "executive_summary",
)

_VALID_RISK_LEVELS: frozenset[str] = frozenset({
    "low", "medium", "high", "critical",
})
_VALID_CONFIDENCE: frozenset[str] = frozenset({"low", "medium", "high"})
_VALID_SOURCE_SYSTEMS: frozenset[str] = frozenset({
    "sharepoint",
    "azure_sql",
    "dynamics_365_finance",
    "servicenow",
    "blob_storage",
})


def _validate_factor(
    factor: Any, idx: int, *, evidence_pack_size: int | None,
) -> tuple[bool, str]:
    if not isinstance(factor, dict):
        return False, f"factors[{idx}] must be an object"
    for key in ("factor", "rationale", "policy_reference"):
        v = factor.get(key)
        if not isinstance(v, str) or not v.strip():
            return False, f"factors[{idx}].{key} must be a non-empty string"
    if factor.get("severity") not in _VALID_RISK_LEVELS:
        return False, (
            f"factors[{idx}].severity invalid: "
            f"{factor.get('severity')!r}"
        )
    indices = factor.get("citation_indices")
    if not isinstance(indices, list) or not all(
        isinstance(i, int) and not isinstance(i, bool) and i >= 0
        for i in indices
    ):
        return False, (
            f"factors[{idx}].citation_indices must be a list of "
            "non-negative integers"
        )
    if evidence_pack_size is not None:
        for i in indices:
            if i >= evidence_pack_size:
                return False, (
                    f"factors[{idx}].citation_indices contains {i} but "
                    f"evidence_pack has only {evidence_pack_size} items"
                )
    supplemental = factor.get("supplemental_citations")
    if not isinstance(supplemental, list):
        return False, (
            f"factors[{idx}].supplemental_citations must be a list"
        )
    for s_idx, s in enumerate(supplemental):
        if not (
            isinstance(s, dict)
            and s.get("source_system") in _VALID_SOURCE_SYSTEMS
            and isinstance(s.get("source"), str)
            and s["source"].strip()
        ):
            return False, (
                f"factors[{idx}].supplemental_citations[{s_idx}] must "
                "be {source_system, source} with a valid source_system"
            )
    if not indices and not supplemental:
        return False, (
            f"factors[{idx}] must cite at least one source via "
            "citation_indices or supplemental_citations"
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

    sc = response["risk_scorecard"]
    if not isinstance(sc, dict):
        return False, "risk_scorecard must be an object"
    if sc.get("overall_risk_level") not in _VALID_RISK_LEVELS:
        return False, (
            f"risk_scorecard.overall_risk_level invalid: "
            f"{sc.get('overall_risk_level')!r}"
        )
    if sc.get("confidence") not in _VALID_CONFIDENCE:
        return False, (
            f"risk_scorecard.confidence invalid: "
            f"{sc.get('confidence')!r}"
        )
    if not isinstance(sc.get("policy_matrix_match"), bool):
        return False, "risk_scorecard.policy_matrix_match must be a boolean"
    factors = sc.get("factors")
    if not isinstance(factors, list):
        return False, "risk_scorecard.factors must be a list"
    if not factors:
        return False, "risk_scorecard.factors must not be empty"

    ev_size = response.get("_evidence_pack_size")
    if not isinstance(ev_size, int) or isinstance(ev_size, bool):
        ev_size = None
    for i, factor in enumerate(factors):
        ok, msg = _validate_factor(
            factor, i, evidence_pack_size=ev_size,
        )
        if not ok:
            return False, msg

    questions = response["unresolved_questions"]
    if not isinstance(questions, list) or not all(
        isinstance(q, str) for q in questions
    ):
        return False, "unresolved_questions must be a list of strings"

    sources = response["sources"]
    if not isinstance(sources, list):
        return False, "sources must be a list"
    for s in sources:
        if not (
            isinstance(s, dict)
            and s.get("source_system") in _VALID_SOURCE_SYSTEMS
            and isinstance(s.get("source"), str)
        ):
            return False, (
                "each sources entry must be {source_system, source} "
                "with a valid source_system"
            )

    # Citation contract: factors are populated -> sources must be too.
    ok, msg = require_citations(
        response,
        when_fields_present=("risk_scorecard",),
        field="sources",
    )
    if not ok:
        return False, msg

    # Hallucination check on supplemental citations only (citation_indices
    # were bound-checked above against the trusted upstream pack).
    retrieved = response.get("_retrieved_uris", []) or []
    supplemental_urls: list[dict[str, str]] = []
    for factor in factors:
        for s in factor.get("supplemental_citations", []):
            supplemental_urls.append({"url": s.get("source", "")})
    ok, msg = assert_no_hallucinated_urls(supplemental_urls, retrieved)
    if not ok:
        return False, msg
    return True, ""
