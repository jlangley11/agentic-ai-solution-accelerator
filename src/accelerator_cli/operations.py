"""Local operation journal used to resume work across coding-agent sessions."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from .protocol import CommandResult
from .repository import RepositoryContext


def ensure_private_workspace(context: RepositoryContext) -> None:
    context.private_dir.mkdir(parents=True, exist_ok=True)
    context.artifacts_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        context.private_dir.chmod(0o700)


def record_operation(
    context: RepositoryContext,
    command: str,
    result: CommandResult,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    workspace = context.root / ".accelerator"
    if not workspace.exists():
        return
    ensure_private_workspace(context)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "operation_id": result.operation_id,
        "command": command,
        "stage": result.stage.value,
        "status": result.status.value,
        "summary": result.summary,
        "metadata": metadata or {},
    }
    with context.operations_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, separators=(",", ":")) + "\n")


def recent_operations(
    context: RepositoryContext,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    path = context.operations_path
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows[-limit:]
