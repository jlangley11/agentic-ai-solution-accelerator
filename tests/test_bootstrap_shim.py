"""Tests for the self-hosted bootstrap compatibility shim."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src import bootstrap


@pytest.fixture(autouse=True)
def _clear_bootstrap_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BOOTSTRAP_SKIP", "HOSTED_AGENT", "FOUNDRY_AGENT_ID"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_bootstrap_skip_noops(monkeypatch: pytest.MonkeyPatch) -> None:
    delegated = AsyncMock()
    monkeypatch.setattr(bootstrap, "provision", delegated)
    monkeypatch.setenv("BOOTSTRAP_SKIP", "1")

    await bootstrap.bootstrap(object())  # type: ignore[arg-type]

    delegated.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("marker", "value"),
    [("HOSTED_AGENT", "1"), ("FOUNDRY_AGENT_ID", "agent-123")],
)
async def test_hosted_runtime_noops(
    monkeypatch: pytest.MonkeyPatch,
    marker: str,
    value: str,
) -> None:
    delegated = AsyncMock()
    monkeypatch.setattr(bootstrap, "provision", delegated)
    monkeypatch.setenv(marker, value)

    await bootstrap.bootstrap(object())  # type: ignore[arg-type]

    delegated.assert_not_awaited()


@pytest.mark.asyncio
async def test_self_host_delegates_to_provision(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = object()
    delegated = AsyncMock()
    monkeypatch.setattr(bootstrap, "provision", delegated)

    await bootstrap.bootstrap(bundle)  # type: ignore[arg-type]

    delegated.assert_awaited_once_with(bundle)
