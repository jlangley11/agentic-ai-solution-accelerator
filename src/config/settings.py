"""Runtime config — env-sourced, DefaultAzureCredential-backed.

Never hardcode. Every resource name flows from ``azd`` env vars or Key Vault
references. If a value is missing, fail loudly at startup.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _require(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(
            f"Required env var {name!r} is not set. See azure.yaml + infra/ "
            f"parameters; `azd env get-values` should include it after `azd up`."
        )
    return v


def foundry_project_endpoint() -> str:
    """Return the Foundry project endpoint for either supported runtime."""
    for name in ("FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_FOUNDRY_ENDPOINT"):
        value = os.environ.get(name)
        if value:
            return value
    raise RuntimeError(
        "Required env var 'FOUNDRY_PROJECT_ENDPOINT' or "
        "'AZURE_AI_FOUNDRY_ENDPOINT' is not set. See azure.yaml + infra/ "
        "parameters; `azd env get-values` should include it after `azd up`."
    )


@dataclass(frozen=True)
class Settings:
    # Foundry
    foundry_project_endpoint: str
    # AI Search
    ai_search_endpoint: str
    ai_search_index: str
    # Observability
    appinsights_connection: str | None
    # HITL
    hitl_approver_endpoint: str | None
    # CORS
    cors_allowed_origins: tuple[str, ...]


def _parse_origins(raw: str | None) -> tuple[str, ...]:
    """Parse a comma-separated ALLOWED_ORIGINS env var into a tuple.

    Empty / unset → empty tuple (no cross-origin allowed; production-safe default).
    The literal value ``*`` is treated specially by the FastAPI middleware
    (allow-all without credentials); pass it explicitly only in dev sandboxes.
    """
    if not raw:
        return ()
    return tuple(o.strip() for o in raw.split(",") if o.strip())


def load_settings() -> Settings:
    return Settings(
        foundry_project_endpoint=foundry_project_endpoint(),
        ai_search_endpoint=_require("AZURE_AI_SEARCH_ENDPOINT"),
        ai_search_index=os.environ.get("AZURE_AI_SEARCH_INDEX", "accounts"),
        appinsights_connection=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        hitl_approver_endpoint=os.environ.get("HITL_APPROVER_ENDPOINT"),
        cors_allowed_origins=_parse_origins(os.environ.get("ALLOWED_ORIGINS")),
    )
