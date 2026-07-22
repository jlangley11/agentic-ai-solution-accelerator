from __future__ import annotations

from typing import Any

from src.accelerator_baseline.citations import assert_no_hallucinated_urls

REQUIRED = ("competitors", "differentiators", "likely_objections",
            "talking_points", "cloud_footprint_signals", "competitor_refs")
FORBIDDEN = ("fit_score", "outreach_subject", "company_overview")
VALID_STANCES = {"incumbent", "challenger", "evaluator", "absent", "unknown"}
VALID_PROVIDERS = {"aws", "gcp", "azure", "oci", "other"}


def validate_response(response: dict[str, Any]) -> tuple[bool, str]:
    for f in REQUIRED:
        if f not in response:
            return False, f"missing field: {f}"
    for f in FORBIDDEN:
        if f in response:
            return False, f"cross-agent contamination: {f}"
    if not isinstance(response["competitors"], list):
        return False, "competitors must be a list"
    for c in response["competitors"]:
        if not isinstance(c, dict) or "name" not in c:
            return False, "each competitor must be {name, stance, evidence, evidence_urls}"
        if c.get("stance") not in VALID_STANCES:
            return False, f"competitor {c.get('name')!r} has invalid stance: {c.get('stance')!r}"
        urls = c.get("evidence_urls", [])
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            return False, f"competitor {c.get('name')!r} has invalid evidence_urls"
    if not isinstance(response["cloud_footprint_signals"], list):
        return False, "cloud_footprint_signals must be a list"
    for s in response["cloud_footprint_signals"]:
        if not isinstance(s, dict):
            return False, "each cloud_footprint_signal must be an object"
        if s.get("provider") not in VALID_PROVIDERS:
            return False, f"invalid cloud provider: {s.get('provider')!r}"
        if not isinstance(s.get("workload_signal"), str) or not s["workload_signal"].strip():
            return False, "cloud_footprint_signal.workload_signal required"
        evidence_url = s.get("evidence_url")
        if evidence_url is not None and not isinstance(evidence_url, str):
            return False, "cloud_footprint_signal.evidence_url must be a string"
    if not isinstance(response["competitor_refs"], list):
        return False, "competitor_refs must be a list"
    if not all(isinstance(b, str) for b in response["competitor_refs"]):
        return False, "competitor_refs must be strings"
    evidence_urls = [
        url
        for competitor in response["competitors"]
        if isinstance(competitor, dict)
        for url in competitor.get("evidence_urls", [])
        if isinstance(url, str) and url
    ]
    evidence_urls.extend(
        signal["evidence_url"]
        for signal in response["cloud_footprint_signals"]
        if isinstance(signal, dict)
        and isinstance(signal.get("evidence_url"), str)
        and signal["evidence_url"]
    )
    if response["competitors"] and not evidence_urls:
        return False, "groundedness violation: competitors require evidence URLs"
    ok, message = assert_no_hallucinated_urls(
        [{"url": url} for url in evidence_urls],
        response.get("_retrieved_uris", []) or [],
    )
    if not ok:
        return False, message
    return True, ""
