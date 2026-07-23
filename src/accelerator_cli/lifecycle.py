"""Derive accelerator lifecycle state from persistent repository artifacts."""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any

from src.implementation_patterns import legacy_implementation_pattern_for

from .architecture_advisor import (
    architecture_is_current,
    committed_requirement_context,
    has_unresolved_markers,
    recommend_architecture,
    validate_selection,
)
from .intake.ledger import EvidenceLedger
from .protocol import STAGE_ORDER, Issue, ResultStatus, Stage, StageSummary
from .repository import RepositoryContext

_UNRESOLVED_MARKERS = (
    "STATUS: TEMPLATE",
    "STATUS: AI-extracted draft",
    "<Customer>",
    "<customer-slug>",
    "[PARTNER-FILL",
    "<!-- FILL IN:",
    "TBD",
    "TODO:",
)
_DEPLOYMENT_TARGETS = {"selfhost", "foundry-prompt", "hosted-preview"}


@dataclass(frozen=True)
class LifecycleState:
    current: Stage
    stages: tuple[StageSummary, ...]

    def for_stage(self, stage: Stage) -> StageSummary:
        return next(item for item in self.stages if item.stage == stage)


def detect_lifecycle(context: RepositoryContext) -> LifecycleState:
    manifest = context.manifest()
    brief = context.brief_path.read_text(encoding="utf-8") if context.brief_path.exists() else ""
    stage_checks = {
        Stage.QUALIFY: _detect_qualify(context, brief),
        Stage.DISCOVER: _detect_discover(context, brief),
        Stage.DESIGN: _detect_design(context, manifest, brief),
        Stage.SCAFFOLD: _detect_scaffold(context, manifest),
        Stage.PROVISION: _detect_provision(context),
        Stage.ITERATE: _detect_iterate(context, manifest),
        Stage.UAT: _detect_uat(context),
        Stage.HANDOVER: _detect_handover(context),
        Stage.OPERATE: _detect_operate(context),
    }
    stages = tuple(stage_checks[stage] for stage in STAGE_ORDER)
    current = next(
        (
            item.stage
            for item in stages
            if item.status not in {ResultStatus.COMPLETE}
        ),
        Stage.OPERATE,
    )
    return LifecycleState(current=current, stages=stages)


def _detect_qualify(context: RepositoryContext, brief: str) -> StageSummary:
    canvas = context.read_text("docs/discovery/use-case-canvas.md")
    if "STATUS: TEMPLATE" not in brief and brief:
        return StageSummary(
            Stage.QUALIFY,
            ResultStatus.COMPLETE,
            "Engagement has progressed beyond template qualification.",
            ("Customer engagement brief exists",),
        )
    unresolved = any(
        token in canvas
        for token in ("<Customer>", "<customer-slug>", "**Process:** …")
    )
    if unresolved:
        return StageSummary(
            Stage.QUALIFY,
            ResultStatus.NEEDS_INPUT,
            "The shipped qualification canvas is still a template.",
            issues=(
                Issue(
                    "qualification-canvas",
                    "Use-case canvas has not been completed for a customer.",
                    "Run `accel discover` or complete docs/discovery/use-case-canvas.md.",
                    "docs/discovery/use-case-canvas.md",
                ),
            ),
        )
    return StageSummary(
        Stage.QUALIFY,
        ResultStatus.COMPLETE,
        "Use-case qualification is complete.",
        ("Use-case canvas completed",),
    )


def _detect_discover(context: RepositoryContext, brief: str) -> StageSummary:
    if not brief:
        return StageSummary(
            Stage.DISCOVER,
            ResultStatus.BLOCKED,
            "The canonical solution brief is missing.",
            issues=(
                Issue(
                    "brief-missing",
                    "docs/discovery/solution-brief.md does not exist.",
                    "Restore the template or run `accel discover`.",
                    "docs/discovery/solution-brief.md",
                ),
            ),
        )
    markers = tuple(marker for marker in _UNRESOLVED_MARKERS if marker in brief)
    if markers:
        return StageSummary(
            Stage.DISCOVER,
            ResultStatus.NEEDS_INPUT,
            "Discovery is incomplete.",
            issues=tuple(
                Issue(
                    f"brief-marker-{index}",
                    f"Unresolved marker remains: {marker}",
                    "Review the brief or continue the guided discovery workflow.",
                    "docs/discovery/solution-brief.md",
                )
                for index, marker in enumerate(markers, start=1)
            ),
        )
    return StageSummary(
        Stage.DISCOVER,
        ResultStatus.COMPLETE,
        "The solution brief is complete.",
        ("Solution brief contains no unresolved markers",),
    )


def _detect_scaffold(
    context: RepositoryContext,
    manifest: dict[str, Any],
) -> StageSummary:
    scenario = manifest.get("scenario") or {}
    package = scenario.get("package")
    if not isinstance(package, str) or not package:
        return StageSummary(
            Stage.SCAFFOLD,
            ResultStatus.BLOCKED,
            "The manifest does not declare a scenario package.",
            issues=(
                Issue(
                    "scenario-package",
                    "accelerator.yaml scenario.package is missing.",
                    "Run `accel scaffold --scenario-id <id> --dry-run`.",
                    "accelerator.yaml",
                ),
            ),
        )
    package_path = context.root.joinpath(*package.split("."))
    required = [
        package_path / "schema.py",
        package_path / "workflow.py",
        package_path / "agents",
    ]
    issues: list[Issue] = []
    diagram_path: str | None = None
    diagram = scenario.get("architecture_diagram")
    if not isinstance(diagram, dict):
        issues.append(Issue(
            "scaffold-architecture-diagram",
            "scenario.architecture_diagram is missing.",
            "Re-run scaffold preview/apply, then generate the diagram through "
            "Azure Architecture Diagram Builder MCP.",
            "accelerator.yaml",
        ))
    else:
        if diagram.get("generator") != "azure-architecture-diagram-builder-mcp":
            issues.append(Issue(
                "scaffold-architecture-diagram-generator",
                "scenario.architecture_diagram.generator is not the Azure "
                "Architecture Diagram Builder MCP.",
                "Set generator to azure-architecture-diagram-builder-mcp.",
                "accelerator.yaml",
            ))
        if diagram.get("version") != "1.0.0":
            issues.append(Issue(
                "scaffold-architecture-diagram-version",
                "scenario.architecture_diagram.version is not pinned to 1.0.0.",
                "Regenerate with Azure Architecture Diagram Builder MCP v1.0.0.",
                "accelerator.yaml",
            ))
        tools = diagram.get("tools")
        required_tools = {
            "list_services",
            "validate_architecture",
            "render_diagram",
        }
        if (
            not isinstance(tools, list)
            or not all(isinstance(tool, str) for tool in tools)
            or not required_tools.issubset(set(tools))
        ):
            issues.append(Issue(
                "scaffold-architecture-diagram-tools",
                "scenario.architecture_diagram.tools does not record the "
                "required MCP sequence.",
                f"Include {sorted(required_tools)}.",
                "accelerator.yaml",
            ))
        for field in ("path", "provenance"):
            value = diagram.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(Issue(
                    f"scaffold-architecture-diagram-{field}",
                    f"scenario.architecture_diagram.{field} is missing.",
                    "Set the MCP-generated diagram and provenance paths.",
                    "accelerator.yaml",
                ))
                continue
            candidate = pathlib.PurePosixPath(value)
            expected_suffix = ".svg" if field == "path" else ".json"
            if (
                candidate.is_absolute()
                or ".." in candidate.parts
                or candidate.suffix != expected_suffix
                or candidate.parts[:3] != ("docs", "assets", "diagrams")
            ):
                issues.append(Issue(
                    f"scaffold-architecture-diagram-{field}",
                    f"scenario.architecture_diagram.{field} is outside the "
                    "governed diagrams directory.",
                    f"Use a {expected_suffix} path under docs/assets/diagrams/.",
                    "accelerator.yaml",
                ))
                continue
            if field == "path":
                diagram_path = value
            required.append(context.root.joinpath(*candidate.parts))

    missing = tuple(path for path in required if not path.exists())
    agent_specs_missing: list[pathlib.Path] = []
    for raw in scenario.get("agents") or []:
        if not isinstance(raw, dict):
            continue
        foundry_name = raw.get("foundry_name")
        if isinstance(foundry_name, str):
            spec = context.root / "docs" / "agent-specs" / f"{foundry_name}.md"
            if not spec.exists():
                agent_specs_missing.append(spec)
    for index, path in enumerate((*missing, *agent_specs_missing), start=1):
        is_diagram = path.suffix in {".svg", ".json"} and (
            "diagrams" in path.parts
        )
        issues.append(Issue(
            f"scaffold-{index}",
            f"Required scaffold artifact is missing: {context.relative(path)}",
            (
                "Generate the SVG and checksum-bound provenance through Azure "
                "Architecture Diagram Builder MCP."
                if is_diagram
                else "Run the corresponding `accel scaffold` or worker command."
            ),
            context.relative(path),
        ))
    if issues:
        return StageSummary(
            Stage.SCAFFOLD,
            ResultStatus.BLOCKED,
            "The scenario scaffold is incomplete.",
            issues=tuple(issues),
        )
    assert diagram_path is not None
    return StageSummary(
        Stage.SCAFFOLD,
        ResultStatus.COMPLETE,
        f"Scenario package {package!r} is materialized.",
        (
            f"Scenario package: {package}",
            f"Registered agents: {len(scenario.get('agents') or [])}",
            f"Architecture diagram: {diagram_path}",
        ),
    )


def _detect_design(
    context: RepositoryContext,
    manifest: dict[str, Any],
    brief: str,
) -> StageSummary:
    if not brief or has_unresolved_markers(brief):
        return StageSummary(
            Stage.DESIGN,
            ResultStatus.BLOCKED,
            "Architecture advice waits for approved discovery intent.",
            issues=(
                Issue(
                    "architecture-discovery",
                    "The solution brief is incomplete.",
                    "Complete discovery before selecting an agent architecture.",
                    "docs/discovery/solution-brief.md",
                ),
            ),
        )
    ledger = EvidenceLedger(context)
    local_requirements = tuple(
        requirement.statement
        for requirement in ledger.list_requirements()
        if requirement.status == "approved"
    )
    traceability = (
        context.root / "docs" / "discovery" / "requirements-traceability.md"
    )
    committed_requirements = committed_requirement_context(
        context.root,
        local_requirements,
    )
    local_normalized = {" ".join(statement.split()) for statement in local_requirements}
    committed_normalized = {
        " ".join(statement.split()) for statement in committed_requirements
    }
    if (
        local_requirements
        and not traceability.exists()
    ) or (
        ledger.path.exists()
        and traceability.exists()
        and local_normalized != committed_normalized
    ):
        return StageSummary(
            Stage.DESIGN,
            ResultStatus.BLOCKED,
            "Approved requirements must be re-exported before architecture review.",
            issues=(
                Issue(
                    "architecture-traceability",
                    "The local approved requirements and committed sanitized "
                    "traceability export do not match.",
                    "Run `accel intake requirement export --apply`.",
                    "docs/discovery/requirements-traceability.md",
                ),
            ),
        )
    recommendation = recommend_architecture(
        brief,
        committed_requirements,
    )
    architecture = manifest.get("architecture")
    if not isinstance(architecture, dict):
        return StageSummary(
            Stage.DESIGN,
            ResultStatus.READY,
            "The architecture advisor is ready to recommend a solution shape.",
            issues=(
                Issue(
                    "architecture-decision",
                    "No approved architecture decision is recorded.",
                    "Run `accel design`, review the rationale, then approve a decision.",
                    "accelerator.yaml",
                ),
            ),
        )
    if not architecture_is_current(
        architecture,
        recommendation.requirements_fingerprint,
    ):
        return StageSummary(
            Stage.DESIGN,
            ResultStatus.APPROVAL_REQUIRED,
            "The architecture decision is missing, unapproved, or stale.",
            issues=(
                Issue(
                    "architecture-decision-stale",
                    "Approved requirements changed after the recorded architecture decision.",
                    "Run `accel design` and approve the updated recommendation.",
                    "accelerator.yaml",
                ),
            ),
        )
    decision = architecture.get("decision") or {}
    implementation_pattern = (
        str(decision.get("implementation_pattern"))
        if decision.get("implementation_pattern")
        else legacy_implementation_pattern_for(
            str(decision.get("agent_type") or "")
        )
    )
    selection_issues = validate_selection(
        agent_type=str(decision.get("agent_type") or ""),
        implementation_pattern=implementation_pattern,
        orchestration_pattern=str(decision.get("orchestration_pattern") or ""),
        application_shell=str(decision.get("application_shell") or ""),
        deployment_target=str(decision.get("deployment_target") or ""),
    )
    if selection_issues:
        return StageSummary(
            Stage.DESIGN,
            ResultStatus.BLOCKED,
            "The approved architecture decision is invalid.",
            issues=tuple(
                Issue(
                    f"architecture-selection-{index}",
                    message,
                    "Run `accel design` and approve a supported combination.",
                    "accelerator.yaml",
                )
                for index, message in enumerate(selection_issues, start=1)
            ),
        )
    return StageSummary(
        Stage.DESIGN,
        ResultStatus.COMPLETE,
        "The Foundry architecture decision is approved and current.",
        (
            f"Agent type: {decision.get('agent_type')}",
            f"Implementation pattern: {implementation_pattern}",
            f"Orchestration: {decision.get('orchestration_pattern')}",
            f"Application shell: {decision.get('application_shell')}",
            f"Recommended target: {decision.get('deployment_target')}",
        ),
    )


def _detect_provision(context: RepositoryContext) -> StageSummary:
    manifest = context.load_yaml("deploy/environments.yaml")
    invalid_targets = [
        (entry.get("name"), entry.get("deployment_target"))
        for entry in manifest.get("environments") or []
        if isinstance(entry, dict)
        and str(entry.get("deployment_target") or "selfhost")
        not in _DEPLOYMENT_TARGETS
    ]
    if invalid_targets:
        return StageSummary(
            Stage.PROVISION,
            ResultStatus.BLOCKED,
            "Deployment environment manifest contains unsupported targets.",
            issues=tuple(
                Issue(
                    f"deployment-target-{index}",
                    f"Environment {name!r} declares target {target!r}.",
                    "Use selfhost, foundry-prompt, or hosted-preview.",
                    "deploy/environments.yaml",
                )
                for index, (name, target) in enumerate(
                    invalid_targets,
                    start=1,
                )
            ),
        )
    environments = _declared_azd_environments(context)
    if not environments:
        return StageSummary(
            Stage.PROVISION,
            ResultStatus.READY,
            "No local azd environment has been provisioned yet.",
            issues=(
                Issue(
                    "azd-environment",
                    "No .azure/<environment>/.env file was found.",
                    "Run `accel environment list`, then `accel deploy --dry-run`.",
                ),
            ),
        )
    endpoint_keys = {
        "SERVICE_API_URI",
        "AZURE_CONTAINER_APP_ENDPOINT",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_FOUNDRY_ENDPOINT",
    }
    configured = [
        name
        for name, (_target, values) in environments.items()
        if endpoint_keys.intersection(values)
    ]
    status = ResultStatus.COMPLETE if configured else ResultStatus.READY
    summary = (
        f"Provisioned environment metadata found: {', '.join(configured)}."
        if configured
        else "Local azd environments exist but no deployed endpoint was detected."
    )
    return StageSummary(
        Stage.PROVISION,
        status,
        summary,
        tuple(
            f"azd environment: {name} ({target})"
            for name, (target, _values) in environments.items()
        ),
    )


def _detect_iterate(
    context: RepositoryContext,
    manifest: dict[str, Any],
) -> StageSummary:
    scenario = manifest.get("scenario") or {}
    evals = scenario.get("evals") or {}
    quality_path = context.root / str(
        evals.get("quality_dataset") or "evals/quality/golden_cases.jsonl"
    )
    redteam_path = context.root / str(
        evals.get("redteam_dataset") or "evals/redteam/cases.jsonl"
    )
    quality_count = _jsonl_count(quality_path)
    redteam_count = _jsonl_count(redteam_path)
    if quality_count == 0 or redteam_count == 0:
        issues: list[Issue] = []
        if quality_count == 0:
            issues.append(
                Issue(
                    "quality-cases",
                    "No quality golden cases were found.",
                    "Add representative cases before UAT.",
                    context.relative(quality_path),
                )
            )
        if redteam_count == 0:
            issues.append(
                Issue(
                    "redteam-cases",
                    "No red-team cases were found.",
                    "Add scenario-specific safety cases before UAT.",
                    context.relative(redteam_path),
                )
            )
        return StageSummary(
            Stage.ITERATE,
            ResultStatus.BLOCKED,
            "Evaluation datasets are incomplete.",
            issues=tuple(issues),
        )
    return StageSummary(
        Stage.ITERATE,
        ResultStatus.COMPLETE,
        "Evaluation datasets are present.",
        (
            f"Quality cases: {quality_count}",
            f"Red-team cases: {redteam_count}",
        ),
    )


def _detect_uat(context: RepositoryContext) -> StageSummary:
    signoff = context.artifacts_dir / "uat-signoff.json"
    acceptance = context.artifacts_dir / "acceptance-report.json"
    if signoff.exists():
        return StageSummary(
            Stage.UAT,
            ResultStatus.COMPLETE,
            "Customer UAT sign-off is recorded.",
            ("UAT sign-off artifact exists",),
        )
    if acceptance.exists():
        return StageSummary(
            Stage.UAT,
            ResultStatus.APPROVAL_REQUIRED,
            "Acceptance results exist and require customer sign-off.",
            issues=(
                Issue(
                    "uat-signoff",
                    "Acceptance report has not been signed.",
                    "Run `accel uat signoff` after customer review.",
                    context.relative(acceptance),
                ),
            ),
        )
    return StageSummary(
        Stage.UAT,
        ResultStatus.READY,
        "UAT has not been run through the unified CLI.",
        issues=(
            Issue(
                "acceptance-report",
                "No acceptance report artifact was found.",
                "Run `accel evaluate --execute`, then `accel uat report`.",
            ),
        ),
    )


def _detect_handover(context: RepositoryContext) -> StageSummary:
    completion = context.artifacts_dir / "handover.json"
    if completion.exists():
        try:
            value = json.loads(completion.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            value = {}
        if value.get("status") != "approved":
            return StageSummary(
                Stage.HANDOVER,
                ResultStatus.APPROVAL_REQUIRED,
                "A handover draft exists and requires customer-ops approval.",
                issues=(
                    Issue(
                        "handover-approval",
                        "Handover package has not been approved.",
                        "Run `accel handover approve --approver <name> --apply`.",
                        context.relative(completion),
                    ),
                ),
            )
        return StageSummary(
            Stage.HANDOVER,
            ResultStatus.COMPLETE,
            "Production handover is recorded.",
            ("Handover artifact exists",),
        )
    return StageSummary(
        Stage.HANDOVER,
        ResultStatus.READY,
        "The engagement-specific handover package has not been generated.",
        issues=(
            Issue(
                "handover-package",
                "No completed handover artifact was found.",
                "Run `accel handover generate --dry-run`.",
            ),
        ),
    )


def _detect_operate(context: RepositoryContext) -> StageSummary:
    handover = context.artifacts_dir / "handover.json"
    approved = False
    if handover.exists():
        try:
            approved = (
                json.loads(handover.read_text(encoding="utf-8")).get("status")
                == "approved"
            )
        except json.JSONDecodeError:
            approved = False
    if not approved:
        return StageSummary(
            Stage.OPERATE,
            ResultStatus.BLOCKED,
            "Day-2 operations begin after handover.",
            issues=(
                Issue(
                    "operate-before-handover",
                    "Handover is not complete.",
                    "Complete the handover stage first.",
                ),
            ),
        )
    return StageSummary(
        Stage.OPERATE,
        ResultStatus.READY,
        "The solution is ready for day-2 monitoring and value review.",
        ("Handover completed",),
    )


def _local_approved_requirement_statements(
    context: RepositoryContext,
) -> tuple[str, ...]:
    return tuple(
        requirement.statement
        for requirement in EvidenceLedger(context).list_requirements()
        if requirement.status == "approved"
    )


def _declared_azd_environments(
    context: RepositoryContext,
) -> dict[str, tuple[str, set[str]]]:
    manifest = context.load_yaml("deploy/environments.yaml")
    environments: dict[str, tuple[str, set[str]]] = {}
    for entry in manifest.get("environments") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        name = entry["name"]
        target = str(entry.get("deployment_target") or "selfhost")
        if target == "hosted-preview":
            workspace = context.root / "deploy" / "hosted-preview"
        elif target == "foundry-prompt":
            workspace = context.root / "deploy" / "foundry-prompt"
        else:
            workspace = context.root
        env_file = workspace / ".azure" / name / ".env"
        if not env_file.exists():
            continue
        keys: set[str] = set()
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                keys.add(stripped.split("=", 1)[0])
        environments[name] = (target, keys)
    return environments


def _jsonl_count(path: pathlib.Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            continue
        count += 1
    return count
