"""Run shared scenario provisioning after the hosted agent is deployed."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Coroutine

REPO_ROOT = Path(__file__).resolve().parents[3]
_TRUE_VALUES = {"1", "true", "yes", "on"}


def canary_enabled(environ: Mapping[str, str] = os.environ) -> bool:
    raw = environ.get("HOSTED_PREVIEW_CANARY", environ.get("BOOTSTRAP_CANARY", ""))
    return raw.strip().lower() in _TRUE_VALUES


def run(
    provision_fn: Callable[..., Coroutine[Any, Any, None]],
    load_scenario_fn: Callable[[], object],
    *,
    environ: Mapping[str, str] = os.environ,
) -> None:
    bundle = load_scenario_fn()
    asyncio.run(provision_fn(bundle, canary=canary_enabled(environ)))


def main() -> None:
    repo = REPO_ROOT.resolve(strict=True)
    if repo.name == "hosted-preview" or not (repo / "src" / "provisioning.py").is_file():
        raise RuntimeError(f"could not resolve accelerator repository root: {repo}")
    sys.path.insert(0, str(repo))

    from src.provisioning import provision
    from src.workflow.registry import load_scenario

    run(provision, load_scenario)


if __name__ == "__main__":
    main()
