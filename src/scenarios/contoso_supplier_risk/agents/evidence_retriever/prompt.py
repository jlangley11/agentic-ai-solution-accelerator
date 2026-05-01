"""evidence_retriever prompt builder - pure function, no side effects.

Capability: Retrieve cited evidence from approved Contoso sources for
the supplier under review.

System instructions live in
``docs/agent-specs/accel-contoso-supplier-risk-evidence-retriever.md``
and are synced to Foundry by ``src/bootstrap.py``. The agent has a
FoundryIQ knowledge tool attached to the ``supplier_evidence`` index
(declared in ``accelerator.yaml``); this module only builds the
per-request input message.
"""
from __future__ import annotations

import json
from typing import Any


def _compact(raw: Any, *, max_items: int = 5, max_str: int = 240) -> str:
    """Compress an upstream worker output for prompt re-use."""
    if raw is None:
        return "{}"
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return str(raw)[:600]
    if not isinstance(data, dict):
        return str(data)[:600]

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
    """Build the evidence_retriever's per-request input.

    ``request_data`` is the dict produced by ``_build_input_evidence_retriever``
    in ``workflow.py`` -- it carries ``intake_validator`` (upstream output)
    and ``request`` (the original analyst request).
    """
    intake = _compact(request_data.get("intake_validator"))
    req = request_data.get("request", {})
    return (
        "Retrieve cited evidence from the supplier_evidence FoundryIQ "
        "Knowledge Base for the supplier under review. Use the knowledge "
        "tool exposed to you; do NOT reach out to the public web or any "
        "unsanctioned third-party API.\n\n"
        f"Supplier under review:\n"
        f"- supplier_name: {req.get('supplier_name')}\n"
        f"- supplier_id: {req.get('supplier_id')}\n"
        f"- review_reason: {req.get('review_reason')}\n"
        f"- category: {req.get('category')}\n"
        f"- country: {req.get('country')}\n"
        f"- annual_spend_usd: {req.get('annual_spend_usd')}\n"
        f"- evidence_packet_uri: "
        f"{req.get('evidence_packet_uri') or '(none)'}\n\n"
        f"Validated intake (from intake_validator):\n{intake}\n\n"
        "Issue queries to the knowledge tool that are scoped to this "
        "supplier and category. Filter by supplier_id, category, country "
        "when the index supports it. Prefer the SharePoint policy library "
        "and the Azure SQL supplier master record over older onboarding "
        "history.\n\n"
        "Return strict JSON with EXACTLY these keys:\n"
        "- evidence_pack: array of 4-8 items, each {summary, source, "
        "source_system, supplier_id?, category?, country?, "
        "retrieved_at}. summary must be one or two sentences (<= 30 "
        "words verbatim from any source). source_system is one of: "
        "sharepoint, azure_sql, dynamics_365_finance, servicenow, "
        "blob_storage.\n"
        "- coverage_gaps: array of <=5 single-sentence statements about "
        "expected evidence the tool did not return (e.g. \"no SOC 2 "
        "attestation in SharePoint within the last 24 months\").\n"
        "- sources: array of {source_system, source} objects, one per "
        "evidence_pack entry, deduplicated.\n\n"
        "BREVITY: Each summary <= 2 sentences. Never invent a citation; "
        "if you cannot find supporting evidence, list the gap in "
        "coverage_gaps and return fewer items. Never include supplier "
        "contact details (names, emails, phone numbers) in summary text."
    )
