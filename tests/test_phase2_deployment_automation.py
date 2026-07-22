"""Focused tests for additive Phase 2 deployment automation."""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"
ENVIRONMENTS = ROOT / "deploy" / "environments.yaml"
PREFLIGHT = ROOT / "scripts" / "preflight-deploy.py"
TEARDOWN = ROOT / "scripts" / "teardown-preflight.py"
ACCELERATOR_LINT = ROOT / "scripts" / "accelerator-lint.py"
SESSION_FIXTURE = ROOT / "tests" / "fixtures" / "azd-agent-session-create.json"
PROMPT_AZURE = ROOT / "deploy" / "foundry-prompt" / "azure.yaml"


def _load_script(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _needs(job: dict[str, Any]) -> set[str]:
    value = job.get("needs") or []
    return {value} if isinstance(value, str) else set(value)


def test_environment_manifest_has_additive_targets_and_selfhost_default() -> None:
    manifest = yaml.safe_load(ENVIRONMENTS.read_text(encoding="utf-8"))
    entries = {entry["name"]: entry for entry in manifest["environments"]}

    assert manifest["default_env"] == "dev"
    assert entries["dev"]["deployment_target"] == "selfhost"
    assert entries["hosted-preview"] == {
        "name": "hosted-preview",
        "github_environment": "hosted-preview",
        "deployment_target": "hosted-preview",
        "description": (
            "Explicit preview-only Microsoft Foundry Hosted Agents deployment; "
            "never the default."
        ),
    }
    assert entries["prompt-agent"]["deployment_target"] == "foundry-prompt"


def test_foundry_prompt_workspace_is_agent_only() -> None:
    data = yaml.safe_load(PROMPT_AZURE.read_text(encoding="utf-8"))

    assert set(data["services"]) == {"ai-project"}
    assert data["infra"]["path"] == "../hosted-preview/infra"
    assert "hosted-supervisor" not in data["services"]
    postprovision = data["hooks"]["postprovision"]
    assert [step["run"] for step in postprovision] == [
        "python ../hosted-preview/hooks/normalize_env.py",
        "python ../../scripts/foundry-provision.py",
    ]


def test_workflow_target_gates_dependencies_and_nested_working_directory() -> None:
    jobs = _workflow()["jobs"]
    selfhost = jobs["azd-up"]
    prompt = jobs["foundry-prompt"]
    hosted = jobs["hosted-preview"]
    evals = jobs["evals"]

    assert {"accelerator-lint", "resolve-env"} <= _needs(selfhost)
    assert {"accelerator-lint", "resolve-env"} <= _needs(prompt)
    assert {"accelerator-lint", "resolve-env"} <= _needs(hosted)
    assert {"azd-up", "resolve-env"} <= _needs(evals)
    assert "deployment_target == 'selfhost'" in selfhost["if"]
    assert "deployment_target == 'foundry-prompt'" in prompt["if"]
    assert "deployment_target == 'hosted-preview'" in hosted["if"]
    assert "always()" in evals["if"]
    assert "deployment_target == 'selfhost'" in evals["if"]
    assert "needs.azd-up.result == 'success'" in evals["if"]
    assert hosted["environment"] == "${{ needs.resolve-env.outputs.github_environment }}"
    assert prompt["environment"] == "${{ needs.resolve-env.outputs.github_environment }}"

    nested_commands = (
        "azd env ",
        "azd provision",
        "azd deploy",
        "azd ai agent show",
        "azd ai agent sessions create",
        "azd ai agent invoke",
    )
    for step in hosted["steps"]:
        run = str(step.get("run") or "")
        if any(command in run for command in nested_commands):
            assert step["working-directory"] == "deploy/hosted-preview"
    hosted_text = yaml.safe_dump(hosted)
    assert "azd -C" not in hosted_text


def test_workflow_resolves_target_installs_exact_extensions_and_smokes() -> None:
    jobs = _workflow()["jobs"]
    resolve = next(
        step["run"]
        for step in jobs["resolve-env"]["steps"]
        if step.get("id") == "resolve"
    )
    hosted_job = jobs["hosted-preview"]
    hosted = yaml.safe_dump(hosted_job)
    hosted_runs = "\n".join(
        str(step.get("run") or "") for step in hosted_job["steps"]
    )

    assert "deployment_target" in jobs["resolve-env"]["outputs"]
    assert 'match.get("deployment_target") or "selfhost"' in resolve
    assert (
        'allowed_targets = {"selfhost", "foundry-prompt", "hosted-preview"}'
        in resolve
    )
    assert (
        "azd ext install azure.ai.agents --version 1.0.0-beta.6 --force --no-prompt"
        in hosted_runs
    )
    assert (
        "azd ext install microsoft.foundry --version 1.0.0-beta.1 --force --no-prompt"
        in hosted_runs
    )
    assert "--deployment-target hosted-preview" in hosted_runs
    assert "--acknowledge-preview" in hosted_runs
    assert "azd ai agent show hosted-supervisor -o json" in hosted_runs
    assert "azd ai agent sessions create -o json" in hosted_runs
    assert "--protocol responses" in hosted_runs
    assert "--new-conversation" in hosted_runs
    assert '"company_name":"Contoso"' in hosted_runs
    assert '"icp_definition":' in hosted_runs
    assert '"our_solution":' in hosted_runs
    assert "AZURE_PRINCIPAL_TYPE: ServicePrincipal" in hosted
    assert "AZURE_PRINCIPAL_ID: ${{ vars.AZURE_PRINCIPAL_ID }}" in hosted
    assert 'azd env set AZURE_PRINCIPAL_ID "$AZURE_PRINCIPAL_ID"' in hosted_runs
    assert 'azd env set AZURE_PRINCIPAL_TYPE "$AZURE_PRINCIPAL_TYPE"' in hosted_runs
    assert "azd env list -o json --no-prompt" in hosted_runs
    assert "azd env select" in hosted_runs
    assert "azd env new" in hosted_runs
    assert not re.search(r"azd env new[^\n]*\|\|", hosted_runs)
    assert hosted_runs.index("azd env set AZURE_PRINCIPAL_TYPE") < hosted_runs.index(
        "azd provision"
    )
    prompt_runs = "\n".join(
        str(step.get("run") or "")
        for step in jobs["foundry-prompt"]["steps"]
    )
    assert "--deployment-target foundry-prompt" in prompt_runs
    assert "azd provision" in prompt_runs
    assert "azd deploy" not in prompt_runs
    assert (
        "azd ext install microsoft.foundry --version 1.0.0-beta.1 "
        "--force --no-prompt"
        in prompt_runs
    )


def test_workflow_session_parser_reads_real_azd_json_field_first() -> None:
    fixture = SESSION_FIXTURE.read_text(encoding="utf-8")
    workflow = _workflow()
    smoke = next(
        step["run"]
        for step in workflow["jobs"]["hosted-preview"]["steps"]
        if step.get("name") == "Smoke invoke Responses endpoint with fresh session"
    )
    script = next(
        script
        for script in re.findall(r"python - <<'PY'\n(.*?)\nPY", smoke, re.DOTALL)
        if "find_session_id" in script
    )

    assert script.index('value.get("agent_session_id")') < script.index(
        'value.get("sessionId")'
    )
    env = {**os.environ, "SESSION_JSON": fixture}
    completed = subprocess.run(  # noqa: S603 - trusted interpreter and repository script
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "sess_01JZ7Y8M4A2Q9X6K3P5N1R0TVC"


def test_workflow_embedded_python_is_syntactically_valid() -> None:
    workflow = _workflow()
    scripts: list[str] = []
    for job in workflow["jobs"].values():
        for step in job.get("steps") or []:
            run = str(step.get("run") or "")
            scripts.extend(re.findall(r"python - <<'PY'\n(.*?)\nPY", run, re.DOTALL))

    assert len(scripts) >= 3
    for index, script in enumerate(scripts):
        compile(script, f"deploy-workflow-heredoc-{index}.py", "exec")


def test_deployment_lint_rules_accept_phase2_contract() -> None:
    lint = _load_script("phase2_accelerator_lint", ACCELERATOR_LINT)

    assert lint.deploy_gated_on_lint_and_evals(lint.Ctx()) == []
    assert lint.deploy_matrix_matches_azure_envs(lint.Ctx()) == []


def test_version_parser_handles_stable_and_prerelease_output() -> None:
    preflight = _load_script("phase2_preflight_versions", PREFLIGHT)

    assert preflight.parse_version("azd version 1.28.0 (commit abc)") > preflight.parse_version(
        "1.27.1"
    )
    assert preflight.parse_version("1.0.0-beta.6") == preflight.parse_version("1.0.0b6")
    assert preflight.parse_version("1.0.0-beta.5") < preflight.parse_version(
        "1.0.0-beta.6"
    )
    assert preflight.parse_version("1.0.0") > preflight.parse_version("1.0.0-rc.9")
    assert preflight.parse_version("not a version") is None


def test_azd_and_extension_checks_use_mocked_subprocesses(monkeypatch: Any) -> None:
    preflight = _load_script("phase2_preflight_subprocess", PREFLIGHT)
    outputs = [
        SimpleNamespace(
            returncode=0,
            stdout="azd version 1.28.0 (commit abc)\n",
            stderr="",
        ),
        SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "azure.ai.agents",
                        "installedVersion": "1.0.0-beta.6",
                    },
                    {
                        "id": "microsoft.foundry",
                        "installedVersion": "1.0.0-beta.1",
                    },
                ]
            ),
            stderr="",
        ),
        SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "azure.ai.agents",
                        "installedVersion": "1.0.0-beta.6",
                    },
                    {
                        "id": "microsoft.foundry",
                        "installedVersion": "1.0.0-beta.1",
                    },
                ]
            ),
            stderr="",
        ),
    ]
    calls: list[list[str]] = []

    monkeypatch.setattr(preflight.shutil, "which", lambda name: f"C:\\tools\\{name}.cmd")

    def fake_run(argv: list[str], **_kwargs: Any) -> Any:
        calls.append(argv)
        return outputs.pop(0)

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    assert preflight.check_azd_version().status == "pass"
    assert preflight.check_agents_extension_version().status == "pass"
    assert preflight.check_foundry_extension_version().status == "pass"
    assert len(calls) == 3
    assert all("azd.cmd" in " ".join(call) for call in calls)


def test_hosted_ack_python_region_and_rp_contract(monkeypatch: Any) -> None:
    preflight = _load_script("phase2_preflight_hosted", PREFLIGHT)

    assert preflight.check_preview_acknowledged(False).status == "fail"
    assert preflight.check_preview_acknowledged(True).status == "pass"
    assert preflight.check_python_version((3, 12, 9)).status == "fail"
    assert preflight.check_python_version((3, 13, 0)).status == "pass"
    assert len(preflight.HOSTED_PREVIEW_REGIONS) == 29
    assert preflight.check_hosted_preview_region("West US 3").status == "pass"
    assert preflight.check_hosted_preview_region("westus2").status == "fail"
    assert "Microsoft.App" not in preflight.HOSTED_PREVIEW_REQUIRED_RPS
    assert "Microsoft.KeyVault" not in preflight.HOSTED_PREVIEW_REQUIRED_RPS
    assert "Microsoft.ManagedIdentity" not in preflight.HOSTED_PREVIEW_REQUIRED_RPS

    seen: list[str] = []

    def fake_az(args: list[str], **_kwargs: Any) -> tuple[int, str, str]:
        seen.append(args[3])
        return 0, "Registered", ""

    monkeypatch.setattr(preflight, "_az", fake_az)
    assert preflight.check_resource_providers("hosted-preview").status == "pass"
    assert seen == preflight.HOSTED_PREVIEW_REQUIRED_RPS
    seen.clear()
    assert preflight.check_resource_providers("foundry-prompt").status == "pass"
    assert seen == preflight.HOSTED_PREVIEW_REQUIRED_RPS


def test_teardown_renders_target_specific_operator_commands(
    tmp_path: pathlib.Path,
    capsys: Any,
) -> None:
    teardown = _load_script("phase2_teardown", TEARDOWN)

    assert teardown.teardown_commands("dev") == [
        "azd down -e dev --purge --force"
    ]
    assert teardown.teardown_commands("hosted-preview", "hosted-preview") == [
        "cd deploy/hosted-preview",
        "azd down -e hosted-preview --purge --force",
    ]
    assert teardown.teardown_commands("prompt-agent", "foundry-prompt") == [
        "cd deploy/foundry-prompt",
        "azd down -e prompt-agent --purge --force",
    ]

    result = teardown.run_post_teardown(
        "missing-hosted-env",
        "hosted-preview",
        root=tmp_path,
    )
    output = capsys.readouterr().out
    assert result == 2
    assert "does not provision a Key Vault" in output
    assert "Cognitive Services" in output
    assert "Cannot resolve" in output
    assert "[PASS]" not in output


def test_teardown_query_failures_are_not_reported_as_clean(
    capsys: Any,
    monkeypatch: Any,
) -> None:
    teardown = _load_script("phase2_teardown_query_failure", TEARDOWN)
    monkeypatch.setattr(
        teardown,
        "_list_soft_deleted_cog_services",
        lambda: (_ for _ in ()).throw(RuntimeError("authorization failed")),
    )

    assert teardown.run_post_teardown("dev") == 2
    assert "authorization failed" in capsys.readouterr().out


def test_teardown_resolves_hashed_hosted_account_and_matches_exact(
    tmp_path: pathlib.Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    teardown = _load_script("phase2_teardown_hashed", TEARDOWN)
    account_name = "aifnd7f4c9e2b1d6a"
    env_file = (
        tmp_path
        / "deploy"
        / "hosted-preview"
        / ".azure"
        / "hosted-preview"
        / ".env"
    )
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        f'AZURE_AI_FOUNDRY_ACCOUNT_NAME="{account_name}"\n'
        "AZURE_AI_ACCOUNT_NAME=lower-priority-name\n",
        encoding="utf-8",
    )
    deleted = [
        {"name": account_name, "location": "westus3"},
        {"name": "legacy-hosted-preview-account", "location": "westus3"},
        {"name": "unrelated-account", "location": "westus3"},
    ]
    monkeypatch.setattr(teardown, "_list_soft_deleted_cog_services", lambda: deleted)
    monkeypatch.setattr(teardown, "_list_soft_deleted_keyvaults", lambda: [])

    assert (
        teardown.resolve_cognitive_account_name(
            "hosted-preview",
            "hosted-preview",
            root=tmp_path,
        )
        == account_name
    )
    result = teardown.run_post_teardown(
        "hosted-preview",
        "hosted-preview",
        root=tmp_path,
    )
    output = capsys.readouterr().out

    assert result == 1
    assert f"Expected Cognitive Services account: {account_name}" in output
    assert account_name in output
    assert "legacy-hosted-preview-account" not in output
    assert "unrelated-account" not in output


def test_teardown_uses_legacy_substring_only_without_exact_account(
    tmp_path: pathlib.Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    teardown = _load_script("phase2_teardown_legacy", TEARDOWN)
    deleted = [
        {"name": "legacy-dev-account", "location": "eastus2"},
        {"name": "unrelated-account", "location": "eastus2"},
    ]
    monkeypatch.setattr(teardown, "_list_soft_deleted_cog_services", lambda: deleted)
    monkeypatch.setattr(teardown, "_list_soft_deleted_keyvaults", lambda: [])

    result = teardown.run_post_teardown("dev", root=tmp_path)
    output = capsys.readouterr().out

    assert result == 1
    assert "Expected account name unavailable" in output
    assert "legacy-dev-account" in output
    assert "unrelated-account" not in output


def test_teardown_account_override_wins_over_environment(
    tmp_path: pathlib.Path,
) -> None:
    teardown = _load_script("phase2_teardown_override", TEARDOWN)
    env_file = tmp_path / ".azure" / "dev" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("AZURE_AI_ACCOUNT_NAME=from-file\n", encoding="utf-8")

    assert (
        teardown.resolve_cognitive_account_name(
            "dev",
            root=tmp_path,
        )
        == "from-file"
    )
    assert (
        teardown.resolve_cognitive_account_name(
            "dev",
            override=" explicit-account ",
            root=tmp_path,
        )
        == "explicit-account"
    )


def test_custom_agent_docs_cover_target_preview_permissions_and_cwd() -> None:
    deploy_doc = (ROOT / ".github" / "agents" / "deploy-to-env.agent.md").read_text(
        encoding="utf-8"
    )
    teardown_doc = (ROOT / ".github" / "agents" / "teardown.agent.md").read_text(
        encoding="utf-8"
    )

    for text in (deploy_doc, teardown_doc):
        assert "deployment-target hosted-preview" in text
        assert "cd deploy/hosted-preview" in text
        assert "azd -C" in text
    assert "--acknowledge-preview" in deploy_doc
    assert "Role Based Access Control Administrator" in deploy_doc
    assert "Role Based Access Control Administrator" in " ".join(teardown_doc.split())
    assert "Contributor alone is not sufficient" in " ".join(deploy_doc.split())
    assert "does not provision a Key Vault" in teardown_doc
    assert "AZURE_PRINCIPAL_TYPE=ServicePrincipal" in deploy_doc
    assert "AZURE_PRINCIPAL_ID" in deploy_doc
    assert "${AZURE_PRINCIPAL_TYPE=User}" in deploy_doc
    assert "--cognitive-account-name" in teardown_doc
