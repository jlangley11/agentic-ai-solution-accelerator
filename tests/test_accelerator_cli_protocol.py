from __future__ import annotations

import json

from src.accelerator_cli.protocol import (
    ApprovalLevel,
    CommandResult,
    ProposedAction,
    ResultStatus,
    Stage,
)


def test_command_result_serializes_stable_wire_values() -> None:
    result = CommandResult(
        stage=Stage.SCAFFOLD,
        status=ResultStatus.APPROVAL_REQUIRED,
        summary="Preview ready.",
        proposed_actions=(
            ProposedAction(
                "apply",
                "Apply changes",
                "accel scaffold --apply",
                ApprovalLevel.APPLY,
            ),
        ),
    )

    payload = json.loads(result.to_json())

    assert payload["schema_version"] == "1.0"
    assert payload["stage"] == "scaffold"
    assert payload["status"] == "approval_required"
    assert payload["proposed_actions"][0]["approval"] == "apply"
    assert result.exit_code == 20


def test_complete_result_uses_success_exit_code() -> None:
    result = CommandResult(
        stage=Stage.OPERATE,
        status=ResultStatus.COMPLETE,
        summary="Complete.",
    )

    assert result.exit_code == 0
