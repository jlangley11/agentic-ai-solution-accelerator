"""Versioned command-result contract shared by humans, agents, and MCP."""
from __future__ import annotations

import dataclasses
import enum
import json
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "1.0"


class Stage(str, enum.Enum):
    QUALIFY = "qualify"
    DISCOVER = "discover"
    SCAFFOLD = "scaffold"
    PROVISION = "provision"
    ITERATE = "iterate"
    UAT = "uat"
    HANDOVER = "handover"
    OPERATE = "operate"


STAGE_ORDER: tuple[Stage, ...] = tuple(Stage)


class ResultStatus(str, enum.Enum):
    COMPLETE = "complete"
    READY = "ready"
    NEEDS_INPUT = "needs_input"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    FAILED = "failed"


class ApprovalLevel(str, enum.Enum):
    INSPECT = "inspect"
    APPLY = "apply"
    EXECUTE = "execute"
    DESTRUCTIVE = "destructive"


@dataclasses.dataclass(frozen=True)
class RequiredInput:
    id: str
    prompt: str
    kind: str = "text"
    required: bool = True
    choices: tuple[str, ...] = ()
    sensitive: bool = False


@dataclasses.dataclass(frozen=True)
class Issue:
    id: str
    message: str
    remediation: str | None = None
    path: str | None = None


@dataclasses.dataclass(frozen=True)
class ProposedAction:
    id: str
    label: str
    command: str
    approval: ApprovalLevel = ApprovalLevel.INSPECT
    reason: str | None = None


@dataclasses.dataclass(frozen=True)
class Artifact:
    id: str
    path: str
    status: str
    description: str | None = None


@dataclasses.dataclass(frozen=True)
class StageSummary:
    stage: Stage
    status: ResultStatus
    summary: str
    completed: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()


@dataclasses.dataclass(frozen=True)
class CommandResult:
    stage: Stage
    status: ResultStatus
    summary: str
    operation_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    completed: tuple[str, ...] = ()
    required_inputs: tuple[RequiredInput, ...] = ()
    blocking_issues: tuple[Issue, ...] = ()
    proposed_actions: tuple[ProposedAction, ...] = ()
    artifacts: tuple[Artifact, ...] = ()
    next_actions: tuple[str, ...] = ()
    next_command: str | None = None
    stages: tuple[StageSummary, ...] = ()
    details: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(dataclasses.asdict(self))

    def to_json(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self.to_dict(),
            indent=2 if pretty else None,
            sort_keys=pretty,
        )

    @property
    def exit_code(self) -> int:
        return {
            ResultStatus.COMPLETE: 0,
            ResultStatus.READY: 0,
            ResultStatus.NEEDS_INPUT: 10,
            ResultStatus.APPROVAL_REQUIRED: 20,
            ResultStatus.BLOCKED: 30,
            ResultStatus.FAILED: 40,
        }[self.status]


def _jsonable(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in value]
    return value
