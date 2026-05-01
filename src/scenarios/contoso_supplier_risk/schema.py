"""Request schema for the contoso-supplier-risk scenario.

Mirrors the UX inputs in ``docs/discovery/solution-brief.md`` Section 5c
(Structured form + report). Resolved at startup by
:func:`src.workflow.registry.load_scenario` via the
``scenario.request_schema`` entry in ``accelerator.yaml``.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

# Closed allow-lists keep the analyst form deterministic and prevent
# free-text drift into the category-risk matrix and review-reason logic.
ReviewReason = Literal[
    "onboarding",
    "renewal",
    "spend_increase",
    "country_risk_change",
    "policy_exception",
]

ProcurementCategory = Literal[
    "raw_materials",
    "components",
    "capital_equipment",
    "logistics",
    "professional_services",
    "it_services",
    "facilities",
    "marketing",
    "other",
]


class ScenarioRequest(BaseModel):
    """Supplier review intake submitted by a procurement risk analyst.

    Field set is locked to brief Section 5c. Adding a field here means
    extending the analyst UI and the intake_validator's required-field
    check; do not silently widen the contract.
    """

    supplier_name: str = Field(
        ..., description="Display name of the supplier under review."
    )
    supplier_id: str = Field(
        ...,
        description=(
            "Contoso supplier master identifier from Dynamics 365 "
            "Finance."
        ),
    )
    review_reason: ReviewReason = Field(
        ..., description="Why this supplier review was triggered."
    )
    category: ProcurementCategory = Field(
        ...,
        description=(
            "Procurement category used to apply the category-risk matrix."
        ),
    )
    country: str = Field(
        ...,
        description="Supplier operating country or primary risk jurisdiction.",
    )
    annual_spend_usd: float = Field(
        ..., ge=0,
        description="Expected or current annual spend in USD.",
    )
    due_date: date = Field(
        ...,
        description=(
            "Date by which Procurement Operations needs the recommendation."
        ),
    )
    requested_by: str = Field(
        ...,
        description="Analyst or category manager requesting the review.",
    )
    evidence_packet_uri: str | None = Field(
        default=None,
        description=(
            "Optional URI for uploaded supplier documents or intake "
            "attachments."
        ),
    )
