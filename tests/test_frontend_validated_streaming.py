from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).parents[1]
FRONTEND = ROOT / "patterns" / "sales-research-frontend" / "src"


def test_flagship_result_panel_never_parses_or_renders_raw_chunks() -> None:
    text = (FRONTEND / "components" / "ResultPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "tryParsePartialJson" not in text
    assert "streaming-raw-text" not in text
    assert "workerThoughts" not in text


def test_generic_workbench_ignores_unvalidated_chunk_events() -> None:
    text = (FRONTEND / "components" / "ScenarioWorkbench.tsx").read_text(
        encoding="utf-8"
    )

    assert 'event.type === "chunk"' in text
    assert 'if (event.type === "chunk" || event.type === "done") return;' in text


def test_flagship_stores_only_chunk_length_not_raw_delta() -> None:
    text = (FRONTEND / "App.tsx").read_text(encoding="utf-8")

    assert "(prev[key] ?? 0) + evt.delta.length" in text
    assert '(prev[key] ?? "") + evt.delta' not in text
