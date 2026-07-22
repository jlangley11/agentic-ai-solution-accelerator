from __future__ import annotations

import json
import pathlib

import src.accelerator_cli.lifecycle_commands as lifecycle_commands
from src.accelerator_cli.lifecycle_commands import (
    environment_list,
    handover_approve,
    handover_generate,
    scaffold,
    uat_signoff,
)
from src.accelerator_cli.protocol import ResultStatus
from src.accelerator_cli.repository import RepositoryContext
from src.accelerator_cli.runner import ProcessResult, render_command


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _context(tmp_path: pathlib.Path) -> RepositoryContext:
    (tmp_path / ".git").mkdir()
    _write(
        tmp_path / "accelerator.yaml",
        """
scenario:
  id: sales-research
  package: src.scenarios.sales_research
  agents:
    - id: supervisor
      foundry_name: accel-sales-research-supervisor
acceptance:
  quality_threshold: 0.75
""".lstrip(),
    )
    _write(
        tmp_path / "deploy/environments.yaml",
        """
default_env: dev
environments:
  - name: dev
    github_environment: dev
    deployment_target: selfhost
""".lstrip(),
    )
    return RepositoryContext(tmp_path)


def test_environment_list_reads_manifest(tmp_path: pathlib.Path) -> None:
    result = environment_list(_context(tmp_path))

    assert result.status == ResultStatus.READY
    assert result.details["default_env"] == "dev"
    assert "dev: selfhost" in result.completed[0]


def test_scaffold_dry_run_does_not_write(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    script = tmp_path / "scripts/scaffold-scenario.py"
    script.parent.mkdir(parents=True)
    source = pathlib.Path(__file__).parents[1] / "scripts/scaffold-scenario.py"
    script.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = scaffold(
        context,
        scenario_id="order-triage",
        no_retrieval=True,
        preserve_evals=True,
        apply=False,
    )

    assert result.status == ResultStatus.APPROVAL_REQUIRED
    assert not (tmp_path / "src/scenarios/order_triage").exists()
    assert "order-triage" not in context.manifest_path.read_text(encoding="utf-8")


def test_uat_signoff_and_handover_are_local_artifacts(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    context.artifacts_dir.mkdir(parents=True)
    _write(
        context.artifacts_dir / "acceptance-report.json",
        json.dumps({"accepted": True, "generated_at": "2026-07-21T00:00:00Z"}),
    )

    signoff = uat_signoff(
        context,
        sponsor="Executive Sponsor",
        approver="Customer Approver",
        apply=True,
    )
    handover = handover_generate(context, env="dev", apply=True)
    approval = handover_approve(
        context,
        approver="Customer ops owner",
        apply=True,
    )

    assert signoff.status == ResultStatus.COMPLETE
    assert handover.status == ResultStatus.APPROVAL_REQUIRED
    assert approval.status == ResultStatus.COMPLETE
    assert (context.artifacts_dir / "uat-signoff.json").exists()
    assert (context.artifacts_dir / "handover-dev.md").exists()
    assert (context.artifacts_dir / "handover.json").exists()
    handover_state = json.loads(
        (context.artifacts_dir / "handover.json").read_text(encoding="utf-8")
    )
    assert handover_state["status"] == "approved"


def test_scaffold_rolls_back_when_manifest_update_fails(
    tmp_path: pathlib.Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path)
    script = tmp_path / "scripts/scaffold-scenario.py"
    script.parent.mkdir(parents=True)
    (tmp_path / "docs/agent-specs").mkdir(parents=True)
    (tmp_path / "data/samples").mkdir(parents=True)
    source = pathlib.Path(__file__).parents[1] / "scripts/scaffold-scenario.py"
    script.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    original_manifest = context.manifest_path.read_text(encoding="utf-8")
    original_replace = lifecycle_commands.replace_scenario

    def fail_apply(ctx, block, *, apply):
        if apply:
            raise OSError("manifest is read-only")
        return original_replace(ctx, block, apply=False)

    monkeypatch.setattr(lifecycle_commands, "replace_scenario", fail_apply)

    result = scaffold(
        context,
        scenario_id="rollback-test",
        no_retrieval=True,
        preserve_evals=False,
        apply=True,
    )

    assert result.status == ResultStatus.FAILED
    assert not (tmp_path / "src/scenarios/rollback_test").exists()
    assert context.manifest_path.read_text(encoding="utf-8") == original_manifest
    assert not (tmp_path / "evals/quality/golden_cases.jsonl").exists()
    assert (tmp_path / "docs/agent-specs").is_dir()
    assert (tmp_path / "data/samples").is_dir()


def test_handover_rejects_undeclared_or_unsafe_environment(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    context.artifacts_dir.mkdir(parents=True)
    _write(context.artifacts_dir / "uat-signoff.json", '{"accepted":true}\n')

    unsafe = handover_generate(context, env="../../outside", apply=False)
    missing = handover_generate(context, env="prod", apply=False)

    assert unsafe.status == ResultStatus.BLOCKED
    assert missing.status == ResultStatus.BLOCKED
    assert not (tmp_path / "outside.md").exists()

    _write(
        context.root / "deploy/environments.yaml",
        "default_env: dev\n"
        "environments:\n"
        "  - name: dev\n"
        "    github_environment: dev\n"
        "    deployment_target: hosted_preview\n",
    )
    invalid_target = handover_generate(context, env="dev", apply=False)
    assert invalid_target.status == ResultStatus.BLOCKED
    assert invalid_target.blocking_issues[0].id == "handover-environment-target"


def test_deploy_rejects_target_override(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)

    result = lifecycle_commands.deploy(
        context,
        env="dev",
        region="eastus2",
        target="hosted-preview",
        acknowledge_preview=True,
        execute=False,
        apply=False,
    )

    assert result.status == ResultStatus.BLOCKED
    assert result.blocking_issues[0].id == "deployment-target-drift"


def test_deploy_rejects_invalid_manifest_target(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    _write(
        context.root / "deploy/environments.yaml",
        "default_env: dev\n"
        "environments:\n"
        "  - name: dev\n"
        "    github_environment: dev\n"
        "    deployment_target: hosted_preview\n",
    )

    result = lifecycle_commands.deploy(
        context,
        env="dev",
        region="eastus2",
        target=None,
        acknowledge_preview=False,
        execute=False,
        apply=False,
    )

    assert result.status == ResultStatus.BLOCKED
    assert result.blocking_issues[0].id == "deployment-target-invalid"


def test_deploy_accepts_explicit_matching_target(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)

    result = lifecycle_commands.deploy(
        context,
        env="dev",
        region="eastus2",
        target="selfhost",
        acknowledge_preview=False,
        execute=False,
        apply=False,
    )

    assert result.status == ResultStatus.APPROVAL_REQUIRED
    assert result.blocking_issues == ()


def test_deploy_preview_quotes_python_path_with_spaces(
    tmp_path: pathlib.Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path)
    python_path = r"C:\Program Files\Python\python.exe"
    monkeypatch.setattr(lifecycle_commands.sys, "executable", python_path)

    result = lifecycle_commands.deploy(
        context,
        env="dev",
        region="eastus2",
        target="selfhost",
        acknowledge_preview=False,
        execute=False,
        apply=False,
    )

    assert result.proposed_actions[0].command == render_command(
        [
            python_path,
            str(context.root / "scripts/preflight-deploy.py"),
            "--region",
            "eastus2",
            "--deployment-target",
            "selfhost",
        ]
    )


def test_hosted_apply_runs_provision_then_deploy(
    tmp_path: pathlib.Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path)
    _write(
        context.root / "deploy/environments.yaml",
        "default_env: dev\n"
        "environments:\n"
        "  - name: dev\n"
        "    github_environment: dev\n"
        "    deployment_target: selfhost\n"
        "  - name: hosted-preview\n"
        "    github_environment: hosted-preview\n"
        "    deployment_target: hosted-preview\n",
    )
    calls: list[tuple[list[str], pathlib.Path]] = []

    def fake_run(ctx, command, *, cwd=None, timeout=1800):
        calls.append((list(command), cwd or ctx.root))
        return ProcessResult(tuple(command), 0, "ok", "")

    monkeypatch.setattr(lifecycle_commands, "run_process", fake_run)

    result = lifecycle_commands.deploy(
        context,
        env="hosted-preview",
        region="eastus2",
        target=None,
        acknowledge_preview=True,
        execute=True,
        apply=True,
    )

    assert result.status == ResultStatus.COMPLETE
    assert [call[0][1] for call in calls] == [
        str(context.root / "scripts/preflight-deploy.py"),
        "provision",
        "deploy",
    ]
    assert calls[1][1] == context.root / "deploy/hosted-preview"
    assert calls[2][1] == context.root / "deploy/hosted-preview"


def test_handover_reads_values_from_declared_target_workspace(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    _write(
        context.root / "deploy/environments.yaml",
        "default_env: dev\n"
        "environments:\n"
        "  - name: dev\n"
        "    github_environment: dev\n"
        "    deployment_target: selfhost\n"
        "  - name: hosted-preview\n"
        "    github_environment: hosted-preview\n"
        "    deployment_target: hosted-preview\n",
    )
    context.artifacts_dir.mkdir(parents=True)
    _write(context.artifacts_dir / "uat-signoff.json", '{"accepted":true}\n')
    _write(
        context.root / ".azure/hosted-preview/.env",
        "FOUNDRY_PROJECT_ENDPOINT=https://wrong.example\n",
    )
    _write(
        context.root / "deploy/hosted-preview/.azure/hosted-preview/.env",
        "FOUNDRY_PROJECT_ENDPOINT=https://correct.example\n",
    )

    result = handover_generate(context, env="hosted-preview", apply=False)

    assert result.status == ResultStatus.APPROVAL_REQUIRED
    assert "https://correct.example" in result.details["preview"]
    assert "https://wrong.example" not in result.details["preview"]


def test_scaffold_cleanup_reports_concurrent_files(tmp_path: pathlib.Path) -> None:
    context = _context(tmp_path)
    generated = tmp_path / "new/generated/file.txt"
    sibling = tmp_path / "new/generated/concurrent.txt"
    _write(generated, "generated")
    _write(sibling, "created by another process")

    issues = lifecycle_commands._remove_scaffold_plan(
        context,
        [generated],
        preexisting_dirs={tmp_path},
    )

    assert not generated.exists()
    assert sibling.exists()
    assert issues
    assert "generated directory" in issues[0]


def test_handover_approval_command_uses_host_shell_quoting(
    tmp_path: pathlib.Path,
) -> None:
    context = _context(tmp_path)
    context.artifacts_dir.mkdir(parents=True)
    _write(
        context.artifacts_dir / "handover.json",
        '{"status":"draft","requires_human_review":true}\n',
    )

    result = handover_approve(
        context,
        approver="Jane Doe",
        apply=False,
    )

    assert result.next_command == render_command(
        [
            "accel",
            "handover",
            "approve",
            "--approver",
            "Jane Doe",
            "--apply",
        ]
    )
