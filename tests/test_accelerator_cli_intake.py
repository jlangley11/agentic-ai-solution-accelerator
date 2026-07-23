from __future__ import annotations

import pathlib

import pytest

from src.accelerator_cli.intake.commands import (
    requirement_add,
    requirement_decide,
    requirement_export,
    review,
)
from src.accelerator_cli.intake.extract import extract_document
from src.accelerator_cli.intake.ledger import EvidenceLedger
from src.accelerator_cli.protocol import ResultStatus
from src.accelerator_cli.repository import RepositoryContext
from src.accelerator_cli.runner import render_command


def _context(tmp_path: pathlib.Path) -> RepositoryContext:
    (tmp_path / ".git").mkdir()
    (tmp_path / "scripts").mkdir()
    return RepositoryContext(tmp_path)


def test_csv_intake_is_local_only_and_deduplicated(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    source = tmp_path / "requirements.csv"
    source.write_text(
        "id,requirement\nR1,Keep customer data in the EU\n",
        encoding="utf-8",
    )
    extraction = extract_document(context, source)
    ledger = EvidenceLedger(context)

    first = ledger.add_extraction(source, extraction)
    second = ledger.add_extraction(source, extraction)

    assert first.id == second.id
    assert second.disclosure_status == "local_only"
    assert second.chunk_count == 2
    assert len(ledger.list_sources()) == 1
    assert context.private_dir.joinpath("evidence.db").exists()


def test_disclosure_requires_explicit_ledger_update(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    source = tmp_path / "requirements.csv"
    source.write_text("id,requirement\nR1,Use Entra ID\n", encoding="utf-8")
    ledger = EvidenceLedger(context)
    registered = ledger.add_extraction(source, extract_document(context, source))

    with pytest.raises(PermissionError, match="approve it"):
        ledger.chunks(registered.id, include_text=True)
    blocked = review(context, registered.id, include_text=True)
    assert blocked.status.value == "blocked"

    updated = ledger.set_disclosure(registered.id, "approved_for_model")

    assert updated.disclosure_status == "approved_for_model"
    assert ledger.chunks(registered.id, include_text=True)[0]["text"]
    ledger.set_disclosure(registered.id, "local_only")
    with pytest.raises(PermissionError, match="local_only"):
        ledger.chunks(registered.id, include_text=True)


@pytest.mark.parametrize(
    "status",
    (
        "",
        "APPROVED_FOR_MODEL",
        "approved_for_model'; DROP TABLE sources; --",
        "approved_for_model\x00OR 1=1",
        'approved_for_model") UNION SELECT 1 --',
    ),
)
def test_disclosure_rejects_invalid_or_injection_shaped_status(
    tmp_path: pathlib.Path,
    status: str,
) -> None:
    context = _context(tmp_path)
    source = tmp_path / "requirements.csv"
    source.write_text("id,requirement\nR1,Use Entra ID\n", encoding="utf-8")
    ledger = EvidenceLedger(context)
    registered = ledger.add_extraction(source, extract_document(context, source))

    with pytest.raises(ValueError, match="Unsupported disclosure status"):
        ledger.set_disclosure(registered.id, status)

    assert ledger.get_source(registered.id).disclosure_status == "local_only"


def test_duplicate_chunks_are_reported_across_sources(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    ledger = EvidenceLedger(context)
    for index, name in enumerate(("one.csv", "two.csv"), start=1):
        source = tmp_path / name
        source.write_text(
            "id,requirement\n"
            "R1,Use managed identity\n"
            f"R{index + 1},Unique requirement {index}\n",
            encoding="utf-8",
        )
        ledger.add_extraction(source, extract_document(context, source))

    groups = ledger.duplicate_groups()

    assert groups
    assert any(group["count"] == 2 for group in groups)


def test_requirement_records_evidence_and_review_decision(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    source = tmp_path / "requirements.csv"
    source.write_text("id,requirement\nR1,Use Entra ID\n", encoding="utf-8")
    ledger = EvidenceLedger(context)
    registered = ledger.add_extraction(source, extract_document(context, source))
    with pytest.raises(PermissionError, match="approve it"):
        ledger.add_requirement(
            "Use Entra ID for end-user authentication.",
            "identity",
            evidence=[(registered.id, "c001")],
        )
    ledger.set_disclosure(registered.id, "approved_for_model")

    requirement = ledger.add_requirement(
        "Use Entra ID for end-user authentication.",
        "identity",
        confidence=0.95,
        evidence=[(registered.id, "c001")],
    )
    approved = ledger.decide_requirement(
        requirement.id,
        "approved",
        approved_by="Customer security lead",
    )
    ledger.add_requirement_link(
        approved.id,
        "quality_eval",
        "evals/quality/golden_cases.jsonl#q-001",
    )

    assert approved.status == "approved"
    assert approved.approved_by == "Customer security lead"
    assert approved.approved_at is not None
    assert ledger.requirement_links(approved.id) == [
        {
            "type": "quality_eval",
            "target": "evals/quality/golden_cases.jsonl#q-001",
        }
    ]


def test_requirement_preview_preserves_confidence_and_evidence(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)

    result = requirement_add(
        context,
        statement="Use Entra ID.",
        category="identity",
        confidence=0.91,
        evidence=["src-123:c001"],
        apply=False,
    )

    assert result.status == ResultStatus.APPROVAL_REQUIRED
    assert result.next_command == render_command(
        [
            "accel",
            "intake",
            "requirement",
            "add",
            "--category",
            "identity",
            "--statement",
            "Use Entra ID.",
            "--confidence",
            "0.91",
            "--evidence",
            "src-123:c001",
            "--apply",
        ]
    )


def test_intake_review_reports_truncation(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    source = tmp_path / "large.csv"
    source.write_text(
        "id,requirement\n"
        + "\n".join(f"R{index},Requirement {index}" for index in range(60)),
        encoding="utf-8",
    )
    ledger = EvidenceLedger(context)
    registered = ledger.add_extraction(source, extract_document(context, source))

    result = review(context, registered.id, include_text=False, limit=10)

    assert result.details["truncated"] is True
    assert result.details["returned_chunks"] == 10
    assert result.details["total_chunks"] == 61
    assert result.details["next_offset"] == 10
    second_page = review(
        context,
        registered.id,
        include_text=False,
        limit=20,
        offset=50,
    )
    assert second_page.details["returned_chunks"] == 11
    assert second_page.details["truncated"] is False
    ledger.set_disclosure(registered.id, "approved_for_model")
    text_page = review(
        context,
        registered.id,
        include_text=True,
        limit=10,
    )
    assert "--include-text" in text_page.next_command


def test_requirement_decision_command_uses_host_shell_quoting(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    ledger = EvidenceLedger(context)
    requirement = ledger.add_requirement("Use Entra ID.", "identity")

    result = requirement_decide(
        context,
        requirement_id=requirement.id,
        status="deferred",
        approved_by="O'Brien Reviewer",
        note="needs review before Q4",
        apply=False,
    )

    assert result.next_command == render_command(
        [
            "accel",
            "intake",
            "requirement",
            "decide",
            requirement.id,
            "deferred",
            "--by",
            "O'Brien Reviewer",
            "--note",
            "needs review before Q4",
            "--apply",
        ]
    )


def test_traceability_export_escapes_untrusted_markdown_html(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    ledger = EvidenceLedger(context)
    requirement = ledger.add_requirement(
        "<script>alert('x')</script> | enforce auth",
        "security",
    )
    ledger.add_requirement_link(
        requirement.id,
        "decision",
        "</code><script>alert(2)</script>",
    )

    requirement_export(context, apply=True)
    report = (
        context.root / "docs/discovery/requirements-traceability.md"
    ).read_text(encoding="utf-8")

    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "&#124;" in report
