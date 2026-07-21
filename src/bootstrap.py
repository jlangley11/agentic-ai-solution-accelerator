"""Compatibility startup shim for self-hosted provisioning.

The substantive implementation lives in :mod:`src.provisioning` so it can run
before either the FastAPI/ACA host or the opt-in Hosted Agents preview host.
Runtime provisioning is intentionally disabled when hosted identity markers
are present.
"""
from __future__ import annotations

import logging
import os

from .provisioning import (
    _agent_definition_unchanged,
    _kb_tool_present,
    _merge_preserved_tools,
    _tool_fingerprint,
    provision,
)
from .workflow.registry import ScenarioBundle

logger = logging.getLogger("accelerator.bootstrap")

__all__ = [
    "_agent_definition_unchanged",
    "_kb_tool_present",
    "_merge_preserved_tools",
    "_tool_fingerprint",
    "bootstrap",
]


async def bootstrap(bundle: ScenarioBundle) -> None:
    """Provision resources during self-host startup unless explicitly skipped."""
    if os.environ.get("BOOTSTRAP_SKIP") == "1":
        logger.info("bootstrap: BOOTSTRAP_SKIP=1; skipping")
        return

    hosted_marker = None
    if os.environ.get("HOSTED_AGENT") == "1":
        hosted_marker = "HOSTED_AGENT"
    elif os.environ.get("FOUNDRY_AGENT_ID"):
        hosted_marker = "FOUNDRY_AGENT_ID"
    if hosted_marker is not None:
        logger.info(
            "bootstrap: hosted mode detected via %s; runtime provisioning is "
            "forbidden and will be skipped",
            hosted_marker,
        )
        return

    await provision(bundle)
