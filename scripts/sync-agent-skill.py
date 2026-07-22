"""Synchronize the canonical accelerator Agent Skill into Claude's project path."""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / ".agents" / "skills" / "accelerator"
TARGET = ROOT / ".claude" / "skills" / "accelerator"


def sync(*, check: bool = False) -> int:
    if not (SOURCE / "SKILL.md").exists():
        print(f"error: canonical skill missing: {SOURCE / 'SKILL.md'}", file=sys.stderr)
        return 1
    source_files = {
        path.relative_to(SOURCE): path.read_bytes()
        for path in SOURCE.rglob("*")
        if path.is_file()
    }
    target_files = (
        {
            path.relative_to(TARGET): path.read_bytes()
            for path in TARGET.rglob("*")
            if path.is_file()
        }
        if TARGET.exists()
        else {}
    )
    if check:
        if source_files != target_files:
            print(
                "error: .claude/skills/accelerator is not synchronized; run "
                "`python scripts/sync-agent-skill.py`.",
                file=sys.stderr,
            )
            return 1
        print("agent skill adapters are synchronized.")
        return 0

    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, TARGET)
    try:
        display_target = TARGET.relative_to(ROOT)
    except ValueError:
        display_target = TARGET
    print(f"synchronized {len(source_files)} skill file(s) into {display_target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return sync(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
