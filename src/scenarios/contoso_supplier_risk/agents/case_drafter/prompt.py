"""case_drafter prompt builder - pure function, no side effects.

Capability: Draft a recommendation, HITL decision prompt, and
side-effect tool preview.

System instructions live in
``docs/agent-specs/accel-contoso-supplier-risk-case-drafter.md`` and
are synced to Foundry by ``src/bootstrap.py``. This worker has NO
grounding tool attached -- it only reformats upstream output. All
factual claims must be derivable from the intake, evidence_pack, and
risk_scorecard handed in here.
"""
from __future__ import annotations

import json
from typing import Any


def _compact(raw: Any, *, max_items: int = 6, max_str: int = 320) -> str:
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
    """Build the case_drafter's per-request input.

    ``request_data`` is the dict produced by ``_build_input_case_drafter``
    in ``workflow.py`` -- it carries ``intake_validator``,
    ``evidence_retriever``, ``risk_scorer`` (upstream outputs) and
    ``request`` (the original analyst request).
    """
    intake = _compact(request_data.get("intake_validator"))
    evidence = _compact(request_data.get("evidence_retriever"))
    risk = _compact(request_data.get("risk_scorer"))
    req = request_data.get("request", {})
    return (
        "Draft the recommendation, HITL decision prompt, and side-effect "
        "tool previews for this supplier review. Do NOT introduce new "
        "facts -- everything must be derivable from the upstream worker "
        "outputs below.\n\n"
        f"Supplier under review:\n"
        f"- supplier_name: {req.get('supplier_name')}\n"
        f"- supplier_id: {req.get('supplier_id')}\n"
        f"- review_reason: {req.get('review_reason')}\n"
        f"- category: {req.get('category')}\n"
        f"- country: {req.get('country')}\n"
        f"- annual_spend_usd: {req.get('annual_spend_usd')}\n"
        f"- due_date: {req.get('due_date')}\n"
        f"- requested_by: {req.get('requested_by')}\n\n"
        f"Validated intake (from intake_validator):\n{intake}\n\n"
        f"Evidence pack (from evidence_retriever):\n{evidence}\n\n"
        f"Risk scorecard (from risk_scorer):\n{risk}\n\n"
        "Return strict JSON with EXACTLY these keys:\n"
        "- recommended_next_actions: array of EXACTLY 3 prioritized "
        "single-sentence actions for the analyst.\n"
        "- recommendation_summary: 2-3 sentence draft suitable for the "
        "ServiceNow case body and the Dynamics 365 onboarding note. "
        "Reference the evidence indices that support it.\n"
        "- hitl_decision_prompt: single paragraph naming the "
        "recommendation, the confidence level, and the side-effect "
        "tools queued for human approval.\n"
        "- tool_previews: object keyed by tool name. Allowed tool names "
        "(closed allow-list): create_supplier_risk_case, "
        "update_supplier_review_status. Each value is the kwargs object "
        "you would pass. If the upstream blocked tool execution "
        "(missing required inputs OR risk_scorecard.policy_matrix_match "
        "is false), tool_previews MUST be an empty object {}.\n"
        "- sources: array of {source_system, source} objects copied from "
        "the evidence/risk citations actually referenced above; "
        "deduplicated.\n\n"
        "BREVITY: Each next_action <= 1 sentence. Never include "
        "supplier contact details (names, emails, phone numbers), "
        "supplier-facing language, or recommendations that approve / "
        "reject / suspend the supplier directly. You draft for human "
        "approval only."
    )
