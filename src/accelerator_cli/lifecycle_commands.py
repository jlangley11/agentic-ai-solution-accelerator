"""Deterministic wrappers for discovery through day-2 operations."""
from __future__ import annotations

import difflib
import json
import pathlib
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import yaml

from src.implementation_patterns import legacy_implementation_pattern_for

from .architecture_advisor import (
    FOUNDRY_AGENT_OVERVIEW,
    HARNESS_GUIDANCE,
    HOSTED_AGENT_GUIDANCE,
    architecture_is_current,
    committed_requirement_context,
    implementation_pattern_for,
    recommend_architecture,
    validate_selection,
)
from .intake.ledger import EvidenceLedger
from .lifecycle import detect_lifecycle
from .manifest_edit import replace_architecture, replace_scenario, scenario_block
from .operations import ensure_private_workspace
from .protocol import (
    ApprovalLevel,
    Artifact,
    CommandResult,
    Issue,
    ProposedAction,
    RequiredInput,
    ResultStatus,
    Stage,
)
from .repository import RepositoryContext
from .runner import load_script, python_command, render_command, run_process

_SCENARIO_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_ENVIRONMENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_DEPLOYMENT_TARGETS = {"selfhost", "foundry-prompt", "hosted-preview"}


def discover(context: RepositoryContext) -> CommandResult:
    lifecycle = detect_lifecycle(context)
    stage = lifecycle.for_stage(Stage.DISCOVER)
    ledger = EvidenceLedger(context)
    sources = ledger.list_sources()
    approved = [
        source for source in sources if source.disclosure_status == "approved_for_model"
    ]
    inputs = (
        RequiredInput(
            "discovery-mode",
            "Are you working live with the customer, from notes, or from source documents?",
            "choice",
            choices=("live", "notes", "documents"),
        ),
    )
    if stage.status == ResultStatus.COMPLETE:
        return CommandResult(
            stage=Stage.DISCOVER,
            status=ResultStatus.COMPLETE,
            summary=stage.summary,
            completed=stage.completed,
            next_command="accel design",
            details={
                "sources": len(sources),
                "approved_sources": len(approved),
            },
        )
    return CommandResult(
        stage=Stage.DISCOVER,
        status=ResultStatus.NEEDS_INPUT,
        summary=stage.summary,
        required_inputs=inputs,
        blocking_issues=stage.issues,
        proposed_actions=(
            ProposedAction(
                "add-source-documents",
                "Add customer source documents locally",
                "accel intake add <document-path> [<document-path> ...]",
            ),
        ),
        next_command=(
            "accel intake list"
            if sources
            else "accel intake add <document-path> [<document-path> ...]"
        ),
        details={
            "sources": len(sources),
            "approved_sources": len(approved),
            "instruction": (
                "The coding agent should ask only for unresolved brief fields, "
                "edit the brief after confirmation, and never infer numeric values."
            ),
        },
    )


def design(
    context: RepositoryContext,
    *,
    agent_type: str | None = None,
    implementation_pattern: str | None = None,
    orchestration_pattern: str | None = None,
    application_shell: str | None = None,
    deployment_target: str | None = None,
    approved_by: str | None = None,
    override_reason: str | None = None,
    apply: bool = False,
) -> CommandResult:
    brief = context.brief_path.read_text(encoding="utf-8") if context.brief_path.exists() else ""
    manifest = context.manifest()
    discovery_stage = detect_lifecycle(context).for_stage(Stage.DISCOVER)
    if discovery_stage.status != ResultStatus.COMPLETE:
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.NEEDS_INPUT,
            summary="Architecture advice requires a completed solution brief.",
            blocking_issues=discovery_stage.issues,
            next_command="accel discover",
        )
    requirements = {
        "solution pattern": "## 5. Solution shape" in brief,
        "UX shape": "UX shape" in brief and "ux_shape" in brief,
        "UX inputs": "UX inputs" in brief,
        "UX output sections": "UX output sections" in brief,
        "RAI risks": "RAI risks" in brief,
        "acceptance thresholds": bool(manifest.get("acceptance")),
        "landing zone": bool(manifest.get("landing_zone")),
    }
    missing = [label for label, present in requirements.items() if not present]
    if missing:
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.NEEDS_INPUT,
            summary=f"{len(missing)} design contract item(s) are missing.",
            blocking_issues=tuple(
                Issue(
                    f"design-{index}",
                    f"Missing design item: {label}",
                    "Update the solution brief through the discovery workflow.",
                    "docs/discovery/solution-brief.md",
                )
                for index, label in enumerate(missing, start=1)
            ),
            next_command="accel discover",
            details={"checks": requirements},
        )
    ledger = EvidenceLedger(context)
    local_approved_requirements = tuple(
        requirement.statement
        for requirement in ledger.list_requirements()
        if requirement.status == "approved"
    )
    traceability = (
        context.root / "docs" / "discovery" / "requirements-traceability.md"
    )
    committed_requirements = committed_requirement_context(
        context.root,
        local_approved_requirements,
    )
    local_normalized = {
        " ".join(statement.split()) for statement in local_approved_requirements
    }
    committed_normalized = {
        " ".join(statement.split()) for statement in committed_requirements
    }
    if (
        local_approved_requirements
        and not traceability.exists()
    ) or (
        ledger.path.exists()
        and traceability.exists()
        and local_normalized != committed_normalized
    ):
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.NEEDS_INPUT,
            summary="Refresh the requirements export before architecture review.",
            blocking_issues=(
                Issue(
                    "architecture-traceability",
                    "The committed sanitized traceability artifact is missing "
                    "or does not match approved local requirements.",
                    "Run `accel intake requirement export --apply`.",
                    "docs/discovery/requirements-traceability.md",
                ),
            ),
            next_command="accel intake requirement export --apply",
        )
    approved_requirements = committed_requirements
    recommendation = recommend_architecture(brief, approved_requirements)
    current_architecture = manifest.get("architecture")
    current_architecture_map = (
        current_architecture
        if isinstance(current_architecture, dict)
        else None
    )
    selected_agent_type = agent_type or recommendation.agent_type
    selected_orchestration = (
        orchestration_pattern or recommendation.orchestration_pattern
    )
    selected_implementation = implementation_pattern
    if selected_implementation is None:
        if (
            selected_agent_type == recommendation.agent_type
            and selected_orchestration == recommendation.orchestration_pattern
        ):
            selected_implementation = recommendation.implementation_pattern
        else:
            selected_implementation = implementation_pattern_for(
                selected_agent_type,
                selected_orchestration,
            )
    selected = {
        "agent_type": selected_agent_type,
        "implementation_pattern": selected_implementation,
        "orchestration_pattern": selected_orchestration,
        "application_shell": application_shell or recommendation.application_shell,
        "deployment_target": deployment_target or recommendation.deployment_target,
    }
    selection_issues = validate_selection(**selected)
    if selection_issues:
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.BLOCKED,
            summary="The selected architecture combination is unsupported.",
            blocking_issues=tuple(
                Issue(
                    f"architecture-selection-{index}",
                    message,
                    "Choose a supported combination from `accel design`.",
                    "accelerator.yaml",
                )
                for index, message in enumerate(selection_issues, start=1)
            ),
            details={"recommendation": recommendation.to_dict(), "selected": selected},
        )
    recommended_selection = {
        "agent_type": recommendation.agent_type,
        "implementation_pattern": recommendation.implementation_pattern,
        "orchestration_pattern": recommendation.orchestration_pattern,
        "application_shell": recommendation.application_shell,
        "deployment_target": recommendation.deployment_target,
    }
    overridden = selected != recommended_selection
    if overridden and not (override_reason or "").strip():
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.NEEDS_INPUT,
            summary="An override reason is required for a non-recommended architecture.",
            required_inputs=(
                RequiredInput(
                    "override-reason",
                    "Why is the partner overriding the deterministic recommendation?",
                ),
            ),
            next_command=_design_command(
                selected,
                include_approval=apply,
                include_override=True,
            ),
            details={
                "recommendation": recommendation.to_dict(),
                "selected": selected,
            },
        )
    if (
        not any(
            value is not None
            for value in (
                agent_type,
                implementation_pattern,
                orchestration_pattern,
                application_shell,
                deployment_target,
                approved_by,
                override_reason,
            )
        )
        and architecture_is_current(
            current_architecture_map,
            recommendation.requirements_fingerprint,
        )
    ):
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.COMPLETE,
            summary="The approved architecture decision is current.",
            completed=tuple(
                f"{key.replace('_', ' ').title()}: {value}"
                for key, value in (
                    ((current_architecture_map or {}).get("decision") or {}).items()
                )
                if key in selected
            ),
            next_command="accel scaffold --scenario-id <scenario-id> --dry-run",
            details={
                "checks": requirements,
                "recommendation": recommendation.to_dict(),
                "architecture": current_architecture,
            },
        )
    decision_block = _architecture_decision_block(
        recommendation=recommendation.to_dict(),
        selected=selected,
        approved_by=approved_by,
        override_reason=override_reason,
    )
    original, updated = replace_architecture(
        context,
        decision_block,
        apply=False,
    )
    manifest_diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="accelerator.yaml",
            tofile="accelerator.yaml (proposed)",
        )
    )
    if not apply:
        apply_command = _design_command(
            selected,
            include_approval=True,
            include_override=overridden,
        )
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=(
                "Architecture Advisor recommends "
                f"{recommendation.agent_type} / "
                f"{recommendation.implementation_pattern} with "
                f"{recommendation.orchestration_pattern}."
            ),
            completed=(
                *recommendation.rationale,
                *(
                    "Alternative "
                    f"{alternative['dimension']}={alternative['option']}: "
                    f"{alternative['reason']}"
                    for alternative in recommendation.alternatives
                ),
            ),
            required_inputs=(
                RequiredInput(
                    "approved-by",
                    "Who approves the selected architecture?",
                ),
            ),
            proposed_actions=(
                ProposedAction(
                    "approve-architecture",
                    "Record the reviewed architecture decision",
                    apply_command,
                    ApprovalLevel.APPLY,
                    reason=(
                        "Scaffolding and deployment remain blocked until the "
                        "partner approves or overrides this recommendation."
                    ),
                ),
            ),
            next_command=apply_command,
            details={
                "checks": requirements,
                "recommendation": recommendation.to_dict(),
                "selected": selected,
                "manifest_diff": manifest_diff,
                "foundry_agent_types": {
                    "prompt-agent": (
                        "Declarative instructions, model, and tools; Foundry "
                        "runs the agent without custom runtime code."
                    ),
                    "hosted-agent": (
                        "Custom code or framework hosted by Foundry with managed "
                        "endpoint, scaling, identity, and observability."
                    ),
                    "workflow-note": (
                        "Workflow is an orchestration pattern. It is not a third "
                        "Foundry Agent Service runtime type."
                    ),
                },
                "implementation_patterns": {
                    "managed-prompt": (
                        "Foundry owns the declarative prompt agent runtime."
                    ),
                    "harness": (
                        "Agent Framework provides the hosted single-agent loop, "
                        "planning, history, mode tracking, and telemetry."
                    ),
                    "custom-workflow": (
                        "Partner code owns deterministic or supervisor orchestration."
                    ),
                },
                "references": [
                    FOUNDRY_AGENT_OVERVIEW,
                    HOSTED_AGENT_GUIDANCE,
                    HARNESS_GUIDANCE,
                ],
            },
        )
    if not (approved_by or "").strip():
        return CommandResult(
            stage=Stage.DESIGN,
            status=ResultStatus.NEEDS_INPUT,
            summary="Architecture approval requires an approver name.",
            required_inputs=(
                RequiredInput(
                    "approved-by",
                    "Who approves the selected architecture?",
                ),
            ),
            next_command=_design_command(
                selected,
                include_approval=True,
                include_override=overridden,
            ),
            details={"recommendation": recommendation.to_dict(), "selected": selected},
        )
    decision_block = _architecture_decision_block(
        recommendation=recommendation.to_dict(),
        selected=selected,
        approved_by=approved_by,
        override_reason=override_reason,
    )
    replace_architecture(context, decision_block, apply=True)
    return CommandResult(
        stage=Stage.DESIGN,
        status=ResultStatus.COMPLETE,
        summary="The architecture decision was approved and recorded.",
        completed=(
            f"Agent type: {selected['agent_type']}",
            f"Implementation pattern: {selected['implementation_pattern']}",
            f"Orchestration: {selected['orchestration_pattern']}",
            f"Application shell: {selected['application_shell']}",
            f"Deployment target: {selected['deployment_target']}",
        ),
        next_command="accel scaffold --scenario-id <scenario-id> --dry-run",
        details={
            "checks": requirements,
            "recommendation": recommendation.to_dict(),
            "architecture": decision_block,
        },
    )


def scaffold(
    context: RepositoryContext,
    *,
    scenario_id: str,
    no_retrieval: bool,
    preserve_evals: bool,
    apply: bool,
) -> CommandResult:
    if not _SCENARIO_ID_RE.fullmatch(scenario_id):
        return CommandResult(
            stage=Stage.SCAFFOLD,
            status=ResultStatus.FAILED,
            summary="The scenario id is invalid.",
            blocking_issues=(
                Issue(
                    "scenario-id",
                    f"{scenario_id!r} must be lowercase words separated by hyphens.",
                ),
            ),
        )
    design_stage = detect_lifecycle(context).for_stage(Stage.DESIGN)
    if design_stage.status != ResultStatus.COMPLETE:
        return CommandResult(
            stage=Stage.SCAFFOLD,
            status=ResultStatus.BLOCKED,
            summary="Scaffolding requires an approved, current architecture decision.",
            blocking_issues=design_stage.issues,
            next_command="accel design",
        )
    architecture = context.manifest().get("architecture") or {}
    decision = architecture.get("decision") or {}
    implementation_pattern = (
        str(decision.get("implementation_pattern"))
        if decision.get("implementation_pattern")
        else legacy_implementation_pattern_for(
            str(decision.get("agent_type") or "")
        )
    )
    if implementation_pattern == "harness" and not no_retrieval:
        command = _scaffold_apply_command(
            scenario_id,
            True,
            preserve_evals,
        )
        return CommandResult(
            stage=Stage.SCAFFOLD,
            status=ResultStatus.NEEDS_INPUT,
            summary="Harness scaffolds currently require retrieval mode none.",
            blocking_issues=(
                Issue(
                    "harness-retrieval",
                    "FoundryIQ prompt-agent attachments are not available to the "
                    "direct FoundryChatClient Harness runtime.",
                    "Re-run scaffold with `--no-retrieval`; add only governed "
                    "Harness tools whose side effects retain hitl.checkpoint.",
                    "accelerator.yaml",
                ),
            ),
            next_command=command,
        )
    script = load_script(
        context,
        "scripts/scaffold-scenario.py",
        module_name="accelerator_cli_scaffold_scenario",
    )
    plan = script._plan(
        scenario_id,
        no_retrieval=no_retrieval,
        agent_type=str(decision["agent_type"]),
        implementation_pattern=implementation_pattern,
    )
    conflicts = [path for path, _ in plan if path.exists()]
    block = scenario_block(
        scenario_id,
        no_retrieval=no_retrieval,
        agent_type=str(decision["agent_type"]),
        implementation_pattern=implementation_pattern,
        orchestration_pattern=str(decision["orchestration_pattern"]),
        application_shell=str(decision["application_shell"]),
    )
    original, updated = replace_scenario(context, block, apply=False)
    manifest_diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="accelerator.yaml",
            tofile="accelerator.yaml (proposed)",
        )
    )
    if conflicts:
        return CommandResult(
            stage=Stage.SCAFFOLD,
            status=ResultStatus.BLOCKED,
            summary="Scaffolding would overwrite existing files.",
            blocking_issues=tuple(
                Issue(
                    f"scaffold-conflict-{index}",
                    f"Target already exists: {context.relative(path)}",
                    "Choose another scenario id or migrate the existing scenario.",
                    context.relative(path),
                )
                for index, path in enumerate(conflicts, start=1)
            ),
        )
    proposed = tuple(
        Artifact(
            f"scaffold-{index}",
            context.relative(path),
            "create",
        )
        for index, (path, _content) in enumerate(plan, start=1)
    )
    if not apply:
        return CommandResult(
            stage=Stage.SCAFFOLD,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=(
                f"Scaffolding {scenario_id!r} would create {len(plan)} files "
                "and update accelerator.yaml."
            ),
            artifacts=proposed,
            proposed_actions=(
                ProposedAction(
                    "apply-scaffold",
                    "Create the scenario and update the manifest",
                    _scaffold_apply_command(scenario_id, no_retrieval, preserve_evals),
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=_scaffold_apply_command(
                scenario_id,
                no_retrieval,
                preserve_evals,
            ),
            details={
                "manifest_diff": manifest_diff,
                "architecture_decision": decision,
                "architecture_diagram": block["architecture_diagram"],
            },
        )

    command = python_command(
        "scripts/scaffold-scenario.py",
        scenario_id,
        "--agent-type",
        str(decision["agent_type"]),
        "--implementation-pattern",
        implementation_pattern,
        "--orchestration-pattern",
        str(decision["orchestration_pattern"]),
        "--application-shell",
        str(decision["application_shell"]),
        *(["--no-retrieval"] if no_retrieval else []),
        *(["--no-evals"] if preserve_evals else []),
    )
    golden_path = context.root / "evals" / "quality" / "golden_cases.jsonl"
    golden_existed = golden_path.exists()
    golden_backup = golden_path.read_bytes() if golden_existed else None
    preexisting_dirs = {
        parent
        for path, _content in plan
        for parent in path.parents
        if parent.exists() and parent.is_dir()
    }
    process = run_process(context, command)
    if not process.ok:
        return _process_failure(Stage.SCAFFOLD, "Scenario scaffolding failed.", process)
    try:
        replace_scenario(context, block, apply=True)
    except Exception as exc:
        context.manifest_path.write_text(original, encoding="utf-8")
        if golden_backup is not None:
            golden_path.write_bytes(golden_backup)
        elif not golden_existed and golden_path.exists():
            golden_path.unlink()
        cleanup_issues = _remove_scaffold_plan(
            context,
            [path for path, _content in plan],
            preexisting_dirs=preexisting_dirs,
        )
        return CommandResult(
            stage=Stage.SCAFFOLD,
            status=ResultStatus.FAILED,
            summary=(
                "Scenario files were rolled back because manifest update failed."
                if not cleanup_issues
                else "Manifest update failed and scaffold rollback was partial."
            ),
            blocking_issues=(
                Issue(
                    "manifest-update",
                    str(exc),
                    "Resolve the manifest write failure and re-run the scaffold.",
                    "accelerator.yaml",
                ),
                *(
                    Issue(
                        f"rollback-{index}",
                        message,
                        "Inspect the path before retrying the scaffold.",
                    )
                    for index, message in enumerate(cleanup_issues, start=1)
                ),
            ),
            details={"rollback_issues": cleanup_issues},
        )
    return CommandResult(
        stage=Stage.SCAFFOLD,
        status=ResultStatus.COMPLETE,
        summary=f"Scenario {scenario_id!r} was scaffolded and registered.",
        completed=(
            f"Created {len(plan)} scaffold artifacts",
            "Updated accelerator.yaml scenario block",
            (
                "Declared MCP architecture diagram deliverable: "
                f"{block['architecture_diagram']['path']}"
            ),
        ),
        artifacts=tuple(
            Artifact(item.id, item.path, "created", item.description)
            for item in proposed
        ),
        next_command="accel validate",
        details={
            "script_stdout": process.stdout[-4000:],
            "architecture_decision": decision,
            "architecture_diagram": block["architecture_diagram"],
        },
    )


def environment_list(context: RepositoryContext) -> CommandResult:
    manifest = context.load_yaml("deploy/environments.yaml")
    entries = manifest.get("environments") or []
    if not isinstance(entries, list):
        entries = []
    completed = tuple(
        f"{entry.get('name')}: {entry.get('deployment_target', 'selfhost')} "
        f"(GitHub Environment: {entry.get('github_environment')})"
        for entry in entries
        if isinstance(entry, dict)
    )
    return CommandResult(
        stage=Stage.PROVISION,
        status=ResultStatus.READY if entries else ResultStatus.NEEDS_INPUT,
        summary=f"{len(completed)} deployment environment(s) are declared.",
        completed=completed,
        next_command=(
            f"accel deploy --env {manifest.get('default_env')} --region <region> --dry-run"
            if manifest.get("default_env")
            else "Use /deploy-to-env to register the first environment."
        ),
        details={"default_env": manifest.get("default_env"), "environments": entries},
    )


def deploy(
    context: RepositoryContext,
    *,
    env: str,
    region: str,
    target: str | None,
    acknowledge_preview: bool,
    execute: bool,
    apply: bool,
) -> CommandResult:
    env_manifest = context.load_yaml("deploy/environments.yaml")
    entries = {
        entry.get("name"): entry
        for entry in env_manifest.get("environments") or []
        if isinstance(entry, dict)
    }
    entry = entries.get(env)
    if not entry:
        return CommandResult(
            stage=Stage.PROVISION,
            status=ResultStatus.BLOCKED,
            summary=f"Environment {env!r} is not declared.",
            blocking_issues=(
                Issue(
                    "environment-missing",
                    f"deploy/environments.yaml has no entry named {env!r}.",
                    "Run /deploy-to-env or add the environment through the supported workflow.",
                    "deploy/environments.yaml",
                ),
            ),
        )
    manifest_target = str(entry.get("deployment_target") or "selfhost")
    if manifest_target not in _DEPLOYMENT_TARGETS:
        return CommandResult(
            stage=Stage.PROVISION,
            status=ResultStatus.BLOCKED,
            summary="The environment manifest contains an unsupported target.",
            blocking_issues=(
                Issue(
                    "deployment-target-invalid",
                    f"Environment {env!r} declares unsupported target "
                    f"{manifest_target!r}.",
                    "Use selfhost, foundry-prompt, or hosted-preview in "
                    "deploy/environments.yaml.",
                    "deploy/environments.yaml",
                ),
            ),
        )
    if target is not None and target != manifest_target:
        return CommandResult(
            stage=Stage.PROVISION,
            status=ResultStatus.BLOCKED,
            summary="The requested deployment target conflicts with the manifest.",
            blocking_issues=(
                Issue(
                    "deployment-target-drift",
                    f"Environment {env!r} is declared as {manifest_target!r}, "
                    f"not {target!r}.",
                    "Update deploy/environments.yaml through the supported "
                    "environment workflow instead of overriding the target.",
                    "deploy/environments.yaml",
                ),
            ),
        )
    deployment_target = manifest_target
    design_stage = detect_lifecycle(context).for_stage(Stage.DESIGN)
    if design_stage.status != ResultStatus.COMPLETE:
        return CommandResult(
            stage=Stage.PROVISION,
            status=ResultStatus.BLOCKED,
            summary="Deployment requires an approved, current architecture decision.",
            blocking_issues=design_stage.issues,
            next_command="accel design",
        )
    architecture_decision = (
        (context.manifest().get("architecture") or {}).get("decision") or {}
    )
    selected_target = str(architecture_decision.get("deployment_target") or "")
    if selected_target != deployment_target:
        return CommandResult(
            stage=Stage.PROVISION,
            status=ResultStatus.BLOCKED,
            summary="The environment target conflicts with the architecture decision.",
            blocking_issues=(
                Issue(
                    "architecture-deployment-target",
                    f"Architecture selected {selected_target!r}, but environment "
                    f"{env!r} declares {deployment_target!r}.",
                    "Approve the intended target with `accel design` or select a "
                    "matching environment.",
                    "accelerator.yaml",
                ),
            ),
        )
    workspace = _deployment_workspace(context, deployment_target)
    preflight = [
        sys.executable,
        str(context.root / "scripts" / "preflight-deploy.py"),
        "--region",
        region,
        "--deployment-target",
        deployment_target,
    ]
    if deployment_target == "hosted-preview" and acknowledge_preview:
        preflight.append("--acknowledge-preview")
    deploy_commands = [["azd", "up", "-e", env, "--no-prompt"]]
    if deployment_target == "hosted-preview":
        deploy_commands = [
            ["azd", "provision", "-e", env, "--no-prompt"],
            ["azd", "deploy", "-e", env, "--no-prompt"],
        ]
    elif deployment_target == "foundry-prompt":
        deploy_commands = [["azd", "provision", "-e", env, "--no-prompt"]]

    if not execute:
        actions = [
            ProposedAction(
                "run-preflight",
                "Run deployment preflight",
                render_command(preflight),
                ApprovalLevel.EXECUTE,
            )
        ]
        if apply:
            actions.extend(
                ProposedAction(
                    f"deploy-{index}",
                    "Provision and deploy the selected environment",
                    render_command(command),
                    ApprovalLevel.EXECUTE,
                )
                for index, command in enumerate(deploy_commands, start=1)
            )
        return CommandResult(
            stage=Stage.PROVISION,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=f"Deployment plan is ready for {env!r} ({deployment_target}).",
            proposed_actions=tuple(actions),
            next_command=(
                f"accel deploy --env {env} --region {region} "
                f"--target {deployment_target} --execute"
            ),
            details={
                "workspace": str(workspace),
                "apply_requested": apply,
                "architecture_decision": architecture_decision,
            },
        )

    preflight_result = run_process(context, preflight, cwd=context.root, timeout=900)
    if not preflight_result.ok:
        return _process_failure(
            Stage.PROVISION,
            "Deployment preflight failed.",
            preflight_result,
        )
    if not apply:
        return CommandResult(
            stage=Stage.PROVISION,
            status=ResultStatus.COMPLETE,
            summary="Deployment preflight passed.",
            completed=(f"Preflight: {env} ({deployment_target})",),
            proposed_actions=tuple(
                ProposedAction(
                    f"apply-deploy-{index}",
                    "Run the deployment",
                    render_command(command),
                    ApprovalLevel.EXECUTE,
                )
                for index, command in enumerate(deploy_commands, start=1)
            ),
            next_command=(
                f"accel deploy --env {env} --region {region} "
                f"--target {deployment_target} --execute --apply"
            ),
            details={"preflight": preflight_result.stdout[-4000:]},
        )
    deployment_results = []
    for deploy_command in deploy_commands:
        deployment = run_process(
            context,
            deploy_command,
            cwd=workspace,
            timeout=3600,
        )
        deployment_results.append(deployment)
        if not deployment.ok:
            return _process_failure(Stage.PROVISION, "Deployment failed.", deployment)
    return CommandResult(
        stage=Stage.PROVISION,
        status=ResultStatus.COMPLETE,
        summary=f"Environment {env!r} deployed successfully.",
        completed=(f"Deployment target: {deployment_target}",),
        next_command=(
            "accel next"
            if deployment_target == "foundry-prompt"
            else "accel evaluate --api-url <api-url>"
        ),
        details={
            "architecture_decision": architecture_decision,
            "deployment_commands": [
                {
                    "command": list(result.command),
                    "stdout": result.stdout[-6000:],
                }
                for result in deployment_results
            ]
        },
    )


def evaluate(
    context: RepositoryContext,
    *,
    api_url: str,
    execute: bool,
    foundry: bool = False,
) -> CommandResult:
    quality_command = python_command("evals/quality/run.py", "--api-url", api_url)
    if foundry:
        quality_command.append("--include-evaluator-inputs")
    command_list = [
        quality_command,
        python_command("evals/redteam/run.py", "--api-url", api_url),
        python_command("scripts/enforce-acceptance.py"),
    ]
    if foundry:
        command_list.append(python_command("evals/foundry/run.py"))
    commands = tuple(command_list)
    if not execute:
        return CommandResult(
            stage=Stage.ITERATE,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary="The deployed acceptance chain is ready.",
            proposed_actions=tuple(
                ProposedAction(
                    f"eval-{index}",
                    f"Run acceptance command {index}",
                    render_command(command),
                    ApprovalLevel.EXECUTE,
                )
                for index, command in enumerate(commands, start=1)
            ),
            next_command=f"accel evaluate --api-url {api_url} --execute",
        )
    results = [run_process(context, list(command), timeout=1800) for command in commands]
    failed = [result for result in results if not result.ok]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "api_url": api_url,
        "accepted": not failed,
        "commands": [
            {
                "command": list(result.command),
                "returncode": result.returncode,
                "stdout": result.stdout[-6000:],
                "stderr": result.stderr[-6000:],
            }
            for result in results
        ],
    }
    ensure_private_workspace(context)
    report_path = context.artifacts_dir / "acceptance-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return CommandResult(
        stage=Stage.ITERATE,
        status=ResultStatus.COMPLETE if not failed else ResultStatus.FAILED,
        summary=(
            "The deployed acceptance chain passed."
            if not failed
            else f"{len(failed)} acceptance command(s) failed."
        ),
        artifacts=(
            Artifact(
                "acceptance-report",
                context.relative(report_path),
                "created",
            ),
        ),
        next_command="accel uat report" if not failed else "accel review",
        details=report,
    )


def uat_report(context: RepositoryContext) -> CommandResult:
    acceptance_path = context.artifacts_dir / "acceptance-report.json"
    if not acceptance_path.exists():
        return CommandResult(
            stage=Stage.UAT,
            status=ResultStatus.BLOCKED,
            summary="No unified acceptance report exists.",
            next_command="accel evaluate --api-url <api-url> --execute",
        )
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    manifest = context.manifest()
    markdown = _uat_markdown(acceptance, manifest)
    output = context.artifacts_dir / "uat-report.md"
    output.write_text(markdown, encoding="utf-8")
    return CommandResult(
        stage=Stage.UAT,
        status=(
            ResultStatus.APPROVAL_REQUIRED
            if acceptance.get("accepted")
            else ResultStatus.BLOCKED
        ),
        summary=(
            "UAT report generated and ready for customer sign-off."
            if acceptance.get("accepted")
            else "UAT report generated, but acceptance has not passed."
        ),
        artifacts=(Artifact("uat-report", context.relative(output), "created"),),
        proposed_actions=(
            ProposedAction(
                "uat-signoff",
                "Record customer UAT sign-off",
                "accel uat signoff --sponsor <name> --approver <name> --apply",
                ApprovalLevel.APPLY,
            ),
        )
        if acceptance.get("accepted")
        else (),
        next_command=(
            "accel uat signoff --sponsor <name> --approver <name> --apply"
            if acceptance.get("accepted")
            else "accel evaluate --api-url <api-url> --execute"
        ),
    )


def uat_signoff(
    context: RepositoryContext,
    *,
    sponsor: str,
    approver: str,
    apply: bool,
) -> CommandResult:
    acceptance_path = context.artifacts_dir / "acceptance-report.json"
    if not acceptance_path.exists():
        return CommandResult(
            stage=Stage.UAT,
            status=ResultStatus.BLOCKED,
            summary="Acceptance must pass before sign-off.",
            next_command="accel evaluate --api-url <api-url> --execute",
        )
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    if not acceptance.get("accepted"):
        return CommandResult(
            stage=Stage.UAT,
            status=ResultStatus.BLOCKED,
            summary="The acceptance report is rejected; UAT cannot be signed.",
            next_command="accel evaluate --api-url <api-url> --execute",
        )
    command = render_command(
        [
            "accel",
            "uat",
            "signoff",
            "--sponsor",
            sponsor,
            "--approver",
            approver,
            "--apply",
        ]
    )
    if not apply:
        return CommandResult(
            stage=Stage.UAT,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=f"Record UAT sign-off by {approver!r} for sponsor {sponsor!r}.",
            proposed_actions=(
                ProposedAction(
                    "apply-uat-signoff",
                    "Write the UAT sign-off artifact",
                    command,
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=command,
        )
    ensure_private_workspace(context)
    signoff = {
        "signed_at": datetime.now(UTC).isoformat(),
        "sponsor": sponsor,
        "approver": approver,
        "acceptance_report": context.relative(acceptance_path),
        "accepted": True,
    }
    path = context.artifacts_dir / "uat-signoff.json"
    path.write_text(json.dumps(signoff, indent=2), encoding="utf-8")
    return CommandResult(
        stage=Stage.UAT,
        status=ResultStatus.COMPLETE,
        summary="Customer UAT sign-off was recorded.",
        artifacts=(Artifact("uat-signoff", context.relative(path), "created"),),
        next_command="accel handover generate --env <environment> --dry-run",
    )


def handover_generate(
    context: RepositoryContext,
    *,
    env: str,
    apply: bool,
) -> CommandResult:
    if not _ENVIRONMENT_NAME_RE.fullmatch(env):
        return CommandResult(
            stage=Stage.HANDOVER,
            status=ResultStatus.BLOCKED,
            summary="The handover environment name is invalid.",
            blocking_issues=(
                Issue(
                    "handover-environment",
                    f"{env!r} is not a safe environment identifier.",
                    "Choose a declared environment name containing only "
                    "letters, numbers, dot, underscore, or hyphen.",
                    "deploy/environments.yaml",
                ),
            ),
        )
    environment_entries = {
        item.get("name"): item
        for item in (
            context.load_yaml("deploy/environments.yaml").get("environments")
            or []
        )
        if isinstance(item, dict)
    }
    if env not in environment_entries:
        return CommandResult(
            stage=Stage.HANDOVER,
            status=ResultStatus.BLOCKED,
            summary=f"Environment {env!r} is not declared.",
            blocking_issues=(
                Issue(
                    "handover-environment",
                    "Handover can only use an environment declared in "
                    "deploy/environments.yaml.",
                    "Register the environment through the supported workflow.",
                    "deploy/environments.yaml",
                ),
            ),
        )
    target = str(
        environment_entries[env].get("deployment_target") or "selfhost"
    )
    if target not in _DEPLOYMENT_TARGETS:
        return CommandResult(
            stage=Stage.HANDOVER,
            status=ResultStatus.BLOCKED,
            summary="The handover environment has an unsupported target.",
            blocking_issues=(
                Issue(
                    "handover-environment-target",
                    f"Environment {env!r} declares target {target!r}.",
                    "Use selfhost, foundry-prompt, or hosted-preview.",
                    "deploy/environments.yaml",
                ),
            ),
        )
    signoff = context.artifacts_dir / "uat-signoff.json"
    if not signoff.exists():
        return CommandResult(
            stage=Stage.HANDOVER,
            status=ResultStatus.BLOCKED,
            summary="UAT sign-off is required before handover.",
            next_command="accel uat report",
        )
    values = _azd_values(context, env)
    markdown = _handover_markdown(context, env, values)
    output = context.artifacts_dir / f"handover-{env}.md"
    if not apply:
        return CommandResult(
            stage=Stage.HANDOVER,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=f"Handover package for {env!r} is ready to generate.",
            proposed_actions=(
                ProposedAction(
                    "apply-handover",
                    "Generate the local handover package",
                    f"accel handover generate --env {env} --apply",
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=f"accel handover generate --env {env} --apply",
            details={"preview": markdown[:8000]},
        )
    ensure_private_workspace(context)
    output.write_text(markdown, encoding="utf-8")
    completion = {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": env,
        "packet": context.relative(output),
        "status": "draft",
        "requires_human_review": True,
    }
    completion_path = context.artifacts_dir / "handover.json"
    completion_path.write_text(json.dumps(completion, indent=2), encoding="utf-8")
    return CommandResult(
        stage=Stage.HANDOVER,
        status=ResultStatus.APPROVAL_REQUIRED,
        summary="The local handover draft was generated and requires approval.",
        artifacts=(
            Artifact("handover-packet", context.relative(output), "created"),
            Artifact("handover-state", context.relative(completion_path), "created"),
        ),
        proposed_actions=(
            ProposedAction(
                "approve-handover",
                "Record customer-ops approval after reviewing the packet",
                "accel handover approve --approver <name> --apply",
                ApprovalLevel.APPLY,
            ),
        ),
        next_command="accel handover approve --approver <name> --apply",
    )


def handover_approve(
    context: RepositoryContext,
    *,
    approver: str,
    apply: bool,
) -> CommandResult:
    completion_path = context.artifacts_dir / "handover.json"
    if not completion_path.exists():
        return CommandResult(
            stage=Stage.HANDOVER,
            status=ResultStatus.BLOCKED,
            summary="Generate and review the handover draft before approval.",
            next_command="accel handover generate --env <environment> --dry-run",
        )
    value = json.loads(completion_path.read_text(encoding="utf-8"))
    command = render_command(
        ["accel", "handover", "approve", "--approver", approver, "--apply"]
    )
    if not apply:
        return CommandResult(
            stage=Stage.HANDOVER,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=f"Record handover approval by {approver!r}.",
            proposed_actions=(
                ProposedAction(
                    "apply-handover-approval",
                    "Finalize the handover state",
                    command,
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command=command,
        )
    value.update(
        {
            "status": "approved",
            "requires_human_review": False,
            "approved_by": approver,
            "approved_at": datetime.now(UTC).isoformat(),
        }
    )
    completion_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return CommandResult(
        stage=Stage.HANDOVER,
        status=ResultStatus.COMPLETE,
        summary="Customer-ops handover approval was recorded.",
        artifacts=(
            Artifact("handover-state", context.relative(completion_path), "approved"),
        ),
        next_command="accel operate status",
    )


def operate_status(context: RepositoryContext) -> CommandResult:
    lifecycle = detect_lifecycle(context)
    operate = lifecycle.for_stage(Stage.OPERATE)
    return CommandResult(
        stage=Stage.OPERATE,
        status=operate.status,
        summary=operate.summary,
        completed=operate.completed,
        blocking_issues=operate.issues,
        proposed_actions=(
            ProposedAction(
                "validate",
                "Run repository validation",
                "accel validate",
            ),
            ProposedAction(
                "review-runbook",
                "Review the customer runbook",
                "Open docs/customer-runbook.md",
            ),
        ),
        next_command="accel validate",
    )


def migrate(context: RepositoryContext, *, apply: bool) -> CommandResult:
    lifecycle = detect_lifecycle(context)
    if not apply:
        return CommandResult(
            stage=lifecycle.current,
            status=ResultStatus.APPROVAL_REQUIRED,
            summary=(
                "Migration is additive: initialize local state and preserve all "
                "existing customer-authored artifacts."
            ),
            proposed_actions=(
                ProposedAction(
                    "apply-migrate",
                    "Initialize the unified CLI workspace",
                    "accel migrate --apply",
                    ApprovalLevel.APPLY,
                ),
            ),
            next_command="accel migrate --apply",
            stages=lifecycle.stages,
        )
    ensure_private_workspace(context)
    marker = context.artifacts_dir / "migration.json"
    marker.write_text(
        json.dumps(
            {
                "migrated_at": datetime.now(UTC).isoformat(),
                "detected_stage": lifecycle.current.value,
                "non_destructive": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return CommandResult(
        stage=lifecycle.current,
        status=ResultStatus.COMPLETE,
        summary="Unified CLI state initialized without modifying engagement artifacts.",
        artifacts=(Artifact("migration", context.relative(marker), "created"),),
        next_command="accel next",
    )


def _scaffold_apply_command(
    scenario_id: str,
    no_retrieval: bool,
    preserve_evals: bool,
) -> str:
    parts = ["accel", "scaffold", "--scenario-id", scenario_id]
    if no_retrieval:
        parts.append("--no-retrieval")
    if preserve_evals:
        parts.append("--preserve-evals")
    parts.append("--apply")
    return render_command(parts)


def _process_failure(stage: Stage, summary: str, process: Any) -> CommandResult:
    return CommandResult(
        stage=stage,
        status=ResultStatus.FAILED,
        summary=summary,
        blocking_issues=(
            Issue(
                "process-failed",
                f"Command exited {process.returncode}: "
                f"{render_command(list(process.command))}",
                process.stderr[-2000:] or process.stdout[-2000:] or None,
            ),
        ),
        details={
            "command": list(process.command),
            "returncode": process.returncode,
            "stdout": process.stdout[-6000:],
            "stderr": process.stderr[-6000:],
        },
    )


def _remove_scaffold_plan(
    context: RepositoryContext,
    paths: list[pathlib.Path],
    *,
    preexisting_dirs: set[pathlib.Path],
) -> list[str]:
    issues: list[str] = []
    for path in reversed(paths):
        if path.is_file():
            try:
                path.unlink()
            except OSError as exc:
                issues.append(f"Could not remove {path}: {exc}")
                continue
        parent = path.parent
        while parent != context.root:
            if parent in preexisting_dirs:
                break
            try:
                parent.rmdir()
            except FileNotFoundError:
                break
            except OSError as exc:
                if parent.exists():
                    issues.append(
                        f"Could not remove generated directory {parent}: {exc}"
                    )
                break
            parent = parent.parent
    return issues


def _uat_markdown(
    acceptance: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    scenario = manifest.get("scenario") or {}
    acceptance_config = manifest.get("acceptance") or {}
    verdict = "PASS" if acceptance.get("accepted") else "FAIL"
    return (
        f"# UAT acceptance report — {scenario.get('id', 'scenario')}\n\n"
        f"**Verdict:** {verdict}\n\n"
        f"**Generated:** {acceptance.get('generated_at', '')}\n\n"
        "## Agreed thresholds\n\n"
        "```yaml\n"
        + yaml.safe_dump(acceptance_config, sort_keys=False).rstrip()
        + "\n```\n\n"
        "## Customer sign-off\n\n"
        "- Sponsor: ____________________\n"
        "- Approver: ___________________\n"
        "- Date: _______________________\n"
        "- Decision: Approve / Reject\n"
    )


def _azd_values(context: RepositoryContext, env: str) -> dict[str, str]:
    entries = {
        item.get("name"): item
        for item in (
            context.load_yaml("deploy/environments.yaml").get("environments")
            or []
        )
        if isinstance(item, dict)
    }
    entry = entries.get(env) or {}
    target = str(entry.get("deployment_target") or "selfhost")
    workspace = _deployment_workspace(context, target)
    path = workspace / ".azure" / env / ".env"
    if path.exists():
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key] = value.strip().strip("'\"")
        return values
    return {}


def _handover_markdown(
    context: RepositoryContext,
    env: str,
    values: dict[str, str],
) -> str:
    manifest = context.manifest()
    scenario = manifest.get("scenario") or {}
    architecture = manifest.get("architecture") or {}
    decision = architecture.get("decision") or {}
    endpoint = next(
        (
            values[key]
            for key in (
                "SERVICE_API_URI",
                "AZURE_CONTAINER_APP_ENDPOINT",
                "FOUNDRY_PROJECT_ENDPOINT",
                "AZURE_AI_FOUNDRY_ENDPOINT",
            )
            if values.get(key)
        ),
        "[PARTNER-FILL REQUIRED: endpoint URL]",
    )
    project = values.get(
        "AZURE_AI_FOUNDRY_PROJECT_NAME",
        "[PARTNER-FILL REQUIRED: Foundry project]",
    )
    return (
        f"# Handover packet — {scenario.get('id', 'scenario')} / {env}\n\n"
        "> Generated locally by `accel handover`. Review every "
        "`PARTNER-FILL REQUIRED` marker before delivery.\n\n"
        "## Deployment\n\n"
        f"- Environment: `{env}`\n"
        f"- Target: `{decision.get('deployment_target', 'unknown')}`\n"
        f"- Endpoint: {endpoint}\n"
        f"- Foundry project: {project}\n"
        f"- Manifest: `accelerator.yaml`\n\n"
        "## Approved architecture\n\n"
        f"- Agent type: `{decision.get('agent_type', 'unknown')}`\n"
        f"- Implementation pattern: "
        f"`{decision.get('implementation_pattern', 'unknown')}`\n"
        f"- Orchestration: `{decision.get('orchestration_pattern', 'unknown')}`\n"
        f"- Application shell: `{decision.get('application_shell', 'unknown')}`\n"
        f"- Approved by: {decision.get('approved_by', 'unknown')}\n"
        f"- Requirements fingerprint: "
        f"`{architecture.get('requirements_fingerprint', 'unknown')}`\n\n"
        "## Acceptance\n\n"
        "- UAT sign-off: `.accelerator/artifacts/uat-signoff.json`\n"
        "- Acceptance report: `.accelerator/artifacts/acceptance-report.json`\n\n"
        "## HITL and operations\n\n"
        "- Approver rota: [PARTNER-FILL REQUIRED]\n"
        "- Alert destinations: [PARTNER-FILL REQUIRED]\n"
        "- Killswitch owner: [PARTNER-FILL REQUIRED]\n"
        "- Rollback owner: [PARTNER-FILL REQUIRED]\n\n"
        "## References\n\n"
        "- `docs/customer-runbook.md`\n"
        "- `docs/discovery/solution-brief.md`\n"
        "- `docs/references/security-review-checklist.md`\n"
    )


def _architecture_decision_block(
    *,
    recommendation: dict[str, Any],
    selected: dict[str, str],
    approved_by: str | None,
    override_reason: str | None,
) -> dict[str, Any]:
    recommended = {
        key: recommendation[key]
        for key in (
            "agent_type",
            "implementation_pattern",
            "orchestration_pattern",
            "application_shell",
            "deployment_target",
            "confidence",
            "rationale",
            "signals",
            "alternatives",
            "score",
        )
    }
    return {
        "status": "approved" if (approved_by or "").strip() else "proposed",
        "requirements_fingerprint": recommendation["requirements_fingerprint"],
        "recommendation": recommended,
        "decision": {
            **selected,
            "approved_by": (approved_by or "").strip() or None,
            "approved_at": (
                datetime.now(UTC).isoformat()
                if (approved_by or "").strip()
                else None
            ),
            "override_reason": (override_reason or "").strip() or None,
        },
        "platform_context": {
            "agent_service_types": ["prompt-agent", "hosted-agent"],
            "implementation_patterns": [
                "managed-prompt",
                "harness",
                "custom-workflow",
            ],
            "workflow_note": (
                "Workflow is modeled as an orchestration pattern, not as a "
                "third Foundry Agent Service runtime type."
            ),
            "harness_note": (
                "Harness is the stable Agent Framework implementation for "
                "hosted single-agent work; experimental capabilities remain off."
            ),
            "references": [
                FOUNDRY_AGENT_OVERVIEW,
                HOSTED_AGENT_GUIDANCE,
                HARNESS_GUIDANCE,
            ],
        },
        "accelerator_support": {
            "foundry-prompt": "supported",
            "hosted-preview": "preview-toolchain",
            "selfhost": "supported",
        },
    }


def _design_command(
    selected: Mapping[str, str],
    *,
    include_approval: bool,
    include_override: bool = False,
) -> str:
    parts = [
        "accel design",
        f"--agent-type {selected['agent_type']}",
        f"--implementation-pattern {selected['implementation_pattern']}",
        f"--orchestration-pattern {selected['orchestration_pattern']}",
        f"--application-shell {selected['application_shell']}",
        f"--deployment-target {selected['deployment_target']}",
    ]
    if include_override:
        parts.append("--override-reason <reason>")
    if include_approval:
        parts.extend(("--approved-by <name>", "--apply"))
    return " ".join(parts)


def _deployment_workspace(
    context: RepositoryContext,
    deployment_target: str,
) -> pathlib.Path:
    if deployment_target == "hosted-preview":
        return context.root / "deploy" / "hosted-preview"
    if deployment_target == "foundry-prompt":
        return context.root / "deploy" / "foundry-prompt"
    return context.root
