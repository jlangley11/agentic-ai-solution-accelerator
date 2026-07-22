"""Normalize microsoft.foundry Bicep outputs into Linux-safe env names."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Mapping

CANONICAL_KEYS = (
    "AZURE_AI_FOUNDRY_ENDPOINT",
    "AZURE_AI_FOUNDRY_ACCOUNT_ENDPOINT",
    "AZURE_AI_FOUNDRY_ACCOUNT_NAME",
    "AZURE_AI_FOUNDRY_PROJECT_NAME",
    "AZURE_AI_FOUNDRY_OPENAI_ENDPOINT",
    "AZURE_AI_FOUNDRY_MODEL",
    "AZURE_AI_FOUNDRY_MODEL_MAP",
    "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT",
    "AZURE_AI_FOUNDRY_RAI_POLICY",
    "AZURE_AI_SEARCH_ENDPOINT",
    "AZURE_AI_SEARCH_RESOURCE_ID",
    "AZURE_AI_FOUNDRY_SEARCH_CONNECTION_NAME",
    "AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME",
    "AZURE_AI_FOUNDRY_KB_NAME",
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
    "AZURE_AI_MODEL_DEPLOYMENT_NAME",
    "HOSTED_AGENT",
    "ENABLE_HOSTED_AGENTS",
)


def canonical_values(values: Mapping[str, object]) -> dict[str, str]:
    """Resolve exact keys or provider-mangled aliases case-insensitively."""
    aliases: dict[str, tuple[str, object]] = {}
    for name, value in values.items():
        normalized = name.upper()
        existing = aliases.get(normalized)
        if existing is None or name == normalized:
            aliases[normalized] = (name, value)

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in CANONICAL_KEYS:
        match = aliases.get(name)
        if match is None:
            missing.append(name)
            continue
        value = match[1]
        if isinstance(value, (dict, list)):
            resolved[name] = json.dumps(value, separators=(",", ":"))
        else:
            resolved[name] = str(value)

    if missing:
        raise RuntimeError(
            "Foundry provision omitted required environment outputs: "
            + ", ".join(missing)
        )
    return resolved


def normalize(
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """Persist canonical keys without logging their potentially sensitive values."""
    azd = shutil.which("azd")
    if not azd:
        raise FileNotFoundError("azd is not available on PATH")

    result = run(
        [azd, "env", "get-values", "-o", "json", "--no-prompt"],
        check=True,
        capture_output=True,
        text=True,
    )
    values = json.loads(result.stdout)
    if not isinstance(values, dict):
        raise RuntimeError("azd env get-values returned a non-object JSON value")

    for name, value in canonical_values(values).items():
        run([azd, "env", "set", name, value], check=True)
        print(f"foundry-workspace: normalized {name}")


def main() -> None:
    normalize()


if __name__ == "__main__":
    main()
