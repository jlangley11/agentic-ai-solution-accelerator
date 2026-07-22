from __future__ import annotations

import re
from typing import Any

from src.accelerator_baseline.citations import assert_no_hallucinated_urls

REQUIRED = ("fit_score", "fit_reasons", "fit_risks",
            "recommended_segment", "recommended_action",
            "tier_recommendation", "signal_evidence",
            "nnr_indicators", "data_gaps")
FORBIDDEN = ("company_overview", "competitors", "outreach_subject")
VALID_SEGMENTS = {"enterprise", "mid-market", "smb", "unknown"}
VALID_ACTIONS = {"pursue", "nurture", "disqualify"}
VALID_TIERS = {"tier-1", "tier-2", "tier-3", "watchlist"}
VALID_NNR_LEVELS = {"strong", "moderate", "weak", "unknown"}
NNR_DIMENSIONS = ("size_signal", "growth_signal", "wallet_expansion_signal")
_PROFILE_FIELD_REF = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\[\d+\])?"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[\d+\])?)*$"
)


def validate_response(response: dict[str, Any]) -> tuple[bool, str]:
    for f in REQUIRED:
        if f not in response:
            return False, f"missing field: {f}"
    for f in FORBIDDEN:
        if f in response:
            return False, f"cross-agent contamination: {f}"
    if not (0 <= response["fit_score"] <= 100):
        return False, "fit_score must be in [0,100]"
    if response["recommended_segment"] not in VALID_SEGMENTS:
        return False, f"invalid segment: {response['recommended_segment']}"
    if response["recommended_action"] not in VALID_ACTIONS:
        return False, f"invalid action: {response['recommended_action']}"
    if response["tier_recommendation"] not in VALID_TIERS:
        return False, f"invalid tier: {response['tier_recommendation']}"
    nnr = response["nnr_indicators"]
    if not isinstance(nnr, dict):
        return False, "nnr_indicators must be an object"
    for dim in NNR_DIMENSIONS:
        level = nnr.get(dim)
        if level not in VALID_NNR_LEVELS:
            return False, f"nnr_indicators.{dim} invalid: {level!r}"
    if not isinstance(response["signal_evidence"], list):
        return False, "signal_evidence must be a list"
    for ev in response["signal_evidence"]:
        if not (isinstance(ev, dict) and "signal" in ev and "source" in ev):
            return False, "each signal_evidence entry must be {signal, source}"
        if not isinstance(ev["source"], str) or not ev["source"].strip():
            return False, "signal_evidence.source must be a non-empty string"
    sources = [
        evidence["source"]
        for evidence in response["signal_evidence"]
        if isinstance(evidence, dict)
    ]
    for source in sources:
        if "://" not in source and not _PROFILE_FIELD_REF.fullmatch(source):
            return False, f"invalid signal_evidence source reference: {source!r}"
    url_sources = [source for source in sources if "://" in source]
    ok, message = assert_no_hallucinated_urls(
        [{"url": source} for source in url_sources],
        response.get("_retrieved_uris", []) or [],
    )
    if not ok:
        return False, message
    if not isinstance(response["data_gaps"], list):
        return False, "data_gaps must be a list"
    return True, ""
