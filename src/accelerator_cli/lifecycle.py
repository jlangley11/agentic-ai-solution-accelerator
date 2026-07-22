"""Derive accelerator lifecycle state from persistent repository artifacts."""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any

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
    required = (
        package_path / "schema.py",
        package_path / "workflow.py",
        package_path / "agents",
    )
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
    all_missing = (*missing, *agent_specs_missing)
    if all_missing:
        return StageSummary(
            Stage.SCAFFOLD,
            ResultStatus.BLOCKED,
            "The scenario scaffold is incomplete.",
            issues=tuple(
                Issue(
                    f"scaffold-{index}",
                    f"Required scaffold artifact is missing: {context.relative(path)}",
                    "Run the corresponding `accel scaffold` or worker command.",
                    context.relative(path),
                )
                for index, path in enumerate(all_missing, start=1)
            ),
        )
    return StageSummary(
        Stage.SCAFFOLD,
        ResultStatus.COMPLETE,
        f"Scenario package {package!r} is materialized.",
        (
            f"Scenario package: {package}",
            f"Registered agents: {len(scenario.get('agents') or [])}",
        ),
    )


def _detect_provision(context: RepositoryContext) -> StageSummary:
    manifest = context.load_yaml("deploy/environments.yaml")
    invalid_targets = [
        (entry.get("name"), entry.get("deployment_target"))
        for entry in manifest.get("environments") or []
        if isinstance(entry, dict)
        and str(entry.get("deployment_target") or "selfhost")
        not in {"selfhost", "hosted-preview"}
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
                    "Use selfhost or hosted-preview.",
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
        workspace = (
            context.root / "deploy" / "hosted-preview"
            if target == "hosted-preview"
            else context.root
        )
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
