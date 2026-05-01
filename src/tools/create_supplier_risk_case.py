"""Create a draft procurement-risk case in ServiceNow. HITL-gated.

Side-effect contract:
- declare JSON schema in ``SCHEMA``
- call ``hitl.checkpoint`` BEFORE any network write
- emit ``tool.executed`` with success/failure

Partner integration:
- replace the stub HTTP body with the customer's ServiceNow API call.
- the case is created in DRAFT state so a closer can void it before
  workflow execution; this preserves the brief's "Reversible: yes"
  posture in solution-brief.md Section 5.
"""
from __future__ import annotations

from typing import Any

from ..accelerator_baseline.hitl import checkpoint
from ..accelerator_baseline.killswitch import assert_enabled
from ..accelerator_baseline.telemetry import Event, emit_event

TOOL_NAME = "create_supplier_risk_case"
HITL_POLICY = "always"  # writes to system of record

SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Create a draft procurement-risk case in the ServiceNow procurement-"
        "risk workspace with cited evidence and a recommended next action. "
        "Requires human approval before execution."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "supplier_id": {"type": "string"},
            "supplier_name": {"type": "string"},
            "review_reason": {"type": "string"},
            "category": {"type": "string"},
            "country": {"type": "string"},
            "annual_spend_usd": {"type": "number"},
            "due_date": {"type": "string"},
            "requested_by": {"type": "string"},
            "recommendation_summary": {"type": "string"},
            "overall_risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
            },
            "confidence": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_system": {"type": "string"},
                        "source": {"type": "string"},
                    },
                    "required": ["source_system", "source"],
                },
            },
        },
        "required": [
            "supplier_id",
            "supplier_name",
            "review_reason",
            "recommendation_summary",
            "overall_risk_level",
            "confidence",
            "citations",
        ],
    },
}


async def create_supplier_risk_case(**args: Any) -> dict[str, Any]:
    assert_enabled("tools")
    await checkpoint(tool=TOOL_NAME, args=args, policy=HITL_POLICY)
    # Partner: replace with the actual ServiceNow Table API call
    # (POST /api/now/table/u_procurement_risk_case) using the
    # workspace's OAuth client credentials referenced from Key Vault.
    case_id = f"stub-PRR-{args['supplier_id']}"
    result = {"ok": True, "case_id": case_id, "state": "draft"}
    emit_event(Event(
        name="tool.executed",
        args_redacted={
            "supplier_id": args["supplier_id"],
            "review_reason": args["review_reason"],
            "overall_risk_level": args["overall_risk_level"],
            "case_id": case_id,
        },
        external_system=TOOL_NAME,
        ok=True,
    ))
    return result
