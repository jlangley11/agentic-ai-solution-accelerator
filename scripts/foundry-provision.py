"""Provision Foundry, FoundryIQ, and AI Search resources before hosting."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import pathlib
import re
import sys
from collections.abc import MutableMapping, Sequence

ROOT = pathlib.Path(__file__).resolve().parent.parent
_ENV_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _decode_quoted_value(
    value: str,
    *,
    path: pathlib.Path,
    line_number: int,
) -> str:
    """Decode the quoted subset emitted by azd/godotenv."""
    quote = value[0]
    decoded: list[str] = []
    double_escapes = {
        "\\": "\\",
        '"': '"',
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "$": "$",
        "!": "!",
        "`": "`",
    }
    single_escapes = {"\\": "\\", "'": "'"}
    escapes = double_escapes if quote == '"' else single_escapes

    index = 1
    while index < len(value):
        char = value[index]
        if char == quote:
            if index != len(value) - 1:
                raise ValueError(
                    f"{path}:{line_number}: characters after quoted environment value"
                )
            return "".join(decoded)
        if char != "\\":
            decoded.append(char)
            index += 1
            continue

        index += 1
        if index >= len(value):
            break
        escaped = value[index]
        replacement = escapes.get(escaped)
        if replacement is None:
            decoded.extend(("\\", escaped))
        else:
            decoded.append(replacement)
        index += 1

    raise ValueError(f"{path}:{line_number}: unterminated quoted environment value")


def parse_env_file(path: pathlib.Path) -> dict[str, str]:
    """Parse a strict azd ``.env`` file."""
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"{path}:{line_number}: malformed environment line")
        key, raw_value = match.groups()
        value = raw_value.strip()
        if value.startswith(("'", '"')):
            value = _decode_quoted_value(
                value,
                path=path,
                line_number=line_number,
            )
        values[key] = value
    return values


def select_env_file(
    env_name: str | None,
    *,
    root: pathlib.Path = ROOT,
    environ: MutableMapping[str, str] | None = None,
) -> pathlib.Path | None:
    """Select one azd environment file without guessing among multiple envs."""
    current = os.environ if environ is None else environ
    selected_name = env_name or current.get("AZURE_ENV_NAME") or current.get("AZD_ENV_NAME")
    azure_root = root / ".azure"

    if selected_name:
        selected = azure_root / selected_name / ".env"
        if not selected.is_file():
            raise FileNotFoundError(
                f"azd environment {selected_name!r} has no env file at {selected}; "
                "pass --env with a valid environment name"
            )
        return selected

    candidates = sorted(azure_root.glob("*/.env")) if azure_root.is_dir() else []
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        names = ", ".join(path.parent.name for path in candidates)
        raise RuntimeError(
            f"multiple azd environments found ({names}); pass --env <azd-env>"
        )
    return None


def load_environment(
    env_name: str | None,
    *,
    root: pathlib.Path = ROOT,
    environ: MutableMapping[str, str] | None = None,
) -> pathlib.Path | None:
    """Load the selected azd env while preserving process-environment values."""
    current = os.environ if environ is None else environ
    path = select_env_file(env_name, root=root, environ=current)
    if path is None:
        return None
    for key, value in parse_env_file(path).items():
        current.setdefault(key, value)
    return path


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", dest="env_name", metavar="AZD_ENV")
    parser.add_argument(
        "--canary",
        action="store_true",
        help="run retrieval canaries after provisioning",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="create/update Search schemas without embedding or uploading seed documents",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Load configuration and run the provisioner. Errors intentionally propagate."""
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    load_environment(args.env_name)

    from src.provisioning import provision
    from src.workflow.registry import load_scenario

    bundle = load_scenario()
    asyncio.run(
        provision(
            bundle,
            skip_seed=args.skip_seed,
            canary=args.canary,
        )
    )


if __name__ == "__main__":
    main()
