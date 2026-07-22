"""Request schema for the Sales Research & Outreach scenario.

Resolved at startup by :func:`src.workflow.registry.load_scenario` via the
``scenario.request_schema`` entry in ``accelerator.yaml``.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    company_name: str
    domain: str = ""
    seller_intent: str = Field(
        ..., description="What the seller wants from this account"
    )
    persona: str = "Decision maker"
    icp_definition: str
    our_solution: str
    context_hints: list[str] = Field(default_factory=list)


class ResearchBriefing(BaseModel):
    """Validated final response contract exposed to generated clients."""

    executive_summary: list[str] = Field(default_factory=list)
    account_profile: dict[str, Any] = Field(default_factory=dict)
    icp_fit: dict[str, Any] = Field(default_factory=dict)
    competitive_play: dict[str, Any] = Field(default_factory=dict)
    recommended_outreach: dict[str, Any] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)
    requires_approval: list[str] = Field(default_factory=list)
    tool_args: dict[str, dict[str, Any]] = Field(default_factory=dict)
    usage: dict[str, int] | None = None
