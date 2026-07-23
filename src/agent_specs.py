"""Repository-owned Foundry and Harness instruction loading."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "docs" / "agent-specs"

_INSTRUCTIONS_RE = re.compile(
    r"^##\s+Instructions\s*\n(.*?)(?=^##\s|\Z)",
    re.DOTALL | re.MULTILINE,
)
_MODEL_RE = re.compile(r"^\s*\*\*Model:\*\*", re.MULTILINE)


def parse_agent_instructions(path: pathlib.Path) -> str:
    """Return the repo-owned ``## Instructions`` body from an agent spec."""
    text = path.read_text(encoding="utf-8")
    if _MODEL_RE.search(text):
        raise RuntimeError(
            f"{path.name}: spec contains a '**Model:**' field, which is no "
            "longer allowed. The deployed model is authoritative."
        )
    match = _INSTRUCTIONS_RE.search(text)
    if match is None:
        raise RuntimeError(f"{path.name}: missing '## Instructions' section")
    return match.group(1).strip()
