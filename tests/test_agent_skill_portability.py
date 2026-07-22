from __future__ import annotations

import importlib.util
import pathlib

import yaml

ROOT = pathlib.Path(__file__).parents[1]
CANONICAL = ROOT / ".agents" / "skills" / "accelerator"
CLAUDE = ROOT / ".claude" / "skills" / "accelerator"
SYNC = ROOT / "scripts" / "sync-agent-skill.py"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_agent_skill", SYNC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_skill_has_required_metadata_and_cli_contract() -> None:
    text = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)

    assert metadata["name"] == "accelerator"
    assert "what to do next" in metadata["description"]
    assert "python -m accelerator_cli --json --pretty next" in body
    assert "local_only" in body
    assert "destructive" in body


def test_claude_skill_adapter_is_generated_from_canonical(tmp_path, monkeypatch) -> None:
    sync = _load_sync()
    target = tmp_path / ".claude" / "skills" / "accelerator"
    monkeypatch.setattr(sync, "TARGET", target)

    assert sync.sync() == 0
    assert (target / "SKILL.md").read_bytes() == (CANONICAL / "SKILL.md").read_bytes()
    assert sync.sync(check=True) == 0


def test_committed_claude_adapter_is_in_sync() -> None:
    canonical_files = {
        path.relative_to(CANONICAL): path.read_bytes()
        for path in CANONICAL.rglob("*")
        if path.is_file()
    }
    claude_files = {
        path.relative_to(CLAUDE): path.read_bytes()
        for path in CLAUDE.rglob("*")
        if path.is_file()
    }

    assert canonical_files == claude_files
