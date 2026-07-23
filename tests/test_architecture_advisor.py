from __future__ import annotations

import pathlib

import yaml

from src.accelerator_cli.architecture_advisor import (
    architecture_is_current,
    committed_requirement_context,
    recommend_architecture,
    requirements_fingerprint,
    validate_selection,
)
from src.accelerator_cli.intake.ledger import EvidenceLedger
from src.accelerator_cli.lifecycle import detect_lifecycle
from src.accelerator_cli.lifecycle_commands import design
from src.accelerator_cli.protocol import ResultStatus, Stage
from src.accelerator_cli.repository import RepositoryContext


def _brief(body: str, *, pattern: str = "single-agent", ux: str = "API-only / embed") -> str:
    return f"""# Solution Brief — Contoso

## 1. Business context
{body}

## 5. Solution shape
- **Pattern:** {pattern}
- **Rationale:** Customer-approved.

## 5b. UX shape
- **`ux_shape`:** {ux}

## 5c. UX inputs
Defined.

## 5d. UX output sections
Defined.

## 6. Constraints & risks
RAI risks are documented.

## 7. Acceptance evals
Thresholds are approved.
"""


def _context(tmp_path: pathlib.Path, brief: str) -> RepositoryContext:
    (tmp_path / ".git").mkdir()
    path = tmp_path / "docs/discovery/solution-brief.md"
    path.parent.mkdir(parents=True)
    path.write_text(brief, encoding="utf-8")
    (tmp_path / "docs/discovery/use-case-canvas.md").write_text(
        "# Canvas\n**Process:** Approved\n",
        encoding="utf-8",
    )
    (tmp_path / "accelerator.yaml").write_text(
        """
scenario:
  id: demo
  package: src.scenarios.demo
  implementation:
    agent_type: prompt-agent
    orchestration_pattern: single-agent
    application_shell: none
  agents: []
acceptance:
  quality_threshold: 0.8
landing_zone:
  mode: standalone
""".lstrip(),
        encoding="utf-8",
    )
    return RepositoryContext(tmp_path)


def test_simple_knowledge_assistant_recommends_prompt_agent() -> None:
    result = recommend_architecture(
        _brief("A simple FAQ knowledge assistant. It is read-only."),
    )

    assert result.agent_type == "prompt-agent"
    assert result.implementation_pattern == "managed-prompt"
    assert result.orchestration_pattern == "single-agent"
    assert result.application_shell == "none"
    assert result.deployment_target == "foundry-prompt"


def test_existing_langgraph_multi_agent_recommends_hosted_agent() -> None:
    result = recommend_architecture(
        _brief(
            "The customer already has an existing LangGraph multi-agent runtime "
            "with custom dependencies and session state.",
            pattern="supervisor-routing",
            ux="Existing app / dashboard",
        ),
    )

    assert result.agent_type == "hosted-agent"
    assert result.implementation_pattern == "custom-workflow"
    assert result.orchestration_pattern == "supervisor-routing"
    assert result.application_shell == "existing-app"
    assert result.deployment_target == "hosted-preview"
    assert "Existing or required custom agent framework/code" in result.signals


def test_deterministic_approval_flow_is_hosted_workflow() -> None:
    result = recommend_architecture(
        _brief(
            "The process has a deterministic sequence, branching, retries, "
            "and a human approval step before creating a ticket.",
            pattern="deterministic-workflow",
            ux="Structured form + report",
        ),
    )

    assert result.agent_type == "hosted-agent"
    assert result.implementation_pattern == "custom-workflow"
    assert result.orchestration_pattern == "deterministic-workflow"
    assert result.application_shell == "workbench"


def test_prompt_agent_cannot_select_custom_workflow_or_hosted_target() -> None:
    issues = validate_selection(
        agent_type="prompt-agent",
        orchestration_pattern="deterministic-workflow",
        application_shell="none",
        deployment_target="hosted-preview",
    )

    assert len(issues) == 3


def test_autonomous_single_agent_recommends_harness() -> None:
    result = recommend_architecture(
        _brief(
            "A long-running autonomous research assistant plans tasks, keeps "
            "an in-run todo list, and uses custom tools.",
            pattern="single-agent",
        ),
    )

    assert result.agent_type == "hosted-agent"
    assert result.implementation_pattern == "harness"
    assert result.orchestration_pattern == "single-agent"
    assert result.deployment_target == "hosted-preview"


def test_durable_session_state_recommends_custom_workflow() -> None:
    result = recommend_architecture(
        _brief(
            "A single agent must resume durable session state and persistent "
            "files across requests.",
            pattern="single-agent",
        ),
    )

    assert result.agent_type == "hosted-agent"
    assert result.implementation_pattern == "custom-workflow"


def test_fingerprint_uses_approved_statements_without_order_drift() -> None:
    brief = _brief("Approved intent.")
    first = requirements_fingerprint(brief, ("Requirement B", "Requirement A"))
    second = requirements_fingerprint(brief, ("Requirement A", "Requirement B"))

    assert first == second


def test_traceability_links_do_not_change_architecture_fingerprint(
    tmp_path: pathlib.Path,
) -> None:
    traceability = tmp_path / "docs/discovery/requirements-traceability.md"
    traceability.parent.mkdir(parents=True)
    first = (
        "# Requirements traceability\n\n"
        "| Requirement | Category | Status | Evidence | Implementation / evaluation links |\n"
        "|---|---|---|---|---|\n"
        "| `req-1` — Use Entra ID | identity | approved | src-1:c001 | — |\n"
        "| `req-2` — Deferred idea | scope | deferred | src-1:c002 | — |\n"
    )
    traceability.write_text(first, encoding="utf-8")
    initial = requirements_fingerprint(
        "Approved brief",
        committed_requirement_context(tmp_path),
    )

    traceability.write_text(
        first.replace("src-1:c001 | —", "src-2:c099 | quality_eval: `q-1`"),
        encoding="utf-8",
    )
    updated = requirements_fingerprint(
        "Approved brief",
        committed_requirement_context(tmp_path),
    )

    assert committed_requirement_context(tmp_path) == ("Use Entra ID",)
    assert updated == initial


def test_traceability_parser_accepts_common_dash_variants(
    tmp_path: pathlib.Path,
) -> None:
    traceability = tmp_path / "docs/discovery/requirements-traceability.md"
    traceability.parent.mkdir(parents=True)
    traceability.write_text(
        "# Requirements traceability\n\n"
        "| Requirement | Category | Status | Evidence | Implementation / evaluation links |\n"
        "|---|---|---|---|---|\n"
        "| `req-1` — Use Entra ID | identity | approved | — | — |\n"
        "| `req-2` – Require HITL | safety | approved | — | — |\n"
        "| `req-3` - Keep telemetry | operations | approved | — | — |\n",
        encoding="utf-8",
    )

    assert committed_requirement_context(tmp_path) == (
        "Keep telemetry",
        "Require HITL",
        "Use Entra ID",
    )


def test_design_previews_and_applies_recommendation(tmp_path: pathlib.Path) -> None:
    brief = _brief("A simple read-only FAQ assistant.")
    context = _context(tmp_path, brief)

    preview = design(context)
    applied = design(context, approved_by="Partner architect", apply=True)
    manifest = yaml.safe_load(context.manifest_path.read_text(encoding="utf-8"))

    assert preview.status == ResultStatus.APPROVAL_REQUIRED
    assert preview.stage == Stage.DESIGN
    assert preview.details["recommendation"]["agent_type"] == "prompt-agent"
    assert preview.details["recommendation"]["implementation_pattern"] == (
        "managed-prompt"
    )
    assert applied.status == ResultStatus.COMPLETE
    assert manifest["architecture"]["status"] == "approved"
    assert manifest["architecture"]["decision"]["approved_by"] == "Partner architect"
    assert manifest["architecture"]["decision"]["implementation_pattern"] == (
        "managed-prompt"
    )
    assert architecture_is_current(
        manifest["architecture"],
        requirements_fingerprint(brief),
    )


def test_design_requires_override_reason(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path, _brief("A simple read-only FAQ assistant."))

    result = design(
        context,
        agent_type="hosted-agent",
        orchestration_pattern="single-agent",
        application_shell="none",
        deployment_target="hosted-preview",
        approved_by="Partner architect",
        apply=True,
    )

    assert result.status == ResultStatus.NEEDS_INPUT
    assert result.required_inputs[0].id == "override-reason"


def test_design_blocks_when_traceability_export_is_stale(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path, _brief("A simple read-only FAQ assistant."))
    ledger = EvidenceLedger(context)
    requirement = ledger.add_requirement(
        "Use Entra ID for every end user.",
        "identity",
    )
    ledger.decide_requirement(
        requirement.id,
        "approved",
        approved_by="Security Lead",
    )
    traceability = (
        tmp_path / "docs/discovery/requirements-traceability.md"
    )
    traceability.write_text(
        "# Requirements traceability\n\n"
        "| Requirement | Category | Status | Evidence | Implementation / evaluation links |\n"
        "|---|---|---|---|---|\n"
        "| `req-old` — Use API keys | identity | approved | — | — |\n",
        encoding="utf-8",
    )

    result = design(context)

    assert result.status == ResultStatus.NEEDS_INPUT
    assert result.blocking_issues[0].id == "architecture-traceability"
    assert result.next_command == "accel intake requirement export --apply"


def test_design_blocks_when_local_ledger_removes_all_approvals(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path, _brief("A simple read-only FAQ assistant."))
    ledger = EvidenceLedger(context)
    requirement = ledger.add_requirement("Use API keys.", "identity")
    ledger.decide_requirement(requirement.id, "rejected", note="Use Entra ID.")
    traceability = tmp_path / "docs/discovery/requirements-traceability.md"
    traceability.write_text(
        "# Requirements traceability\n\n"
        "| Requirement | Category | Status | Evidence | Implementation / evaluation links |\n"
        "|---|---|---|---|---|\n"
        "| `req-old` — Use API keys | identity | approved | — | — |\n",
        encoding="utf-8",
    )

    result = design(context)

    assert result.status == ResultStatus.NEEDS_INPUT
    assert result.blocking_issues[0].id == "architecture-traceability"


def test_design_trusts_committed_traceability_without_private_ledger(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path, _brief("A simple read-only FAQ assistant."))
    traceability = tmp_path / "docs/discovery/requirements-traceability.md"
    traceability.write_text(
        "# Requirements traceability\n\n"
        "| Requirement | Category | Status | Evidence | Implementation / evaluation links |\n"
        "|---|---|---|---|---|\n"
        "| `req-1` — Use Entra ID | identity | approved | — | — |\n",
        encoding="utf-8",
    )

    result = design(context)

    assert result.status == ResultStatus.APPROVAL_REQUIRED


def test_lifecycle_inserts_design_before_scaffold(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path, _brief("A simple read-only FAQ assistant."))

    lifecycle = detect_lifecycle(context)

    assert lifecycle.current == Stage.DESIGN
    assert lifecycle.for_stage(Stage.DESIGN).status == ResultStatus.READY
