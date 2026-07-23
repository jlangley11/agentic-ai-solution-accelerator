from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).parents[1]
LINT_PATH = ROOT / "scripts" / "accelerator-lint.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("quickstart_lint", LINT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quickstart_requires_disclosure_after_intake(tmp_path, monkeypatch) -> None:
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    (tmp_path / "QUICKSTART.md").write_text(
        "accel intake add <path>\naccel intake review <source-id>\n",
        encoding="utf-8",
    )

    findings = lint.quickstart_enforces_intake_disclosure(lint.Ctx())

    assert len(findings) == 1
    assert findings[0].rule == "quickstart-intake-disclosure"


def test_quickstart_disclosure_flow_passes(tmp_path, monkeypatch) -> None:
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    (tmp_path / "QUICKSTART.md").write_text(
        "accel intake add <path>\n"
        "accel intake review <source-id>\n"
        "accel intake disclose <source-id> approved_for_model --apply\n",
        encoding="utf-8",
    )

    assert lint.quickstart_enforces_intake_disclosure(lint.Ctx()) == []
