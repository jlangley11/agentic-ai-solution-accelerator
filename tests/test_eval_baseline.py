"""Tests for scripts/eval-baseline.py — regression diff logic."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
EBL = ROOT / "scripts" / "eval-baseline.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("eval_baseline", EBL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_baseline"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_check_no_baseline_returns_zero(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    # No evals/baseline dir at all.
    (tmp_path / "evals" / "quality").mkdir(parents=True)
    _write_jsonl(tmp_path / "evals" / "quality" / "results.jsonl",
                 [{"case_id": "q-001", "passed": True}])
    assert mod.check() == 0


def test_check_no_flips_returns_zero(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    cases = [
        {"case_id": "q-001", "passed": True},
        {"case_id": "q-002", "passed": True},
    ]
    _write_jsonl(tmp_path / "evals" / "quality" / "results.jsonl", cases)
    _write_jsonl(tmp_path / "evals" / "redteam" / "results.jsonl",
                 [{"case_id": "xpia-001", "passed": True}])
    _write_jsonl(tmp_path / "evals" / "baseline" / "quality-baseline.jsonl", cases)
    _write_jsonl(tmp_path / "evals" / "baseline" / "redteam-baseline.jsonl",
                 [{"case_id": "xpia-001", "passed": True}])
    assert mod.check() == 0


def test_check_pass_to_fail_flip_returns_one(tmp_path, monkeypatch, capsys):
    mod = _load_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_jsonl(tmp_path / "evals" / "baseline" / "quality-baseline.jsonl",
                 [{"case_id": "q-001", "passed": True},
                  {"case_id": "q-002", "passed": True}])
    _write_jsonl(tmp_path / "evals" / "quality" / "results.jsonl",
                 [{"case_id": "q-001", "passed": True},
                  {"case_id": "q-002", "passed": False}])
    # redteam: identical
    _write_jsonl(tmp_path / "evals" / "baseline" / "redteam-baseline.jsonl",
                 [{"case_id": "x-001", "passed": True}])
    _write_jsonl(tmp_path / "evals" / "redteam" / "results.jsonl",
                 [{"case_id": "x-001", "passed": True}])
    assert mod.check() == 1
    captured = capsys.readouterr()
    assert "q-002" in captured.out
    assert "regression" in captured.out


def test_check_skips_when_smoke_subset(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    # Baseline = 3 cases; current = 1 case (smoke run).
    _write_jsonl(tmp_path / "evals" / "baseline" / "quality-baseline.jsonl",
                 [{"case_id": "q-001", "passed": True},
                  {"case_id": "q-002", "passed": True},
                  {"case_id": "q-003", "passed": True}])
    _write_jsonl(tmp_path / "evals" / "quality" / "results.jsonl",
                 [{"case_id": "q-001", "passed": True}])
    _write_jsonl(tmp_path / "evals" / "baseline" / "redteam-baseline.jsonl",
                 [{"case_id": "x-001", "passed": True}])
    _write_jsonl(tmp_path / "evals" / "redteam" / "results.jsonl",
                 [{"case_id": "x-001", "passed": True}])
    assert mod.check() == 0


def test_snapshot_copies_results(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_jsonl(tmp_path / "evals" / "quality" / "results.jsonl",
                 [{"case_id": "q-001", "passed": True}])
    _write_jsonl(tmp_path / "evals" / "redteam" / "results.jsonl",
                 [{"case_id": "x-001", "passed": True}])
    assert mod.snapshot() == 0
    assert (tmp_path / "evals" / "baseline" / "quality-baseline.jsonl").exists()
    assert (tmp_path / "evals" / "baseline" / "redteam-baseline.jsonl").exists()
