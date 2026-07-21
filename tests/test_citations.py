"""Unit tests for src.accelerator_baseline.citations."""
from __future__ import annotations

from types import SimpleNamespace

from src.accelerator_baseline.citations import (
    assert_no_hallucinated_urls,
    extract_tool_trace_uris,
    require_citations,
)


def test_require_citations_passes_when_no_factual_fields_present():
    ok, msg = require_citations(
        {"summary": "", "citations": []},
        when_fields_present=("recent_news", "buying_committee"),
    )
    assert ok and msg == ""


def test_require_citations_passes_when_citations_present():
    ok, msg = require_citations(
        {"recent_news": ["x"], "citations": [{"url": "https://example.com"}]},
        when_fields_present=("recent_news",),
    )
    assert ok and msg == ""


def test_require_citations_fails_when_factual_field_populated_no_citations():
    ok, msg = require_citations(
        {"recent_news": ["x"], "citations": []},
        when_fields_present=("recent_news", "buying_committee"),
    )
    assert not ok
    assert "recent_news" in msg
    assert "groundedness" in msg


def test_require_citations_rejects_non_list_citations():
    ok, msg = require_citations(
        {"recent_news": ["x"], "citations": "not a list"},
        when_fields_present=("recent_news",),
    )
    assert not ok
    assert "must be a list" in msg


def test_require_citations_treats_empty_string_as_unpopulated():
    ok, msg = require_citations(
        {"recent_news": "", "citations": []},
        when_fields_present=("recent_news",),
    )
    assert ok and msg == ""


def test_assert_no_hallucinated_urls_passes_when_normalized_url_matches():
    ok, _ = assert_no_hallucinated_urls(
        [{"url": "https://WWW.contoso.com/news/1/"}],
        ["https://www.contoso.com/news/1#retrieved"],
    )
    assert ok


def test_assert_no_hallucinated_urls_fails_on_fabricated_same_host_path():
    ok, msg = assert_no_hallucinated_urls(
        [{"url": "https://investors.contoso.example/press/fabricated"}],
        ["https://investors.contoso.example/press/q1-2026"],
    )
    assert not ok
    assert "fabricated" in msg


def test_assert_no_hallucinated_urls_fails_on_unknown_host():
    ok, msg = assert_no_hallucinated_urls(
        [{"url": "https://hallucinated.example/x"}],
        ["https://www.contoso.com/wiki"],
    )
    assert not ok
    assert "hallucinated.example" in msg


def test_assert_no_hallucinated_urls_fails_open_when_no_sources():
    ok, _ = assert_no_hallucinated_urls(
        [{"url": "https://anything.example/x"}], [],
    )
    assert ok


def test_assert_no_hallucinated_urls_skips_url_less_citations():
    ok, _ = assert_no_hallucinated_urls(
        [{"id": "doc-42", "quote": "..."}],
        ["https://www.contoso.com/wiki"],
    )
    assert ok


def test_assert_no_hallucinated_urls_empty_citations():
    ok, _ = assert_no_hallucinated_urls([], ["https://x.example"])
    assert ok


# ---------------------------------------------------------------------------
# extract_tool_trace_uris
# ---------------------------------------------------------------------------


def _ns_response(messages):
    return SimpleNamespace(messages=messages)


def _ns_message(contents):
    return SimpleNamespace(contents=contents)


def _ns_content(annotations):
    return SimpleNamespace(annotations=annotations)


def test_extract_tool_trace_uris_returns_empty_for_none():
    assert extract_tool_trace_uris(None) == set()


def test_extract_tool_trace_uris_returns_empty_for_no_messages():
    assert extract_tool_trace_uris(_ns_response(messages=[])) == set()


def test_extract_tool_trace_uris_collects_single_citation():
    resp = _ns_response([
        _ns_message([
            _ns_content([
                {"type": "citation", "url": "https://contoso.example/a"},
            ]),
        ]),
    ])
    assert extract_tool_trace_uris(resp) == {"https://contoso.example/a"}


def test_extract_tool_trace_uris_collects_foundryiq_source_metadata():
    resp = _ns_response([
        _ns_message([
            _ns_content([
                {
                    "type": "citation",
                    "url": "mcp://searchindex/contoso-ltd-01",
                    "additional_properties": {
                        "mcp_document_id": "contoso-ltd-01",
                        "source": "https://investors.contoso.example/press/q1-2026",
                    },
                },
            ]),
        ]),
    ])

    assert extract_tool_trace_uris(resp) == {
        "mcp://searchindex/contoso-ltd-01",
        "https://investors.contoso.example/press/q1-2026",
    }


def test_extract_tool_trace_uris_dedupes_across_messages():
    cite = {"type": "citation", "url": "https://contoso.example/a"}
    resp = _ns_response([
        _ns_message([_ns_content([cite, cite])]),
        _ns_message([_ns_content([cite])]),
    ])
    assert extract_tool_trace_uris(resp) == {"https://contoso.example/a"}


def test_extract_tool_trace_uris_collects_across_multiple_messages():
    resp = _ns_response([
        _ns_message([_ns_content([
            {"type": "citation", "url": "https://a.example/x"},
        ])]),
        _ns_message([_ns_content([
            {"type": "citation", "url": "https://b.example/y"},
        ])]),
    ])
    assert extract_tool_trace_uris(resp) == {
        "https://a.example/x",
        "https://b.example/y",
    }


def test_extract_tool_trace_uris_skips_non_citation_annotations():
    resp = _ns_response([
        _ns_message([_ns_content([
            {"type": "text_span", "url": "https://nope.example/z"},
            {"type": "citation", "url": "https://yes.example/q"},
        ])]),
    ])
    assert extract_tool_trace_uris(resp) == {"https://yes.example/q"}


def test_extract_tool_trace_uris_skips_citations_without_url():
    resp = _ns_response([
        _ns_message([_ns_content([
            {"type": "citation", "title": "no url here"},
            {"type": "citation", "url": ""},
            {"type": "citation", "url": "https://ok.example"},
        ])]),
    ])
    assert extract_tool_trace_uris(resp) == {"https://ok.example"}


def test_extract_tool_trace_uris_handles_dict_shaped_response():
    """Robust to plain-dict shape (e.g. deserialized telemetry payload)."""
    resp = {
        "messages": [
            {"contents": [
                {"annotations": [
                    {"type": "citation", "url": "https://dict.example"},
                ]},
            ]},
        ],
    }
    assert extract_tool_trace_uris(resp) == {"https://dict.example"}


def test_extract_tool_trace_uris_tolerates_missing_attrs():
    # message with no contents attribute, message with None contents,
    # content with None annotations -- all should degrade gracefully.
    resp = _ns_response([
        SimpleNamespace(),
        _ns_message(None),
        _ns_message([_ns_content(None)]),
    ])
    assert extract_tool_trace_uris(resp) == set()


def test_extract_tool_trace_uris_ignores_non_dict_annotations():
    """Defensive: future SDK might emit objects -- skip rather than raise."""
    resp = _ns_response([
        _ns_message([_ns_content([
            SimpleNamespace(type="citation", url="https://obj.example"),
            {"type": "citation", "url": "https://dict.example"},
        ])]),
    ])
    # Only the dict-shaped one is collected (current contract).
    assert extract_tool_trace_uris(resp) == {"https://dict.example"}
