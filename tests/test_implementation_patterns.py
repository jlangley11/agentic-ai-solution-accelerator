from src.implementation_patterns import (
    implementation_pattern_for,
    legacy_implementation_pattern_for,
)


def test_new_hosted_single_agent_defaults_to_harness() -> None:
    assert implementation_pattern_for("hosted-agent", "single-agent") == "harness"


def test_legacy_hosted_single_agent_remains_custom_workflow() -> None:
    assert legacy_implementation_pattern_for("hosted-agent") == "custom-workflow"


def test_legacy_prompt_agent_remains_managed_prompt() -> None:
    assert legacy_implementation_pattern_for("prompt-agent") == "managed-prompt"
