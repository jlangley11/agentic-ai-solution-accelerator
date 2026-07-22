"""Safe subprocess and repository-script helpers for lifecycle commands."""
from __future__ import annotations

import importlib.util
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from .repository import RepositoryContext


@dataclass(frozen=True)
class ProcessResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_process(
    context: RepositoryContext,
    command: list[str],
    *,
    cwd: pathlib.Path | None = None,
    timeout: int = 1800,
) -> ProcessResult:
    executable = _resolve_executable(command[0])
    argv = [executable, *command[1:]]
    completed = subprocess.run(  # noqa: S603 - explicit argv, never shell=True
        argv,
        cwd=cwd or context.root,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return ProcessResult(
        command=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def load_script(
    context: RepositoryContext,
    relative_path: str,
    *,
    module_name: str,
) -> Any:
    path = context.root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load repository script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def python_command(*args: str) -> list[str]:
    return [sys.executable, *args]


def render_command(argv: list[str]) -> str:
    """Render argv for the current host shell without choosing quotes ad hoc."""
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def _resolve_executable(command: str) -> str:
    path = pathlib.Path(command)
    if path.is_absolute() and path.exists():
        return str(path)
    resolved = shutil.which(command)
    if resolved:
        return resolved
    raise FileNotFoundError(f"Executable not found on PATH: {command}")
