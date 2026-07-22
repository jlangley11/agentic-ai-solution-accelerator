"""Render the shared command protocol for a terminal user."""
from __future__ import annotations

from .protocol import CommandResult


def render_human(result: CommandResult, *, verbose: bool = False) -> str:
    lines = [
        f"Stage: {result.stage.value}",
        f"Status: {result.status.value}",
        "",
        result.summary,
    ]
    if result.completed:
        lines.extend(("", "Completed:"))
        lines.extend(f"  [x] {item}" for item in result.completed)
    if result.required_inputs:
        lines.extend(("", "Required input:"))
        lines.extend(f"  - {item.prompt}" for item in result.required_inputs)
    if result.blocking_issues:
        lines.extend(("", "Issues:"))
        for issue in result.blocking_issues:
            rendered = f"  - {issue.message}"
            if issue.remediation:
                rendered += f" Fix: {issue.remediation}"
            lines.append(rendered)
    if result.proposed_actions:
        lines.extend(("", "Actions:"))
        for action in result.proposed_actions:
            lines.append(
                f"  - [{action.approval.value}] {action.label}: {action.command}"
            )
    if result.artifacts:
        lines.extend(("", "Artifacts:"))
        lines.extend(
            f"  - {artifact.path} ({artifact.status})"
            for artifact in result.artifacts
        )
    if result.next_command:
        lines.extend(("", f"Next: {result.next_command}"))
    if verbose and result.stages:
        lines.extend(("", "Lifecycle:"))
        lines.extend(
            f"  - {stage.stage.value}: {stage.status.value} - {stage.summary}"
            for stage in result.stages
        )
    return "\n".join(lines).rstrip() + "\n"
