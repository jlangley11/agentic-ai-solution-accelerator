from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).parents[1]
LINT = ROOT / "scripts" / "accelerator-lint.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("private_state_lint", LINT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lint_context_excludes_generated_and_private_directories(
    tmp_path: pathlib.Path,
    monkeypatch,
) -> None:
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
    for directory in ("docs-build", "site", ".accelerator", ".azure"):
        path = tmp_path / directory
        path.mkdir()
        (path / "private.json").write_text('{"secret":"do-not-read"}\n', encoding="utf-8")

    context = lint.Ctx()
    context.load()
    relative = {path.relative_to(tmp_path).as_posix() for path in context.files}

    assert "src/app.py" in relative
    assert not any("private.json" in path for path in relative)
