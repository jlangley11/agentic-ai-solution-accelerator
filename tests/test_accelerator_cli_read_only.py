from __future__ import annotations

import pathlib

from src.accelerator_cli import main as cli_main
from src.accelerator_cli.intake.ledger import EvidenceLedger
from src.accelerator_cli.lifecycle_commands import migrate
from src.accelerator_cli.repository import RepositoryContext


def _context(tmp_path: pathlib.Path) -> RepositoryContext:
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs/discovery").mkdir(parents=True)
    (tmp_path / "docs/discovery/solution-brief.md").write_text(
        "# Brief\n> **STATUS: TEMPLATE.**\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/discovery/use-case-canvas.md").write_text(
        "# Canvas\n<Customer>\n**Process:** …\n",
        encoding="utf-8",
    )
    (tmp_path / "accelerator.yaml").write_text(
        "scenario:\n  id: demo\n  package: src.scenarios.demo\n  agents: []\n",
        encoding="utf-8",
    )
    return RepositoryContext(tmp_path)


def test_read_only_ledger_queries_do_not_create_private_state(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    ledger = EvidenceLedger(context)

    assert ledger.list_sources() == []
    assert ledger.list_requirements() == []
    assert not context.private_dir.exists()


def test_migration_preview_does_not_create_local_state(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)

    migrate(context, apply=False)

    assert not context.private_dir.exists()
    assert not context.artifacts_dir.exists()


def test_status_command_does_not_create_operation_journal(
    tmp_path: pathlib.Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path)
    monkeypatch.setattr(
        RepositoryContext,
        "discover",
        classmethod(lambda cls, start=None: context),
    )

    cli_main.main(["--json", "status"])

    assert not (context.root / ".accelerator").exists()
