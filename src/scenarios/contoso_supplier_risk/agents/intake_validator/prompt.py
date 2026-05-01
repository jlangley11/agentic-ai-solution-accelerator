"""intake_validator prompt builder - pure function, no side effects.

Capability: Validate the supplier review intake and list any missing
required inputs.

System instructions live in
``docs/agent-specs/accel-contoso-supplier-risk-intake-validator.md`` and
are synced to Foundry by ``src/bootstrap.py``; this module only builds
the per-request input message.
"""
from __future__ import annotations

from typing import Any


def build_prompt(request_data: dict[str, Any]) -> str:
    """Build the intake_validator's per-request input.

    ``request_data`` is the dict produced by ``_build_input_intake_validator``
    in ``workflow.py`` -- it carries the original analyst request under the
    ``request`` key.
    """
    req = request_data.get("request", {})
    return (
        "Validate the supplier review intake below. Echo the canonical "
        "fields back, list any missing required inputs, and surface "
        "non-blocking data-quality warnings.\n\n"
        "Required fields the analyst must provide:\n"
        "- supplier_name (non-empty string)\n"
        "- supplier_id (non-empty string)\n"
        "- review_reason (one of: onboarding, renewal, spend_increase, "
        "country_risk_change, policy_exception)\n"
        "- category (procurement category)\n"
        "- country (operating country)\n"
        "- annual_spend_usd (number > 0 unless review_reason is "
        "policy_exception)\n"
        "- due_date (ISO date in the future)\n"
        "- requested_by (non-empty string)\n"
        "evidence_packet_uri is OPTIONAL and may be null.\n\n"
        f"Intake:\n{req}\n\n"
        "Return strict JSON with EXACTLY these keys:\n"
        "- intake_summary: object echoing supplier_name, supplier_id, "
        "review_reason, category, country, annual_spend_usd, due_date, "
        "requested_by, evidence_packet_uri\n"
        "- missing_required_inputs: array of field names (strings); "
        "empty when the request is ready\n"
        "- data_quality_warnings: array of <=3 single-sentence "
        "warnings; empty when nothing to flag\n"
        "- sources: empty array (this worker does not retrieve evidence)"
    )
