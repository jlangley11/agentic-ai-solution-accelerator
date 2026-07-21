"""Focused tests for Search schema-only provisioning."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import provisioning


@pytest.mark.asyncio
async def test_skip_seed_still_provisions_schema_without_embedding_or_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_indexes: list[object] = []
    search_clients: list[object] = []

    index = SimpleNamespace(
        fields=[
            SimpleNamespace(
                name="contentVector",
                vector_search_dimensions=1536,
            )
        ]
    )
    existing = SimpleNamespace(fields=[SimpleNamespace(name="contentVector")])
    entry = SimpleNamespace(
        name="accounts",
        seed="data/samples/accounts.json",
        schema_callable=lambda _name: index,
    )
    bundle = SimpleNamespace(retrieval_indexes=(entry,))

    class FakeCredential:
        async def close(self) -> None:
            return None

    class FakeIndexClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def get_index(self, _name: str) -> object:
            return existing

        async def create_or_update_index(self, value: object) -> None:
            created_indexes.append(value)

        async def close(self) -> None:
            return None

    class FakeSearchClient:
        def __init__(self, **_kwargs: object) -> None:
            search_clients.append(self)

    import azure.identity.aio
    import azure.search.documents.aio
    import azure.search.documents.indexes.aio

    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://search.example")
    monkeypatch.setattr(azure.identity.aio, "DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(
        azure.search.documents.indexes.aio,
        "SearchIndexClient",
        FakeIndexClient,
    )
    monkeypatch.setattr(
        azure.search.documents.aio,
        "SearchClient",
        FakeSearchClient,
    )
    embed = AsyncMock()
    monkeypatch.setattr(provisioning, "_embed_seed_docs", embed)

    await provisioning._bootstrap_search(bundle, skip_seed=True)  # type: ignore[arg-type]

    assert created_indexes == [index]
    assert search_clients == []
    embed.assert_not_awaited()
