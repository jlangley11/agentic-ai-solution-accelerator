from __future__ import annotations

import importlib.util
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).parents[1]
LINT_PATH = ROOT / "scripts" / "accelerator-lint.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("architecture_lint", LINT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return {
        "architecture": {
            "status": "approved",
            "requirements_fingerprint": "abc",
            "recommendation": {},
            "decision": {
                "agent_type": "prompt-agent",
                "orchestration_pattern": "single-agent",
                "application_shell": "none",
                "deployment_target": "foundry-prompt",
                "approved_by": "Architect",
                "approved_at": "2026-07-22T00:00:00+00:00",
            },
        },
        "scenario": {
            "implementation": {
                "agent_type": "prompt-agent",
                "orchestration_pattern": "single-agent",
                "application_shell": "none",
            }
        },
    }


def _run(tmp_path: pathlib.Path, monkeypatch, data: dict):
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    (tmp_path / "accelerator.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    return lint.architecture_decision_shape(lint.Ctx())


def test_valid_architecture_decision_passes(tmp_path, monkeypatch) -> None:
    assert _run(tmp_path, monkeypatch, _manifest()) == []


def test_prompt_agent_workflow_is_blocked(tmp_path, monkeypatch) -> None:
    data = _manifest()
    data["architecture"]["decision"]["orchestration_pattern"] = (
        "deterministic-workflow"
    )
    data["scenario"]["implementation"]["orchestration_pattern"] = (
        "deterministic-workflow"
    )

    findings = _run(tmp_path, monkeypatch, data)

    assert any("prompt-agent decisions" in finding.message for finding in findings)


def test_scenario_implementation_must_match_decision(tmp_path, monkeypatch) -> None:
    data = _manifest()
    data["scenario"]["implementation"]["agent_type"] = "hosted-agent"

    findings = _run(tmp_path, monkeypatch, data)

    assert any("scenario.implementation.agent_type" in finding.message for finding in findings)
