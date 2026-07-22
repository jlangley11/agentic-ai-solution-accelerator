"""Foundational accelerator CLI commands."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .lifecycle import detect_lifecycle
from .operations import recent_operations
from .protocol import (
    ApprovalLevel,
    Artifact,
    CommandResult,
    ProposedAction,
    ResultStatus,
    Stage,
)
from .repository import RepositoryContext


def status(context: RepositoryContext) -> CommandResult:
    lifecycle = detect_lifecycle(context)
    current = lifecycle.for_stage(lifecycle.current)
    return CommandResult(
        stage=lifecycle.current,
        status=current.status,
        summary=current.summary,
        completed=current.completed,
        blocking_issues=current.issues,
        proposed_actions=_actions_for_stage(lifecycle.current),
        artifacts=_core_artifacts(context),
        next_actions=tuple(action.label for action in _actions_for_stage(lifecycle.current)),
        next_command=_next_command(lifecycle.current),
        stages=lifecycle.stages,
        details={
            "git_changes": list(context.git_changes()),
            "recent_operations": recent_operations(context),
        },
    )


def next_step(context: RepositoryContext) -> CommandResult:
    lifecycle = detect_lifecycle(context)
    current = lifecycle.for_stage(lifecycle.current)
    actions = _actions_for_stage(lifecycle.current)
    return CommandResult(
        stage=lifecycle.current,
        status=current.status,
        summary=current.summary,
        completed=current.completed,
        blocking_issues=current.issues,
        proposed_actions=actions,
        next_actions=tuple(action.label for action in actions),
        next_command=_next_command(lifecycle.current),
        stages=lifecycle.stages,
    )


def review(context: RepositoryContext) -> CommandResult:
    changes = context.git_changes()
    if not changes:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.COMPLETE,
            summary="The repository has no staged or unstaged changes.",
            next_command="accel next",
        )
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.READY,
        summary=f"{len(changes)} repository change(s) require review.",
        completed=changes,
        proposed_actions=(
            ProposedAction(
                "explain-change",
                "Explain change impact",
                f"{sys.executable} scripts/explain-change.py",
            ),
            ProposedAction(
                "git-diff",
                "Review the repository diff",
                "git --no-pager diff",
            ),
        ),
        next_command="accel validate",
    )


def validate(
    context: RepositoryContext,
    *,
    execute: bool,
    full: bool,
) -> CommandResult:
    commands = [
        [sys.executable, "scripts/accelerator-lint.py"],
        [sys.executable, "-m", "pytest", "-q"],
    ]
    if full:
        commands = [
            ["ruff", "check", "src", "patterns", "scripts"],
            ["pyright", "src", "patterns"],
            *commands,
        ]
    rendered = tuple(" ".join(command) for command in commands)
    if not execute:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary="Validation commands are ready to run.",
            proposed_actions=tuple(
                ProposedAction(
                    f"validate-{index}",
                    f"Run validation command {index}",
                    command,
                    ApprovalLevel.EXECUTE,
                )
                for index, command in enumerate(rendered, start=1)
            ),
            next_command=f"accel validate {'--full ' if full else ''}--execute",
        )

    failures: list[str] = []
    outputs: dict[str, dict[str, object]] = {}
    for command, display in zip(commands, rendered, strict=True):
        completed = subprocess.run(  # noqa: S603 - fixed repository-owned argv
            command,
            cwd=context.root,
            check=False,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        outputs[display] = {
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
        if completed.returncode != 0:
            failures.append(display)
    result_status = ResultStatus.COMPLETE if not failures else ResultStatus.FAILED
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=result_status,
        summary=(
            "All validation commands passed."
            if not failures
            else f"{len(failures)} validation command(s) failed."
        ),
        completed=tuple(command for command in rendered if command not in failures),
        blocking_issues=tuple(),
        next_command="accel next" if not failures else "accel review",
        details={"commands": outputs, "failed": failures},
    )


def _actions_for_stage(stage: Stage) -> tuple[ProposedAction, ...]:
    mapping = {
        Stage.QUALIFY: (
            ProposedAction(
                "start-discovery",
                "Start or continue customer discovery",
                "accel discover",
            ),
        ),
        Stage.DISCOVER: (
            ProposedAction(
                "continue-discovery",
                "Resolve outstanding discovery requirements",
                "accel discover",
            ),
        ),
        Stage.DESIGN: (
            ProposedAction(
                "review-architecture",
                "Review the Foundry architecture recommendation",
                "accel design",
            ),
        ),
        Stage.SCAFFOLD: (
            ProposedAction(
                "preview-scaffold",
                "Preview scenario scaffolding",
                "accel scaffold --scenario-id <id> --dry-run",
            ),
        ),
        Stage.PROVISION: (
            ProposedAction(
                "list-environments",
                "Review deployment environments",
                "accel environment list",
            ),
            ProposedAction(
                "preview-deploy",
                "Run deployment preflight",
                "accel deploy --dry-run",
            ),
        ),
        Stage.ITERATE: (
            ProposedAction(
                "validate",
                "Run local validation",
                "accel validate",
            ),
            ProposedAction(
                "evaluate",
                "Prepare deployed evaluations",
                "accel evaluate",
            ),
        ),
        Stage.UAT: (
            ProposedAction(
                "uat-report",
                "Generate or review the UAT report",
                "accel uat report",
            ),
        ),
        Stage.HANDOVER: (
            ProposedAction(
                "handover",
                "Generate the handover package",
                "accel handover generate --dry-run",
            ),
        ),
        Stage.OPERATE: (
            ProposedAction(
                "operate",
                "Review day-2 operational status",
                "accel operate status",
            ),
        ),
    }
    return mapping[stage]


def _next_command(stage: Stage) -> str:
    return _actions_for_stage(stage)[0].command


def _core_artifacts(context: RepositoryContext) -> tuple[Artifact, ...]:
    paths = (
        ("manifest", context.manifest_path, "Executable engagement contract"),
        ("brief", context.brief_path, "Customer-approved solution brief"),
        (
            "evidence",
            context.private_dir / "evidence.db",
            "Local private evidence ledger",
        ),
    )
    return tuple(
        Artifact(
            id=artifact_id,
            path=_display_path(context, path),
            status="present" if path.exists() else "missing",
            description=description,
        )
        for artifact_id, path, description in paths
    )


def _display_path(context: RepositoryContext, path: Path) -> str:
    try:
        return context.relative(path)
    except ValueError:
        return str(path)
