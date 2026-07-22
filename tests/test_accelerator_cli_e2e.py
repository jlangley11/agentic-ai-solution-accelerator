from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).parents[1]


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(
    repo: pathlib.Path,
    *args: str,
    expected: tuple[int, ...] = (0,),
) -> dict:
    completed = subprocess.run(  # noqa: S603 - trusted interpreter and module
        [sys.executable, "-m", "src.accelerator_cli", *args, "--json"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode in expected, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "customer"
    (repo / ".git").mkdir(parents=True)
    _write(
        repo / "docs/discovery/use-case-canvas.md",
        "# Use-case canvas — Contoso\n\n"
        "**Process:** Analysts review supplier risk before approval.\n",
    )
    _write(
        repo / "docs/discovery/solution-brief.md",
        "# Solution Brief — Contoso\n\n"
        "## 5. Solution shape\n\n"
        "Pattern: supervisor-routing\n\n"
        "## 5b. UX shape\n\n"
        "ux_shape: Structured form + report\n\n"
        "## 5c. UX inputs\n\n"
        "| Field | Type | Description | Required |\n"
        "|---|---|---|---|\n"
        "| query | text | Supplier to review | yes |\n\n"
        "## 5d. UX output sections\n\n"
        "| Section | Content | Source agent |\n"
        "|---|---|---|\n"
        "| Result | Risk result | supervisor |\n\n"
        "## 5e. Data and access contract\n\n"
        "| Source | Owner | Classification | Contains PII? | "
        "Caller identity / ACL enforcement | Refresh | Retention |\n"
        "|---|---|---|---|---|---|---|\n"
        "| Supplier data | Procurement | internal | no | workload MI | daily | 30d |\n\n"
        "## 6. Constraints & risks\n\nRAI risks: none identified for fixture.\n",
    )
    _write(
        repo / "accelerator.yaml",
        "schema_version: '1.0'\n"
        "landing_zone:\n"
        "  mode: standalone\n"
        "scenario:\n"
        "  id: old\n"
        "  package: src.scenarios.old\n"
        "  request_schema: schema:ScenarioRequest\n"
        "  workflow_factory: workflow:build_workflow\n"
        "  endpoint:\n"
        "    path: /old/stream\n"
        "  agents:\n"
        "    - id: supervisor\n"
        "      foundry_name: accel-old-supervisor\n"
        "acceptance:\n"
        "  quality_threshold: 0.75\n"
        "solution:\n"
        "  grounding_sources: []\n",
    )
    _write(
        repo / "deploy/environments.yaml",
        "default_env: dev\n"
        "environments:\n"
        "  - name: dev\n"
        "    github_environment: dev\n"
        "    deployment_target: selfhost\n",
    )
    (repo / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/scaffold-scenario.py", repo / "scripts/scaffold-scenario.py")
    return repo


def test_local_customer_engagement_reaches_operate_state(
    tmp_path: pathlib.Path,
) -> None:
    repo = _repo(tmp_path)
    source = repo / "customer-requirements.csv"
    _write(source, "id,requirement\nR1,Use Entra ID for every end user\n")

    status = _run(repo, "status", expected=(30,))
    assert status["stage"] == "scaffold"

    intake = _run(repo, "intake", "add", str(source))
    source_id = intake["completed"][0].split(":", 1)[0]
    blocked = _run(
        repo,
        "intake",
        "review",
        source_id,
        "--include-text",
        expected=(30,),
    )
    assert blocked["status"] == "blocked"

    _run(
        repo,
        "intake",
        "disclose",
        source_id,
        "approved_for_model",
        "--apply",
    )
    requirement = _run(
        repo,
        "intake",
        "requirement",
        "add",
        "--category",
        "identity",
        "--statement",
        "Use Entra ID for every end user.",
        "--evidence",
        f"{source_id}:c001",
        "--apply",
    )
    requirement_id = requirement["details"]["requirement"]["id"]
    _run(
        repo,
        "intake",
        "requirement",
        "decide",
        requirement_id,
        "approved",
        "--by",
        "Security Lead",
        "--apply",
    )
    _run(
        repo,
        "intake",
        "requirement",
        "link",
        requirement_id,
        "--type",
        "quality_eval",
        "--target",
        "evals/quality/golden_cases.jsonl#q-001",
        "--apply",
    )
    _run(repo, "intake", "requirement", "export", "--apply")
    assert (repo / "docs/discovery/requirements-traceability.md").exists()

    preview = _run(
        repo,
        "scaffold",
        "--scenario-id",
        "supplier-risk",
        "--no-retrieval",
        "--dry-run",
        expected=(20,),
    )
    assert preview["status"] == "approval_required"
    applied = _run(
        repo,
        "scaffold",
        "--scenario-id",
        "supplier-risk",
        "--no-retrieval",
        "--apply",
    )
    assert applied["status"] == "complete"
    assert (repo / "src/scenarios/supplier_risk/schema.py").exists()

    _write(
        repo / ".azure/dev/.env",
        "SERVICE_API_URI=https://contoso.example\n"
        "AZURE_AI_FOUNDRY_PROJECT_NAME=contoso-project\n",
    )
    _write(repo / "evals/redteam/cases.jsonl", '{"case_id":"r-001"}\n')
    after_scaffold = _run(repo, "status", expected=(0,))
    assert after_scaffold["stage"] == "uat"

    _write(
        repo / ".accelerator/artifacts/acceptance-report.json",
        json.dumps(
            {
                "generated_at": "2026-07-22T00:00:00Z",
                "api_url": "https://contoso.example",
                "accepted": True,
                "commands": [],
            }
        ),
    )
    _run(repo, "uat", "report", expected=(20,))
    _run(
        repo,
        "uat",
        "signoff",
        "--sponsor",
        "Executive Sponsor",
        "--approver",
        "UAT Lead",
        "--apply",
    )
    _run(repo, "handover", "generate", "--env", "dev", "--apply", expected=(20,))
    _run(
        repo,
        "handover",
        "approve",
        "--approver",
        "Customer Ops",
        "--apply",
    )
    operate = _run(repo, "operate", "status")

    assert operate["stage"] == "operate"
    assert operate["status"] == "ready"
    journal = (repo / ".accelerator/operations.jsonl").read_text(encoding="utf-8")
    assert '"command":"intake.disclose"' in journal
    assert '"command":"intake.requirement.add"' in journal
    assert '"command":"handover.approve"' in journal
    assert "Use Entra ID for every end user" not in journal
