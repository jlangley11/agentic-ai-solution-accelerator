from __future__ import annotations

import pathlib

import pytest

from src.workflow.registry import _validate_architecture


def _manifest() -> tuple[dict, dict]:
    scenario = {
        "implementation": {
            "agent_type": "hosted-agent",
            "implementation_pattern": "custom-workflow",
            "orchestration_pattern": "supervisor-routing",
            "application_shell": "workbench",
        }
    }
    manifest = {
        "architecture": {
            "status": "approved",
            "decision": dict(scenario["implementation"]),
        },
        "scenario": scenario,
    }
    return manifest, scenario


def test_runtime_accepts_approved_matching_architecture() -> None:
    manifest, scenario = _manifest()

    _validate_architecture(manifest, scenario, pathlib.Path("accelerator.yaml"))


def test_runtime_rejects_unapproved_architecture() -> None:
    manifest, scenario = _manifest()
    manifest["architecture"]["status"] = "proposed"

    with pytest.raises(ValueError, match=r"Run `accel design`"):
        _validate_architecture(manifest, scenario, pathlib.Path("accelerator.yaml"))


def test_runtime_rejects_scenario_implementation_drift() -> None:
    manifest, scenario = _manifest()
    scenario["implementation"]["agent_type"] = "prompt-agent"

    with pytest.raises(
        ValueError,
        match=r"scenario\.implementation\.agent_type must match.*Run `accel design`",
    ):
        _validate_architecture(manifest, scenario, pathlib.Path("accelerator.yaml"))


def test_runtime_rejects_invalid_harness_combination() -> None:
    manifest, scenario = _manifest()
    manifest["architecture"]["decision"]["implementation_pattern"] = "harness"
    scenario["implementation"]["implementation_pattern"] = "harness"

    with pytest.raises(ValueError, match="Harness requires"):
        _validate_architecture(manifest, scenario, pathlib.Path("accelerator.yaml"))


def test_legacy_hosted_single_agent_is_not_reclassified_as_harness() -> None:
    scenario = {
        "implementation": {
            "agent_type": "hosted-agent",
            "orchestration_pattern": "single-agent",
            "application_shell": "workbench",
        }
    }
    manifest = {
        "architecture": {
            "status": "approved",
            "decision": dict(scenario["implementation"]),
        },
        "scenario": scenario,
    }

    _validate_architecture(manifest, scenario, pathlib.Path("accelerator.yaml"))
