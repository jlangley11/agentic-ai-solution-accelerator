from __future__ import annotations

import pathlib

from src.accelerator_cli.repository import RepositoryContext
from src.accelerator_mcp.api import AcceleratorApi


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


def test_mcp_api_reuses_versioned_cli_contract(tmp_path: pathlib.Path) -> None:
    payload = AcceleratorApi(_context(tmp_path)).next()

    assert payload["schema_version"] == "1.0"
    assert payload["stage"] == "qualify"
    assert payload["status"] == "needs_input"


def test_mcp_deploy_defaults_to_non_executing_plan(
    tmp_path: pathlib.Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path)
    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy/environments.yaml").write_text(
        "default_env: dev\n"
        "environments:\n"
        "  - name: dev\n"
        "    github_environment: dev\n"
        "    deployment_target: selfhost\n",
        encoding="utf-8",
    )
    called = []
    monkeypatch.setattr(
        "src.accelerator_cli.lifecycle_commands.run_process",
        lambda *_args, **_kwargs: called.append(True),
    )

    payload = AcceleratorApi(context).deploy("dev", "eastus2")

    assert payload["status"] == "approval_required"
    assert called == []


def test_mcp_mutation_records_operation(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    source = tmp_path / "source.csv"
    source.write_text("id,requirement\nR1,Use Entra ID\n", encoding="utf-8")
    from src.accelerator_cli.intake.extract import extract_document
    from src.accelerator_cli.intake.ledger import EvidenceLedger

    registered = EvidenceLedger(context).add_extraction(
        source,
        extract_document(context, source),
    )

    AcceleratorApi(context).intake_disclose(
        registered.id,
        "approved_for_model",
        apply=True,
    )

    journal = context.operations_path.read_text(encoding="utf-8")
    assert "mcp.intake_disclose" in journal


def test_mcp_disclosure_preview_does_not_mutate_or_journal(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    source = tmp_path / "source.csv"
    source.write_text("id,requirement\nR1,Use Entra ID\n", encoding="utf-8")
    from src.accelerator_cli.intake.extract import extract_document
    from src.accelerator_cli.intake.ledger import EvidenceLedger

    ledger = EvidenceLedger(context)
    registered = ledger.add_extraction(source, extract_document(context, source))
    operations_before = context.operations_path.read_text(encoding="utf-8") \
        if context.operations_path.exists() else ""

    result = AcceleratorApi(context).intake_disclose(
        registered.id,
        "approved_for_model",
        apply=False,
    )

    assert result["status"] == "approval_required"
    assert ledger.get_source(registered.id).disclosure_status == "local_only"
    operations_after = context.operations_path.read_text(encoding="utf-8") \
        if context.operations_path.exists() else ""
    assert operations_after == operations_before
