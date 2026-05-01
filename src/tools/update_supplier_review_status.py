"""Update Dynamics 365 Finance supplier onboarding notes. HITL-gated.

Side-effect contract:
- declare JSON schema in ``SCHEMA``
- call ``hitl.checkpoint`` BEFORE any network write
- emit ``tool.executed`` with success/failure

Partner integration:
- replace the stub HTTP body with the customer's Dynamics 365 Finance
  data entity write (PATCH on the supplier onboarding note entity).
- the brief flags this as "Reversible: yes" because the entity is
  audited and a corrected note can supersede a prior one. Bypassing the
  HITL gate is forbidden per solution-brief.md Section 6 RAI risk #4.
"""
from __future__ import annotations

from typing import Any

from ..accelerator_baseline.hitl import checkpoint
from ..accelerator_baseline.killswitch import assert_enabled
from ..accelerator_baseline.telemetry import Event, emit_event

TOOL_NAME = "update_supplier_review_status"
HITL_POLICY = "always"  # writes to system of record (Dynamics 365 Finance)

SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Write the approved recommendation, confidence, and evidence "
        "summary to the supplier onboarding notes in Dynamics 365 "
        "Finance. Requires human approval before execution."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "supplier_id": {"type": "string"},
            "review_status": {
                "type": "string",
                "enum": [
                    "ready_for_category_manager",
                    "blocked_pending_evidence",
                    "blocked_pending_policy_review",
                ],
            },
            "recommendation_summary": {"type": "string"},
            "evidence_summary": {"type": "string"},
            "overall_risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
            },
            "confidence": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "servicenow_case_id": {"type": "string"},
            "approved_by": {"type": "string"},
        },
        "required": [
            "supplier_id",
            "review_status",
            "recommendation_summary",
            "evidence_summary",
            "overall_risk_level",
            "confidence",
            "approved_by",
        ],
    },
}


async def update_supplier_review_status(**args: Any) -> dict[str, Any]:
    assert_enabled("tools")
    await checkpoint(tool=TOOL_NAME, args=args, policy=HITL_POLICY)
    # Partner: replace with the actual Dynamics 365 Finance OData call
    # (PATCH /data/VendorOnboardingNotes(SupplierId='...')) using the
    # service principal referenced from Key Vault.
    note_id = f"stub-D365N-{args['supplier_id']}"
    result = {"ok": True, "note_id": note_id, "state": "written"}
    emit_event(Event(
        name="tool.executed",
        args_redacted={
            "supplier_id": args["supplier_id"],
            "review_status": args["review_status"],
            "overall_risk_level": args["overall_risk_level"],
            "note_id": note_id,
        },
        external_system=TOOL_NAME,
        ok=True,
    ))
    return result
