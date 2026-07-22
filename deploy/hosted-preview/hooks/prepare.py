"""Stage the repository package inside the hosted-agent project boundary."""

from __future__ import annotations

import shutil
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKSPACE_ROOT.parents[1]

_IGNORED_NAMES = {
    ".azure",
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "venv",
}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _ignore_generated(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if (
            name in _IGNORED_NAMES
            or name.startswith(".env.")
            or Path(name).suffix in _IGNORED_SUFFIXES
        )
    }


def prepare(
    *,
    repo_root: Path = REPO_ROOT,
    workspace_root: Path = WORKSPACE_ROOT,
) -> None:
    """Replace generated app/src and copy the exact package inputs."""
    repo = repo_root.resolve(strict=True)
    workspace = workspace_root.resolve(strict=True)
    app = (workspace / "app").resolve(strict=True)
    source = (repo / "src").resolve(strict=True)
    staged_source = (app / "src").resolve()

    if workspace.parent.name != "deploy" or workspace.name != "hosted-preview":
        raise RuntimeError(f"unexpected hosted workspace path: {workspace}")
    if source.parent != repo:
        raise RuntimeError(f"source path escaped repository root: {source}")
    if staged_source.parent != app:
        raise RuntimeError(f"staged source path escaped app directory: {staged_source}")

    metadata_files = ("accelerator.yaml", "pyproject.toml", "README.md")
    required = [source, *(repo / name for name in metadata_files)]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"hosted preview staging inputs missing: {missing}")
    linked = [str(path) for path in source.rglob("*") if path.is_symlink()]
    if linked:
        raise RuntimeError(f"hosted preview source must not contain symlinks: {linked}")

    if staged_source.exists():
        if not staged_source.is_dir():
            raise RuntimeError(f"generated source path is not a directory: {staged_source}")
        shutil.rmtree(staged_source)

    shutil.copytree(source, staged_source, ignore=_ignore_generated)
    for name in metadata_files:
        shutil.copy2(repo / name, app / name)


def main() -> None:
    prepare()


if __name__ == "__main__":
    main()
