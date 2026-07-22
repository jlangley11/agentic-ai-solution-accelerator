"""Install deterministic local dependencies for the Hosted Agents preview."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = WORKSPACE_ROOT.parents[1]


def bootstrap(
    *,
    repo_root: pathlib.Path = REPO_ROOT,
    python_executable: str = sys.executable,
) -> None:
    repo = repo_root.resolve(strict=True)
    if not (repo / "pyproject.toml").is_file():
        raise FileNotFoundError(f"hosted preview root pyproject.toml missing: {repo}")
    pip_available = subprocess.run(  # noqa: S603 - trusted interpreter
        [python_executable, "-m", "pip", "--version"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0
    if pip_available:
        command = [
            python_executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-e",
            ".[hosted-preview]",
        ]
    else:
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError(
                "the selected Python has no pip module and uv is not available on PATH"
            )
        command = [
            uv,
            "pip",
            "install",
            "--python",
            python_executable,
            "-e",
            ".[hosted-preview]",
        ]
    subprocess.run(  # noqa: S603 - current interpreter installs the trusted repository
        command,
        cwd=repo,
        check=True,
    )


def main() -> None:
    bootstrap()


if __name__ == "__main__":
    main()
