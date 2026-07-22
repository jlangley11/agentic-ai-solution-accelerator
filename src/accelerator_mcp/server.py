"""Run the accelerator workflow as a local stdio MCP server."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .api import AcceleratorApi

mcp = FastMCP(
    "accelerator",
    instructions=(
        "Use read-only status and preview tools first. File changes and cloud "
        "execution require explicit client approval. Never transmit local-only "
        "evidence excerpts without a recorded disclosure decision."
    ),
)


def _api() -> AcceleratorApi:
    return AcceleratorApi()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_status() -> dict[str, Any]:
    """Return lifecycle status, blockers, artifacts, and proposed next actions."""
    return _api().status()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_next() -> dict[str, Any]:
    """Return the next valid accelerator action from persistent repository state."""
    return _api().next()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_review() -> dict[str, Any]:
    """Return the repository change-review plan."""
    return _api().review()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_intake_sources() -> dict[str, Any]:
    """List local evidence sources without returning source text."""
    return _api().intake_sources()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_intake_review(
    source_id: str,
    include_text: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Review one local source; source text is omitted unless explicitly requested."""
    return _api().intake_review(
        source_id,
        include_text=include_text,
        limit=limit,
        offset=offset,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_intake_disclosure_preview(
    source_id: str,
    disclosure_status: str,
) -> dict[str, Any]:
    """Preview a local source-disclosure decision without changing it."""
    return _api().intake_disclose(
        source_id,
        disclosure_status,
        apply=False,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_intake_disclosure_apply(
    source_id: str,
    disclosure_status: str,
) -> dict[str, Any]:
    """Record a reviewed local source-disclosure decision."""
    return _api().intake_disclose(
        source_id,
        disclosure_status,
        apply=True,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_design_recommendation(
    agent_type: str | None = None,
    orchestration_pattern: str | None = None,
    application_shell: str | None = None,
    deployment_target: str | None = None,
    override_reason: str | None = None,
) -> dict[str, Any]:
    """Recommend or preview a reviewed Foundry architecture decision."""
    return _api().design(
        agent_type=agent_type,
        orchestration_pattern=orchestration_pattern,
        application_shell=application_shell,
        deployment_target=deployment_target,
        override_reason=override_reason,
        apply=False,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_design_approve(
    approved_by: str,
    agent_type: str | None = None,
    orchestration_pattern: str | None = None,
    application_shell: str | None = None,
    deployment_target: str | None = None,
    override_reason: str | None = None,
) -> dict[str, Any]:
    """Record an explicitly approved architecture decision."""
    return _api().design(
        agent_type=agent_type,
        orchestration_pattern=orchestration_pattern,
        application_shell=application_shell,
        deployment_target=deployment_target,
        approved_by=approved_by,
        override_reason=override_reason,
        apply=True,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
def accelerator_scaffold_preview(
    scenario_id: str,
    no_retrieval: bool = False,
    preserve_evals: bool = False,
) -> dict[str, Any]:
    """Preview scenario files and manifest changes without writing them."""
    return _api().scaffold(
        scenario_id,
        no_retrieval=no_retrieval,
        preserve_evals=preserve_evals,
        apply=False,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
def accelerator_scaffold_apply(
    scenario_id: str,
    no_retrieval: bool = False,
    preserve_evals: bool = False,
) -> dict[str, Any]:
    """Create a reviewed scenario scaffold and update accelerator.yaml."""
    return _api().scaffold(
        scenario_id,
        no_retrieval=no_retrieval,
        preserve_evals=preserve_evals,
        apply=True,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
def accelerator_deployment_plan(
    env: str,
    region: str,
    target: str | None = None,
    acknowledge_preview: bool = False,
) -> dict[str, Any]:
    """Return deployment preflight and execution commands without running them."""
    return _api().deployment_plan(
        env,
        region,
        target=target,
        acknowledge_preview=acknowledge_preview,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    )
)
def accelerator_deploy(
    env: str,
    region: str,
    target: str | None = None,
    acknowledge_preview: bool = False,
    execute: bool = False,
    apply: bool = False,
) -> dict[str, Any]:
    """Preview, preflight, or execute a deployment with explicit flags."""
    return _api().deploy(
        env,
        region,
        target=target,
        acknowledge_preview=acknowledge_preview,
        execute=execute,
        apply=apply,
    )


def main(argv: Sequence[str] | None = None) -> None:
    del argv
    mcp.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
