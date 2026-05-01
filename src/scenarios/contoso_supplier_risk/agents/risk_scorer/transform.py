"""Normalise risk_scorer output to the canonical dict shape.

Coerces enums into closed vocabularies and trims/dedupes citations so
the supervisor and case_drafter consume a consistent shape.
"""
from __future__ import annotations

import json
from typing import Any

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


def _coerce_enum(
    raw: Any, valid: frozenset[str], default: str,
) -> str:
    if not isinstance(raw, str):
        return default
    cleaned = raw.strip().lower()
    return cleaned if cleaned in valid else default


def _coerce_supplemental(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ss = item.get("source_system")
        src = item.get("source")
        if (
            isinstance(ss, str) and ss in _VALID_SOURCE_SYSTEMS
            and isinstance(src, str) and src.strip()
        ):
            out.append({"source_system": ss, "source": src.strip()})
    return out


def _coerce_factor(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    factor = item.get("factor")
    rationale = item.get("rationale")
    policy_ref = item.get("policy_reference")
    if not (isinstance(factor, str) and factor.strip()):
        return None
    if not (isinstance(rationale, str) and rationale.strip()):
        return None
    if not (isinstance(policy_ref, str) and policy_ref.strip()):
        return None
    severity = _coerce_enum(item.get("severity"), _VALID_RISK_LEVELS, "low")
    indices_raw = item.get("citation_indices") or []
    indices: list[int] = []
    if isinstance(indices_raw, list):
        for idx in indices_raw:
            if isinstance(idx, bool):
                # bool subclasses int in Python -- exclude explicitly.
                continue
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    supplemental = _coerce_supplemental(item.get("supplemental_citations"))
    return {
        "factor": factor.strip(),
        "severity": severity,
        "rationale": rationale.strip(),
        "policy_reference": policy_ref.strip(),
        "citation_indices": indices,
        "supplemental_citations": supplemental,
    }


def _dedupe_sources(
    sources: list[dict[str, Any]],
) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        ss = s.get("source_system")
        src = s.get("source")
        if not (isinstance(ss, str) and isinstance(src, str)):
            continue
        key = (ss, src)
        if key in seen:
            continue
        seen.add(key)
        out.append({"source_system": ss, "source": src})
    return out


def transform_response(response: str | dict[str, Any]) -> dict[str, Any]:
    data = _parse(response)
    sc_raw = data.get("risk_scorecard") or {}
    if not isinstance(sc_raw, dict):
        sc_raw = {}
    factors_raw = sc_raw.get("factors") or []
    factors: list[dict[str, Any]] = []
    if isinstance(factors_raw, list):
        for item in factors_raw[:6]:
            coerced = _coerce_factor(item)
            if coerced is not None:
                factors.append(coerced)
    risk_scorecard = {
        "overall_risk_level": _coerce_enum(
            sc_raw.get("overall_risk_level"), _VALID_RISK_LEVELS, "high",
        ),
        "confidence": _coerce_enum(
            sc_raw.get("confidence"), _VALID_CONFIDENCE, "low",
        ),
        "factors": factors,
        "policy_matrix_match": bool(sc_raw.get("policy_matrix_match")),
    }
    questions_raw = data.get("unresolved_questions") or []
    questions = [
        s.strip() for s in questions_raw
        if isinstance(s, str) and s.strip()
    ][:4]
    sources = _dedupe_sources(data.get("sources") or [])
    return {
        "risk_scorecard": risk_scorecard,
        "unresolved_questions": questions,
        "sources": sources,
    }
