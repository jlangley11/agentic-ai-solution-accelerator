"""Tool-callable API that returns the same versioned contract as `accel`."""
from __future__ import annotations

from typing import Any

from src.accelerator_cli import commands, lifecycle_commands
from src.accelerator_cli.intake import commands as intake_commands
from src.accelerator_cli.operations import ensure_private_workspace, record_operation
from src.accelerator_cli.protocol import CommandResult
from src.accelerator_cli.repository import RepositoryContext


class AcceleratorApi:
    def __init__(self, context: RepositoryContext | None = None) -> None:
        self.context = context or RepositoryContext.discover()

    def status(self) -> dict[str, Any]:
        return self._finish("mcp.status", commands.status(self.context))

    def next(self) -> dict[str, Any]:
        return self._finish("mcp.next", commands.next_step(self.context))

    def review(self) -> dict[str, Any]:
        return self._finish("mcp.review", commands.review(self.context))

    def validate(self, *, execute: bool = False, full: bool = False) -> dict[str, Any]:
        result = commands.validate(
            self.context,
            execute=execute,
            full=full,
        )
        return self._finish(
            "mcp.validate",
            result,
            journal=execute,
        )

    def intake_sources(self) -> dict[str, Any]:
        return self._finish(
            "mcp.intake_sources",
            intake_commands.list_sources(self.context),
        )

    def intake_review(
        self,
        source_id: str,
        *,
        include_text: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._finish(
            "mcp.intake_review",
            intake_commands.review(
                self.context,
                source_id,
                include_text=include_text,
                limit=limit,
                offset=offset,
            ),
        )

    def intake_disclose(
        self,
        source_id: str,
        disclosure_status: str,
        *,
        apply: bool = False,
    ) -> dict[str, Any]:
        result = intake_commands.disclose(
            self.context,
            source_id,
            disclosure_status,
            apply=apply,
        )
        return self._finish(
            "mcp.intake_disclose",
            result,
            journal=apply,
        )

    def scaffold(
        self,
        scenario_id: str,
        *,
        no_retrieval: bool = False,
        preserve_evals: bool = False,
        apply: bool = False,
    ) -> dict[str, Any]:
        result = lifecycle_commands.scaffold(
            self.context,
            scenario_id=scenario_id,
            no_retrieval=no_retrieval,
            preserve_evals=preserve_evals,
            apply=apply,
        )
        return self._finish(
            "mcp.scaffold",
            result,
            journal=apply,
        )

    def deployment_plan(
        self,
        env: str,
        region: str,
        *,
        target: str | None = None,
        acknowledge_preview: bool = False,
    ) -> dict[str, Any]:
        return self._finish(
            "mcp.deployment_plan",
            lifecycle_commands.deploy(
                self.context,
                env=env,
                region=region,
                target=target,
                acknowledge_preview=acknowledge_preview,
                execute=False,
                apply=False,
            ),
        )

    def deploy(
        self,
        env: str,
        region: str,
        *,
        target: str | None = None,
        acknowledge_preview: bool = False,
        execute: bool = False,
        apply: bool = False,
    ) -> dict[str, Any]:
        result = lifecycle_commands.deploy(
            self.context,
            env=env,
            region=region,
            target=target,
            acknowledge_preview=acknowledge_preview,
            execute=execute,
            apply=apply,
        )
        return self._finish(
            "mcp.deploy",
            result,
            journal=execute or apply,
        )

    def _finish(
        self,
        command: str,
        result: CommandResult,
        *,
        journal: bool = False,
    ) -> dict[str, Any]:
        if not journal:
            return result.to_dict()
        try:
            ensure_private_workspace(self.context)
            record_operation(self.context, command, result)
        except OSError as exc:
            payload = result.to_dict()
            details = dict(payload.get("details") or {})
            details["journal_warning"] = str(exc)
            payload["details"] = details
            return payload
        return result.to_dict()
