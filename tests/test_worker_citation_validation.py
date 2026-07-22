from __future__ import annotations

from src.accelerator_baseline import citations
from src.scenarios.sales_research.agents.competitive_context.validate import (
    validate_response as validate_competitive,
)
from src.scenarios.sales_research.agents.icp_fit_analyst.validate import (
    validate_response as validate_icp,
)


def _competitive(url: str) -> dict:
    return {
        "competitors": [
            {
                "name": "Example",
                "stance": "incumbent",
                "evidence": "Public evidence",
                "evidence_urls": [url],
            }
        ],
        "differentiators": ["Integrated platform"],
        "likely_objections": ["Migration risk"],
        "talking_points": ["Phased migration"],
        "cloud_footprint_signals": [
            {"provider": "azure", "workload_signal": "Uses Azure"}
        ],
        "competitor_refs": [],
        "_retrieved_uris": ["https://real.example/source"],
    }


def _icp(url: str) -> dict:
    return {
        "fit_score": 80,
        "fit_reasons": ["Strong fit"],
        "fit_risks": [],
        "recommended_segment": "enterprise",
        "recommended_action": "pursue",
        "tier_recommendation": "tier-1",
        "signal_evidence": [{"signal": "Growth", "source": url}],
        "nnr_indicators": {
            "size_signal": "strong",
            "growth_signal": "moderate",
            "wallet_expansion_signal": "strong",
        },
        "data_gaps": [],
        "_retrieved_uris": ["https://real.example/source"],
    }


def test_competitive_context_rejects_hallucinated_evidence_url() -> None:
    ok, message = validate_competitive(
        _competitive("https://not-retrieved.example/source")
    )

    assert not ok
    assert "not in retrieved" in message


def test_icp_fit_rejects_hallucinated_signal_source() -> None:
    ok, message = validate_icp(_icp("https://not-retrieved.example/source"))

    assert not ok
    assert "not in retrieved" in message


def test_icp_fit_accepts_upstream_profile_field_reference() -> None:
    response = _icp("strategic_initiatives[0]")

    ok, message = validate_icp(response)

    assert ok
    assert message == ""


def test_empty_provenance_fail_open_emits_telemetry(monkeypatch) -> None:
    emitted = []
    monkeypatch.setattr(citations, "emit_event", emitted.append)

    ok, message = citations.assert_no_hallucinated_urls(
        [{"url": "https://claimed.example/source"}],
        [],
    )

    assert ok
    assert message == ""
    assert emitted[0].name == "citation.guard_bypassed"
    assert emitted[0].ok is False


def test_quote_only_citations_do_not_emit_url_guard_bypass(monkeypatch) -> None:
    emitted = []
    monkeypatch.setattr(citations, "emit_event", emitted.append)

    ok, message = citations.assert_no_hallucinated_urls(
        [{"quote": "Grounded excerpt"}],
        [],
    )

    assert ok
    assert message == ""
    assert emitted == []
