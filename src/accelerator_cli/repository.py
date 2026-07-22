"""Repository access helpers with no cloud or model dependencies."""
from __future__ import annotations

import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class RepositoryContext:
    root: pathlib.Path

    @classmethod
    def discover(cls, start: pathlib.Path | None = None) -> "RepositoryContext":
        current = (start or pathlib.Path.cwd()).resolve()
        for candidate in (current, *current.parents):
            if (candidate / "accelerator.yaml").exists() and (candidate / ".git").exists():
                return cls(candidate)
        raise RuntimeError(
            "Could not find the accelerator repository root. Run this command "
            "inside a clone containing accelerator.yaml and .git."
        )

    @property
    def manifest_path(self) -> pathlib.Path:
        return self.root / "accelerator.yaml"

    @property
    def brief_path(self) -> pathlib.Path:
        return self.root / "docs" / "discovery" / "solution-brief.md"

    @property
    def private_dir(self) -> pathlib.Path:
        return self.root / ".accelerator" / "private"

    @property
    def artifacts_dir(self) -> pathlib.Path:
        return self.root / ".accelerator" / "artifacts"

    @property
    def operations_path(self) -> pathlib.Path:
        return self.root / ".accelerator" / "operations.jsonl"

    def load_yaml(self, relative: str | pathlib.Path) -> dict[str, Any]:
        path = self.root / relative
        if not path.exists():
            return {}
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}

    def manifest(self) -> dict[str, Any]:
        return self.load_yaml("accelerator.yaml")

    def read_text(self, relative: str | pathlib.Path) -> str:
        path = self.root / relative
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def relative(self, path: pathlib.Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def git_changes(self) -> tuple[str, ...]:
        git = shutil.which("git")
        if not git:
            return ()
        try:
            completed = subprocess.run(  # noqa: S603 - resolved git executable
                [git, "--no-pager", "status", "--short"],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ()
        return tuple(line for line in completed.stdout.splitlines() if line.strip())
