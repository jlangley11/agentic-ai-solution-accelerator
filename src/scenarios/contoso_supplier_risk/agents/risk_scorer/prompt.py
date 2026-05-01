"""risk_scorer prompt builder - pure function, no side effects.

Capability: Score supplier risk factors with rationale and policy
references.

System instructions live in
``docs/agent-specs/accel-contoso-supplier-risk-risk-scorer.md`` and are
synced to Foundry by ``src/bootstrap.py``. The agent has a FoundryIQ
knowledge tool attached to the ``supplier-evidence`` index (top_k=3,
declared in ``accelerator.yaml``); this module only builds the
per-request input message.
"""
from __future__ import annotations

import json
from typing import Any


def _compact(raw: Any, *, max_items: int = 8, max_str: int = 320) -> str:
    """Compress upstream worker output to bound prompt tokens."""
    if raw is None:
        return "{}"
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return str(raw)[:1200]
    if not isinstance(data, dict):
        return str(data)[:1200]

    def _cv(v: Any) -> Any:
        if isinstance(v, str) and len(v) > max_str:
            return v[:max_str] + "..."
        if isinstance(v, list):
            trunc = v[:max_items]
            if all(isinstance(x, dict) for x in trunc):
                return [{kk: _cv(vv) for kk, vv in x.items()} for x in trunc]
            return trunc
        if isinstance(v, dict):
            return {kk: _cv(vv) for kk, vv in v.items()}
        return v

    return json.dumps({k: _cv(v) for k, v in data.items()}, default=str)


def build_prompt(request_data: dict[str, Any]) -> str:
    """Build the risk_scorer's per-request input.

    ``request_data`` is the dict produced by ``_build_input_risk_scorer``
    in ``workflow.py`` -- it carries ``intake_validator`` and
    ``evidence_retriever`` (upstream outputs) and ``request`` (the
    original analyst request).
    """
    intake = _compact(request_data.get("intake_validator"))
    evidence = _compact(request_data.get("evidence_retriever"))
    req = request_data.get("request", {})
    return (
        "Score supplier risk for the supplier under review. Use the "
        "evidence pack below as your primary input. Use the knowledge "
        "tool sparingly -- only to confirm the SharePoint category-risk "
        "matrix applies, to pull a precise policy_reference string, or "
        "to verify SOX Control PR-04 is in force. Do NOT run breadth "
        "searches; that is the evidence_retriever's job.\n\n"
        f"Supplier under review:\n"
        f"- supplier_id: {req.get('supplier_id')}\n"
        f"- category: {req.get('category')}\n"
        f"- country: {req.get('country')}\n"
        f"- annual_spend_usd: {req.get('annual_spend_usd')}\n"
        f"- review_reason: {req.get('review_reason')}\n\n"
        f"Validated intake (from intake_validator):\n{intake}\n\n"
        f"Evidence pack (from evidence_retriever):\n{evidence}\n\n"
        "Return strict JSON with EXACTLY these keys:\n"
        "- risk_scorecard: object with\n"
        "    - overall_risk_level: low | medium | high | critical\n"
        "    - confidence: low | medium | high\n"
        "    - factors: array of <=6 entries, each {factor (1 sentence), "
        "severity (low|medium|high|critical), rationale (<=2 sentences), "
        "policy_reference (string), citation_indices (array of 0-based "
        "ints into the evidence_pack), supplemental_citations (array of "
        "{source_system, source} you fetched directly via the knowledge "
        "tool; leave empty when the upstream pack already cites it)}\n"
        "    - policy_matrix_match: boolean\n"
        "- unresolved_questions: array of <=4 single-sentence questions\n"
        "- sources: array of {source_system, source} covering EVERY "
        "citation actually used in factors (both citation_indices "
        "resolved to evidence-pack sources AND any "
        "supplemental_citations), deduplicated.\n\n"
        "BREVITY: Keep rationale tight. Every factor MUST cite at least "
        "one source via citation_indices or supplemental_citations -- "
        "uncited factors are rejected. Set policy_matrix_match=false "
        "ONLY when the matrix could not be located or you must deviate; "
        "explain why in unresolved_questions. Never recommend approval "
        "language; you only score. Never include supplier-facing "
        "messaging."
    )
