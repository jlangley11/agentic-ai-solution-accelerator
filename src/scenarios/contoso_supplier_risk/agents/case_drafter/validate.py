"""Validate case_drafter output shape, allow-list, and PII guards.

The brief Section 6 RAI guards that depend on upstream worker state
(``missing_required_inputs`` from intake_validator;
``policy_matrix_match`` from risk_scorer) live in the workflow's
:meth:`ContosoSupplierRiskWorkflow._aggregate` -- the canonical
enforcement point that runs after every worker has completed and
BEFORE any side-effect tool is queued. Re-implementing the same
checks here is unsafe because the supervisor DAG calls
``validate_response`` with only the case_drafter's own parsed
output (plus the auto-injected ``_retrieved_uris`` from the Foundry
tool trace); upstream worker state is not visible at that point.

This validator therefore covers ONLY:

* shape -- required fields present, list/dict types correct;
* allow-list -- ``tool_previews`` keys must be in
  ``ALLOWED_TOOLS``;
* PII guard -- analyst-facing prose must not contain email- or
  phone-shaped strings (brief Section 6 RAI risk #3).
"""
from __future__ import annotations

import re
from typing import Any

REQUIRED_FIELDS: tuple[str, ...] = (
    "recommended_next_actions",
    "recommendation_summary",
    "hitl_decision_prompt",
    "tool_previews",
    "sources",
)

FORBIDDEN_FIELDS: tuple[str, ...] = (
    "intake_summary",
    "missing_required_inputs",
    "evidence_pack",
    "risk_scorecard",
    "executive_summary",
)

ALLOWED_TOOLS: frozenset[str] = frozenset({
    "create_supplier_risk_case",
    "update_supplier_review_status",
})

_VALID_SOURCE_SYSTEMS: frozenset[str] = frozenset({
    "sharepoint",
    "azure_sql",
    "dynamics_365_finance",
    "servicenow",
    "blob_storage",
})

# Heuristic PII guards (brief Section 6 RAI risk #3: leak supplier
# contact details). Kept lightweight so unit-test fixtures don't have
# to dance around them; the redteam pii-leak case exercises real LLM
# behaviour.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"(?:(?<!\d)\+?\d[\d \-().]{7,}\d(?!\d))")


def _pii_in(text: str) -> str | None:
    if _EMAIL_RE.search(text):
        return "email-shaped string"
    if _PHONE_RE.search(text):
        return "phone-shaped string"
    return None


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

    actions = response["recommended_next_actions"]
    if not isinstance(actions, list):
        return False, "recommended_next_actions must be a list"
    if len(actions) != 3:
        return False, (
            f"recommended_next_actions must have exactly 3 entries; "
            f"got {len(actions)}"
        )
    if not all(isinstance(a, str) and a.strip() for a in actions):
        return False, (
            "recommended_next_actions entries must be non-empty strings"
        )

    summary = response["recommendation_summary"]
    if not isinstance(summary, str) or not summary.strip():
        return False, "recommendation_summary must be a non-empty string"

    decision_prompt = response["hitl_decision_prompt"]
    if not isinstance(decision_prompt, str) or not decision_prompt.strip():
        return False, "hitl_decision_prompt must be a non-empty string"

    tool_previews = response["tool_previews"]
    if not isinstance(tool_previews, dict):
        return False, "tool_previews must be an object"
    for tool_name, kwargs in tool_previews.items():
        if tool_name not in ALLOWED_TOOLS:
            return False, (
                f"tool_previews has tool {tool_name!r} not in the "
                f"allow-list {sorted(ALLOWED_TOOLS)}"
            )
        if not isinstance(kwargs, dict):
            return False, (
                f"tool_previews[{tool_name!r}] kwargs must be an object"
            )

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

    # PII guards: scan the analyst-facing prose fields. The
    # tool_previews kwargs are allowed to carry the analyst's own
    # ``requested_by`` email since that is system metadata, so we
    # exclude tool_previews from the PII scan.
    for field, text in (
        ("recommendation_summary", summary),
        ("hitl_decision_prompt", decision_prompt),
        *(
            (f"recommended_next_actions[{i}]", a)
            for i, a in enumerate(actions)
        ),
    ):
        hit = _pii_in(text)
        if hit:
            return False, (
                f"{field} contains a {hit}; supplier contact details are "
                "not allowed in analyst-facing fields"
            )
    return True, ""
