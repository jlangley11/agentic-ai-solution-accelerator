from __future__ import annotations

import pathlib

import yaml

from src.accelerator_cli.architecture_advisor import requirements_fingerprint
from src.accelerator_cli.lifecycle import detect_lifecycle
from src.accelerator_cli.protocol import ResultStatus, Stage
from src.accelerator_cli.repository import RepositoryContext


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: pathlib.Path) -> RepositoryContext:
    (tmp_path / ".git").mkdir()
    _write(
        tmp_path / "accelerator.yaml",
        """
scenario:
  id: demo
  package: src.scenarios.demo
  agents:
    - id: supervisor
      foundry_name: accel-demo-supervisor
  evals:
    quality_dataset: evals/quality/golden_cases.jsonl
    redteam_dataset: evals/redteam/cases.jsonl
""".lstrip(),
    )
    _write(
        tmp_path / "docs/discovery/use-case-canvas.md",
        "# Canvas\n<Customer>\n**Process:** …\n",
    )
    _write(
        tmp_path / "docs/discovery/solution-brief.md",
        "# Solution Brief\n> **STATUS: TEMPLATE.**\n",
    )
    return RepositoryContext(tmp_path)


def _approve_architecture(
    context: RepositoryContext,
    brief: str,
    *,
    target: str = "selfhost",
) -> None:
    data = yaml.safe_load(context.manifest_path.read_text(encoding="utf-8"))
    data["architecture"] = {
        "status": "approved",
        "requirements_fingerprint": requirements_fingerprint(brief),
        "recommendation": {},
        "decision": {
            "agent_type": "hosted-agent",
            "orchestration_pattern": "supervisor-routing",
            "application_shell": "workbench",
            "deployment_target": target,
            "approved_by": "Test",
            "approved_at": "2026-07-22T00:00:00+00:00",
        },
    }
    context.manifest_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def test_template_repository_starts_at_qualification(tmp_path: pathlib.Path) -> None:
    state = detect_lifecycle(_repo(tmp_path))

    assert state.current == Stage.QUALIFY
    assert state.for_stage(Stage.QUALIFY).status == ResultStatus.NEEDS_INPUT


def test_complete_brief_advances_to_missing_scaffold(tmp_path: pathlib.Path) -> None:
    context = _repo(tmp_path)
    _write(
        context.brief_path,
        "# Solution Brief — Contoso\n\nApproved customer requirements.\n",
    )
    _write(
        context.root / "docs/discovery/use-case-canvas.md",
        "# Canvas — Contoso\n\n**Process:** Review supplier risk.\n",
    )

    state = detect_lifecycle(context)

    assert state.for_stage(Stage.QUALIFY).status == ResultStatus.COMPLETE
    assert state.for_stage(Stage.DISCOVER).status == ResultStatus.COMPLETE
    assert state.current == Stage.DESIGN


def test_materialized_scenario_advances_to_provision(tmp_path: pathlib.Path) -> None:
    context = _repo(tmp_path)
    brief = "# Solution Brief — Contoso\n\nApproved.\n"
    _write(context.brief_path, brief)
    _approve_architecture(context, brief)
    _write(
        context.root / "docs/discovery/use-case-canvas.md",
        "# Canvas — Contoso\n\n**Process:** Review supplier risk.\n",
    )
    package = context.root / "src/scenarios/demo"
    _write(package / "schema.py", "class ScenarioRequest: ...\n")
    _write(package / "workflow.py", "def build_workflow(): ...\n")
    (package / "agents").mkdir(parents=True)
    _write(
        context.root / "docs/agent-specs/accel-demo-supervisor.md",
        "# Agent\n",
    )
    _write(
        context.root / "evals/quality/golden_cases.jsonl",
        '{"case_id":"q-1"}\n',
    )
    _write(
        context.root / "evals/redteam/cases.jsonl",
        '{"case_id":"r-1"}\n',
    )

    state = detect_lifecycle(context)

    assert state.for_stage(Stage.SCAFFOLD).status == ResultStatus.COMPLETE
    assert state.current == Stage.PROVISION


def test_undeclared_hosted_state_does_not_complete_selfhost_provision(
    tmp_path: pathlib.Path,
) -> None:
    context = _repo(tmp_path)
    brief = "# Solution Brief — Contoso\n\nApproved.\n"
    _write(context.brief_path, brief)
    _approve_architecture(context, brief)
    _write(
        context.root / "docs/discovery/use-case-canvas.md",
        "# Canvas — Contoso\n\n**Process:** Review supplier risk.\n",
    )
    package = context.root / "src/scenarios/demo"
    _write(package / "schema.py", "class ScenarioRequest: ...\n")
    _write(package / "workflow.py", "def build_workflow(): ...\n")
    (package / "agents").mkdir(parents=True)
    _write(context.root / "docs/agent-specs/accel-demo-supervisor.md", "# Agent\n")
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
    _write(
        context.root
        / "deploy/hosted-preview/.azure/other-hosted-name/.env",
        "FOUNDRY_PROJECT_ENDPOINT=https://hosted.example\n",
    )

    state = detect_lifecycle(context)

    assert state.for_stage(Stage.PROVISION).status == ResultStatus.READY


def test_invalid_manifest_target_blocks_provision_stage(
    tmp_path: pathlib.Path,
) -> None:
    context = _repo(tmp_path)
    _write(
        context.root / "deploy/environments.yaml",
        "default_env: dev\n"
        "environments:\n"
        "  - name: dev\n"
        "    github_environment: dev\n"
        "    deployment_target: hosted_preview\n",
    )

    state = detect_lifecycle(context)

    assert state.for_stage(Stage.PROVISION).status == ResultStatus.BLOCKED
    assert "unsupported targets" in state.for_stage(Stage.PROVISION).summary
