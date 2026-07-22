from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).parents[1]
LINT = ROOT / "scripts" / "accelerator-lint.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("experience_lint", LINT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_scenario_experience_is_valid() -> None:
    lint = _load_lint()

    findings = lint.scenario_manifest_valid(lint.Ctx())

    assert not [
        finding
        for finding in findings
        if "scenario.experience" in finding.message
        or "response_schema" in finding.message
    ]
