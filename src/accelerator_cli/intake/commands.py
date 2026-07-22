"""CLI-facing document intake operations."""
from __future__ import annotations

import html
import pathlib

from ..lifecycle import detect_lifecycle
from ..protocol import (
    ApprovalLevel,
    Artifact,
    CommandResult,
    Issue,
    ProposedAction,
    ResultStatus,
)
from ..repository import RepositoryContext
from ..runner import render_command
from .extract import extract_document
from .ledger import EvidenceLedger, RequirementRecord


def add(
    context: RepositoryContext,
    paths: list[str],
) -> CommandResult:
    ledger = EvidenceLedger(context)
    added = []
    failures: list[Issue] = []
    for raw_path in paths:
        path = pathlib.Path(raw_path)
        try:
            extraction = extract_document(context, path)
            source = ledger.add_extraction(path.expanduser().resolve(), extraction)
            added.append(source)
        except Exception as exc:  # noqa: BLE001 - report each source independently
            failures.append(
                Issue(
                    f"intake-{len(failures) + 1}",
                    f"{raw_path}: {exc}",
                    "Fix the file or format and re-run `accel intake add`.",
                )
            )
    status = ResultStatus.COMPLETE if added and not failures else ResultStatus.FAILED
    if added and failures:
        status = ResultStatus.BLOCKED
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=status,
        summary=f"Added {len(added)} source document(s) to the local evidence ledger.",
        completed=tuple(
            f"{source.id}: {pathlib.Path(source.source_path).name} "
            f"({source.chunk_count} chunks, local-only)"
            for source in added
        ),
        blocking_issues=tuple(failures),
        artifacts=(
            Artifact(
                "evidence-ledger",
                ".accelerator/private/evidence.db",
                "updated" if added else "unchanged",
                "Local-only; ignored by Git.",
            ),
        ),
        proposed_actions=tuple(
            ProposedAction(
                f"review-{source.id}",
                f"Review {pathlib.Path(source.source_path).name}",
                f"accel intake review {source.id}",
            )
            for source in added
        ),
        next_command="accel intake list",
    )


def list_sources(context: RepositoryContext) -> CommandResult:
    ledger = EvidenceLedger(context)
    sources = ledger.list_sources()
    if not sources:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.NEEDS_INPUT,
            summary="No source documents have been added.",
            next_command="accel intake add <document-path> [<document-path> ...]",
        )
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.READY,
        summary=f"{len(sources)} source document(s) are registered.",
        completed=tuple(
            f"{source.id}: {pathlib.Path(source.source_path).name} "
            f"[{source.disclosure_status}]"
            for source in sources
        ),
        next_command=f"accel intake review {sources[0].id}",
        details=ledger.export_summary(),
    )


def review(
    context: RepositoryContext,
    source_id: str,
    *,
    include_text: bool,
    limit: int = 50,
    offset: int = 0,
) -> CommandResult:
    ledger = EvidenceLedger(context)
    source = ledger.get_source(source_id)
    if include_text and source.disclosure_status != "approved_for_model":
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.BLOCKED,
            summary="Source text remains local-only.",
            blocking_issues=(
                Issue(
                    "source-disclosure",
                    f"{source_id} is {source.disclosure_status}.",
                    "Record an explicit approved_for_model disclosure decision "
                    "before requesting text through an agent-facing command.",
                ),
            ),
            next_command=(
                f"accel intake disclose {source_id} approved_for_model --apply"
            ),
        )
    chunks = ledger.chunks(
        source_id,
        include_text=include_text,
        limit=limit,
        offset=offset,
    )
    truncated = source.chunk_count > offset + len(chunks)
    if truncated:
        next_argv = [
            "accel",
            "intake",
            "review",
            source_id,
            "--limit",
            str(limit),
            "--offset",
            str(offset + len(chunks)),
        ]
        if include_text:
            next_argv.append("--include-text")
        next_command = render_command(next_argv)
    else:
        next_command = (
            f"accel intake disclose {source_id} approved_for_model --apply"
        )
    actions = (
        ProposedAction(
            f"approve-{source_id}",
            "Approve this source for model-assisted requirement extraction",
            f"accel intake disclose {source_id} approved_for_model --apply",
            ApprovalLevel.APPLY,
            "This changes only the local disclosure status; it does not send content.",
        ),
        ProposedAction(
            f"reject-{source_id}",
            "Reject this source",
            f"accel intake disclose {source_id} rejected --apply",
            ApprovalLevel.APPLY,
        ),
    )
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.APPROVAL_REQUIRED,
        summary=(
            f"Review {pathlib.Path(source.source_path).name}: "
            f"returned chunks {offset + 1}-{offset + len(chunks)} of "
            f"{source.chunk_count}, "
            f"disclosure={source.disclosure_status}."
        ),
        proposed_actions=actions,
        next_command=next_command,
        details={
            "source": source.__dict__,
            "chunks": chunks,
            "returned_chunks": len(chunks),
            "total_chunks": source.chunk_count,
            "offset": offset,
            "next_offset": offset + len(chunks) if truncated else None,
            "truncated": truncated,
            "text_included": include_text,
            "warning": (
                "Approving disclosure permits an agent workflow to request these "
                "chunks later; it does not transmit content by itself."
            ),
        },
    )


def disclose(
    context: RepositoryContext,
    source_id: str,
    disclosure_status: str,
    *,
    apply: bool,
) -> CommandResult:
    ledger = EvidenceLedger(context)
    source = ledger.get_source(source_id)
    if not apply:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=(
                f"Disclosure status would change from {source.disclosure_status} "
                f"to {disclosure_status}."
            ),
            proposed_actions=(
                ProposedAction(
                    "apply-disclosure",
                    "Apply disclosure decision",
                    f"accel intake disclose {source_id} {disclosure_status} --apply",
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=(
                f"accel intake disclose {source_id} {disclosure_status} --apply"
            ),
        )
    updated = ledger.set_disclosure(source_id, disclosure_status)
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.COMPLETE,
        summary=(
            f"{pathlib.Path(updated.source_path).name} is now "
            f"{updated.disclosure_status}."
        ),
        completed=(f"Disclosure: {updated.disclosure_status}",),
        next_command="accel intake list",
    )


def requirement_add(
    context: RepositoryContext,
    *,
    statement: str,
    category: str,
    confidence: float | None,
    evidence: list[str],
    apply: bool,
) -> CommandResult:
    parsed_evidence: list[tuple[str, str]] = []
    for reference in evidence:
        if ":" not in reference:
            return CommandResult(
                stage=detect_lifecycle(context).current,
                status=ResultStatus.FAILED,
                summary=f"Invalid evidence reference: {reference!r}.",
                blocking_issues=(
                    Issue(
                        "evidence-reference",
                        "Evidence references must use <source-id>:<chunk-id>.",
                    ),
                ),
            )
        source_id, chunk_id = reference.split(":", 1)
        parsed_evidence.append((source_id, chunk_id))
    command_parts = [
        "accel",
        "intake",
        "requirement",
        "add",
        "--category",
        category,
        "--statement",
        statement,
    ]
    if confidence is not None:
        command_parts.extend(("--confidence", str(confidence)))
    for reference in evidence:
        command_parts.extend(("--evidence", reference))
    command_parts.append("--apply")
    command = render_command(command_parts)
    if not apply:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary="A proposed requirement is ready to record locally.",
            proposed_actions=(
                ProposedAction(
                    "apply-requirement",
                    "Record the proposed requirement and its evidence links",
                    command,
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=command,
            details={
                "statement": statement,
                "category": category,
                "confidence": confidence,
                "evidence": evidence,
            },
        )
    requirement = EvidenceLedger(context).add_requirement(
        statement,
        category,
        confidence=confidence,
        evidence=parsed_evidence,
    )
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.COMPLETE,
        summary=f"Requirement {requirement.id} was recorded as proposed.",
        completed=(requirement.statement,),
        next_command="accel intake requirement list",
        details={"requirement": requirement.__dict__},
    )


def requirement_list(context: RepositoryContext) -> CommandResult:
    requirements = EvidenceLedger(context).list_requirements()
    if not requirements:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.NEEDS_INPUT,
            summary="No structured requirements have been recorded.",
            next_command=(
                "accel intake requirement add --category <category> "
                "--statement <text>"
            ),
        )
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.READY,
        summary=f"{len(requirements)} structured requirement(s) are recorded.",
        completed=tuple(
            f"{requirement.id} [{requirement.status}] "
            f"{requirement.category}: {requirement.statement}"
            for requirement in requirements
        ),
        next_command=(
            f"accel intake requirement decide {requirements[0].id} approved "
            "--by <reviewer> --apply"
        ),
        details={
            "requirements": [
                requirement.__dict__ for requirement in requirements
            ]
        },
    )


def requirement_decide(
    context: RepositoryContext,
    *,
    requirement_id: str,
    status: str,
    approved_by: str | None,
    note: str | None,
    apply: bool,
) -> CommandResult:
    ledger = EvidenceLedger(context)
    requirement = ledger.get_requirement(requirement_id)
    command_parts = [
        "accel",
        "intake",
        "requirement",
        "decide",
        requirement_id,
        status,
    ]
    if approved_by:
        command_parts.extend(("--by", approved_by))
    if note:
        command_parts.extend(("--note", note))
    command_parts.append("--apply")
    command = render_command(command_parts)
    if not apply:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=(
                f"Requirement {requirement_id} would change from "
                f"{requirement.status} to {status}."
            ),
            proposed_actions=(
                ProposedAction(
                    "apply-requirement-decision",
                    "Record the requirement review decision",
                    command,
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=command,
        )
    updated = ledger.decide_requirement(
        requirement_id,
        status,
        approved_by=approved_by,
        note=note,
    )
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.COMPLETE,
        summary=f"Requirement {requirement_id} is now {updated.status}.",
        completed=(updated.statement,),
        next_command="accel intake requirement list",
        details={"requirement": updated.__dict__},
    )


def requirement_link(
    context: RepositoryContext,
    *,
    requirement_id: str,
    link_type: str,
    target: str,
    apply: bool,
) -> CommandResult:
    command = render_command(
        [
            "accel",
            "intake",
            "requirement",
            "link",
            requirement_id,
            "--type",
            link_type,
            "--target",
            target,
            "--apply",
        ]
    )
    ledger = EvidenceLedger(context)
    requirement = ledger.get_requirement(requirement_id)
    if not apply:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=f"Trace link ready for requirement {requirement_id}.",
            proposed_actions=(
                ProposedAction(
                    "apply-requirement-link",
                    "Record the implementation/evaluation trace link",
                    command,
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=command,
            details={
                "requirement": requirement.__dict__,
                "type": link_type,
                "target": target,
            },
        )
    ledger.add_requirement_link(requirement_id, link_type, target)
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.COMPLETE,
        summary=f"Trace link recorded for requirement {requirement_id}.",
        completed=(f"{link_type}: {target}",),
        next_command="accel intake requirement export --apply",
    )


def requirement_export(
    context: RepositoryContext,
    *,
    apply: bool,
) -> CommandResult:
    ledger = EvidenceLedger(context)
    requirements = ledger.list_requirements()
    markdown = _traceability_markdown(ledger, requirements)
    output = context.root / "docs" / "discovery" / "requirements-traceability.md"
    if not apply:
        return CommandResult(
            stage=detect_lifecycle(context).current,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=f"Traceability report ready for {len(requirements)} requirement(s).",
            proposed_actions=(
                ProposedAction(
                    "apply-traceability",
                    "Write the sanitized traceability report",
                    "accel intake requirement export --apply",
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command="accel intake requirement export --apply",
            details={"preview": markdown[:8000]},
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return CommandResult(
        stage=detect_lifecycle(context).current,
        status=ResultStatus.COMPLETE,
        summary="Requirements traceability report generated.",
        artifacts=(
            Artifact(
                "requirements-traceability",
                context.relative(output),
                "created",
            ),
        ),
        next_command="accel next",
    )


def _traceability_markdown(
    ledger: EvidenceLedger,
    requirements: list[RequirementRecord],
) -> str:
    lines = [
        "# Requirements traceability",
        "",
        "> Generated from the local evidence ledger. Source excerpts remain in",
        "> `.accelerator/private/evidence.db`; this report contains references only.",
        "",
        "| Requirement | Category | Status | Evidence | Implementation / evaluation links |",
        "|---|---|---|---|---|",
    ]
    for requirement in requirements:
        evidence = "<br>".join(
            _markdown_cell(item)
            for item in ledger.requirement_evidence(requirement.id)
        ) or "—"
        links = "<br>".join(
            f"{_markdown_cell(link['type'])}: "
            f"`{_markdown_cell(link['target'])}`"
            for link in ledger.requirement_links(requirement.id)
        ) or "—"
        statement = _markdown_cell(requirement.statement)
        lines.append(
            f"| `{requirement.id}` — {statement} | "
            f"{_markdown_cell(requirement.category)} | "
            f"{_markdown_cell(requirement.status)} | {evidence} | {links} |"
        )
    return "\n".join(lines) + "\n"


def _markdown_cell(value: str) -> str:
    return (
        html.escape(value, quote=True)
        .replace("|", "&#124;")
        .replace("`", "&#96;")
        .replace("\n", " ")
    )
