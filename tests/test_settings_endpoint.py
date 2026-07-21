from __future__ import annotations

import pytest

from src.config.settings import foundry_project_endpoint


def test_foundry_project_endpoint_prefers_hosted_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://hosted.example")
    monkeypatch.setenv("AZURE_AI_FOUNDRY_ENDPOINT", "https://selfhost.example")

    assert foundry_project_endpoint() == "https://hosted.example"


def test_foundry_project_endpoint_falls_back_to_selfhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_AI_FOUNDRY_ENDPOINT", "https://selfhost.example")

    assert foundry_project_endpoint() == "https://selfhost.example"


def test_foundry_project_endpoint_requires_an_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_AI_FOUNDRY_ENDPOINT", raising=False)

    with pytest.raises(RuntimeError, match="FOUNDRY_PROJECT_ENDPOINT.*AZURE_AI_FOUNDRY_ENDPOINT"):
        foundry_project_endpoint()
