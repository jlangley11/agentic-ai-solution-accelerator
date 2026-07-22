from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "generate-cli-docs.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_cli_docs", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_cli_reference_is_current() -> None:
    generator = _load_generator()

    assert generator.OUTPUT.read_text(encoding="utf-8") == generator.render()
