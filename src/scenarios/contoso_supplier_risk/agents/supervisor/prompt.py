"""Supervisor prompt builder - pure function, no side effects.

Builds the per-request input message for the supplier-risk supervisor.
System instructions live in
``docs/agent-specs/accel-contoso-supplier-risk-supervisor.md`` and are
synced to Foundry by ``src/bootstrap.py``; do NOT add agent role / output
contract content here.
"""
from __future__ import annotations

from typing import Any


def build_prompt(request: dict[str, Any]) -> str:
    """Build the supervisor's per-request input.

    The five report sections (Intake Summary, Evidence Pack, Risk
    Scorecard, Recommended Next Actions, Audit Trail) are merged from
    the workers in code by the workflow aggregator. The supervisor only
    produces the synthesis fields below so the response stays short and
    auditable.
    """
    return (
        "Supplier review intake (analyst-submitted):\n"
        f"- supplier_name: {request['supplier_name']}\n"
        f"- supplier_id: {request['supplier_id']}\n"
        f"- review_reason: {request['review_reason']}\n"
        f"- category: {request['category']}\n"
        f"- country: {request['country']}\n"
        f"- annual_spend_usd: {request['annual_spend_usd']}\n"
        f"- due_date: {request['due_date']}\n"
        f"- requested_by: {request['requested_by']}\n"
        f"- evidence_packet_uri: "
        f"{request.get('evidence_packet_uri') or '(none)'}\n\n"
        "The four worker outputs (intake_summary, evidence_pack, "
        "risk_scorecard, recommended_next_actions) will be carried into "
        "the final report verbatim by the orchestrator -- do NOT echo "
        "them back. Produce ONLY the synthesis fields defined in your "
        "system instructions: executive_summary, audit_trail, "
        "requires_approval, tool_args. Output ONLY a JSON object."
    )
