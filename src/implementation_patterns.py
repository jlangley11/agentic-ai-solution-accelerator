"""Shared implementation-pattern vocabulary for design and runtime."""
from __future__ import annotations

IMPLEMENTATION_PATTERNS = ("managed-prompt", "harness", "custom-workflow")


def implementation_pattern_for(
    agent_type: str,
    orchestration: str,
    *,
    custom_framework: bool = False,
) -> str:
    """Derive the safe default implementation from approved architecture."""
    if agent_type == "prompt-agent":
        return "managed-prompt"
    if orchestration == "single-agent" and not custom_framework:
        return "harness"
    return "custom-workflow"


def legacy_implementation_pattern_for(agent_type: str) -> str:
    """Preserve pre-Harness manifests until they are explicitly re-approved."""
    return "managed-prompt" if agent_type == "prompt-agent" else "custom-workflow"
