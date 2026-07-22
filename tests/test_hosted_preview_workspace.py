"""Focused contract tests for the additive Hosted Agents preview workspace."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import zipfile
from collections.abc import Iterator
from typing import Any

import pytest
import yaml

from src import provisioning
from src.workflow import registry

ROOT = pathlib.Path(__file__).parents[1]
WORKSPACE = ROOT / "deploy" / "hosted-preview"


def _load_hook(name: str) -> Any:
    path = WORKSPACE / "hooks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"hosted_preview_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files(root: pathlib.Path) -> Iterator[pathlib.Path]:
    return (path for path in sorted(root.rglob("*")) if path.is_file())


def _snapshot(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in _files(root)
    }


def test_prepare_replaces_only_generated_source_and_filters_local_artifacts(
    tmp_path: pathlib.Path,
) -> None:
    prepare = _load_hook("prepare")
    repo = tmp_path / "repo"
    workspace = repo / "deploy" / "hosted-preview"
    app = workspace / "app"
    source = repo / "src"
    app.mkdir(parents=True)
    source.mkdir(parents=True)

    (source / "package.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / ".env").write_text("SECRET=do-not-copy\n", encoding="utf-8")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "package.pyc").write_bytes(b"cache")
    (source / ".venv").mkdir()
    (source / ".venv" / "token.txt").write_text("secret", encoding="utf-8")
    (repo / ".azure").mkdir()
    (repo / ".azure" / "local.env").write_text("SECRET=local\n", encoding="utf-8")
    (repo / "accelerator.yaml").write_text("scenario: {}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (repo / "README.md").write_text("# Test package\n", encoding="utf-8")
    (app / "main.py").write_text("committed = True\n", encoding="utf-8")
    (app / "src").mkdir()
    (app / "src" / "stale.py").write_text("stale = True\n", encoding="utf-8")

    prepare.prepare(repo_root=repo, workspace_root=workspace)
    first = _snapshot(app)

    assert (app / "main.py").read_text(encoding="utf-8") == "committed = True\n"
    assert (app / "src" / "package.py").is_file()
    assert (app / "README.md").read_text(encoding="utf-8") == "# Test package\n"
    assert not (app / "src" / "stale.py").exists()
    assert not (app / "src" / ".env").exists()
    assert not (app / "src" / "__pycache__").exists()
    assert not (app / "src" / ".venv").exists()
    assert not (app / ".azure").exists()

    (app / "src" / "unexpected.txt").write_text("remove me", encoding="utf-8")
    prepare.prepare(repo_root=repo, workspace_root=workspace)

    assert _snapshot(app) == first


def test_bootstrap_installs_root_hosted_extra_with_current_python(
    tmp_path: pathlib.Path,
    monkeypatch: Any,
) -> None:
    bootstrap = _load_hook("bootstrap")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    bootstrap.bootstrap(repo_root=tmp_path, python_executable="python-current")

    assert calls == [
        (
            ["python-current", "-m", "pip", "--version"],
            {
                "cwd": tmp_path.resolve(),
                "check": False,
                "capture_output": True,
                "text": True,
            },
        ),
        (
            [
                "python-current",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-e",
                ".[hosted-preview]",
            ],
            {"cwd": tmp_path.resolve(), "check": True},
        ),
    ]


def test_bootstrap_uses_uv_when_selected_python_has_no_pip(
    tmp_path: pathlib.Path,
    monkeypatch: Any,
) -> None:
    bootstrap = _load_hook("bootstrap")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> Any:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            1 if command[-2:] == ["pip", "--version"] else 0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "uv" if name == "uv" else None)

    bootstrap.bootstrap(repo_root=tmp_path, python_executable="python-current")

    assert calls[-1] == [
        "uv",
        "pip",
        "install",
        "--python",
        "python-current",
        "-e",
        ".[hosted-preview]",
    ]


def test_normalize_env_restores_provider_mangled_output_names(
    monkeypatch: Any,
) -> None:
    normalize_env = _load_hook("normalize_env")
    values = {
        key[:-1].lower() + key[-1]: f"value-{index}"
        for index, key in enumerate(normalize_env.CANONICAL_KEYS)
    }
    values["ENABLE_HOSTED_AGENTS"] = "true"
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> Any:
        calls.append(command)
        if "get-values" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(values),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(normalize_env.shutil, "which", lambda name: name)
    normalize_env.normalize(run=fake_run)

    set_calls = [
        call
        for call in calls
        if len(call) >= 5 and call[1:3] == ["env", "set"]
    ]
    assert len(set_calls) == len(normalize_env.CANONICAL_KEYS)
    assert {call[3] for call in set_calls} == set(normalize_env.CANONICAL_KEYS)
    enable_call = next(call for call in set_calls if call[3] == "ENABLE_HOSTED_AGENTS")
    assert enable_call[4] == "true"


def test_normalize_env_fails_when_required_output_is_missing() -> None:
    normalize_env = _load_hook("normalize_env")

    with pytest.raises(RuntimeError, match="AZURE_AI_FOUNDRY_ENDPOINT"):
        normalize_env.canonical_values({})


def test_prepared_app_builds_real_wheel_metadata(tmp_path: pathlib.Path) -> None:
    prepare = _load_hook("prepare")
    workspace = tmp_path / "deploy" / "hosted-preview"
    app = workspace / "app"
    wheelhouse = tmp_path / "wheelhouse"
    app.mkdir(parents=True)

    prepare.prepare(repo_root=ROOT, workspace_root=workspace)
    completed = subprocess.run(  # noqa: S603 - trusted interpreter and test paths
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(app),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    wheels = list(wheelhouse.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        metadata_name = next(
            name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = wheel.read(metadata_name).decode("utf-8")
    assert "Name: agentic-ai-solution-accelerator" in metadata
    assert "Provides-Extra: hosted-preview" in metadata
    assert "# Agentic AI Solution Accelerator" in metadata


def test_postdeploy_delegates_to_shared_registry_and_provisioner(
    monkeypatch: Any,
) -> None:
    postdeploy = _load_hook("postdeploy")
    bundle = object()
    calls: list[tuple[object, bool | None]] = []

    async def fake_provision(
        delegated_bundle: object,
        *,
        canary: bool | None = None,
    ) -> None:
        calls.append((delegated_bundle, canary))

    monkeypatch.setattr(registry, "load_scenario", lambda: bundle)
    monkeypatch.setattr(provisioning, "provision", fake_provision)
    monkeypatch.setenv("HOSTED_PREVIEW_CANARY", "true")

    postdeploy.main()

    assert calls == [(bundle, True)]
    source = (WORKSPACE / "hooks" / "postdeploy.py").read_text(encoding="utf-8")
    assert "load_environment" not in source
    assert "foundry-provision.py" not in source
    assert ".azure" not in source


def test_hosted_preview_manifest_schema_and_environment_contract() -> None:
    data = yaml.safe_load((WORKSPACE / "azure.yaml").read_text(encoding="utf-8"))
    services = data["services"]
    project = services["ai-project"]
    agent = services["hosted-supervisor"]

    assert data["requiredVersions"]["extensions"]["azure.ai.agents"] == ">=1.0.0-beta.6"
    assert data["hooks"]["postprovision"] == {
        "run": "python hooks/normalize_env.py",
    }
    assert data["hooks"]["predeploy"] == [
        {"run": "python hooks/bootstrap.py"},
        {"run": "python hooks/prepare.py"},
    ]
    assert data["infra"] == {
        "provider": "microsoft.foundry",
        "path": "infra",
        "module": "main",
    }
    assert project["host"] == "azure.ai.project"
    assert project["deployments"][0] == {
        "name": "gpt-5-mini",
        "model": {
            "format": "OpenAI",
            "name": "gpt-5-mini",
            "version": "2025-08-07",
        },
        "sku": {"name": "GlobalStandard", "capacity": 30},
    }
    assert agent["host"] == "azure.ai.agent"
    assert agent["kind"] == "hosted"
    assert agent["project"] == "app"
    assert agent["codeConfiguration"] == {
        "dependencyResolution": "remote_build",
        "entryPoint": "main.py",
        "runtime": "python_3_14",
    }
    assert agent["container"]["resources"] == {"cpu": "0.5", "memory": "1Gi"}
    assert {
        (entry["protocol"], entry["version"]) for entry in agent["protocols"]
    } == {("responses", "2.0.0"), ("invocations", "2.0.0")}

    env = {entry["name"]: entry["value"] for entry in agent["environmentVariables"]}
    required = {
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "AZURE_AI_FOUNDRY_ACCOUNT_ENDPOINT",
        "AZURE_AI_FOUNDRY_ACCOUNT_NAME",
        "AZURE_AI_FOUNDRY_PROJECT_NAME",
        "AZURE_AI_FOUNDRY_OPENAI_ENDPOINT",
        "AZURE_AI_FOUNDRY_MODEL",
        "AZURE_AI_FOUNDRY_MODEL_MAP",
        "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT",
        "AZURE_AI_SEARCH_ENDPOINT",
        "AZURE_AI_SEARCH_RESOURCE_ID",
        "AZURE_AI_FOUNDRY_SEARCH_CONNECTION_NAME",
        "AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME",
        "AZURE_AI_FOUNDRY_KB_NAME",
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "HOSTED_AGENT",
        "ENABLE_HOSTED_AGENTS",
    }
    assert required <= env.keys()
    assert all(env[name] == f"${{{name}}}" for name in required)


def test_hosted_bicep_provider_and_runtime_output_contract() -> None:
    bicep = (WORKSPACE / "infra" / "main.bicep").read_text(encoding="utf-8")
    resources = (WORKSPACE / "infra" / "modules" / "resources.bicep").read_text(
        encoding="utf-8"
    )
    required_parameters = {
        "location",
        "resourceGroupName",
        "tags",
        "resourceTokenSalt",
        "foundryProjectName",
        "deployments",
        "connections",
        "principalId",
        "principalType",
        "includeAcr",
        "enableNetworkIsolation",
        "useManagedEgress",
        "vnetId",
        "agentSubnetName",
        "agentSubnetPrefix",
        "createAgentSubnet",
        "peSubnetName",
        "peSubnetPrefix",
        "createPESubnet",
        "managedIsolationMode",
        "dnsZonesResourceGroup",
        "dnsZonesSubscription",
    }
    required_outputs = {
        "AZURE_RESOURCE_GROUP",
        "AZURE_AI_PROJECT_ID",
        "AZURE_AI_ACCOUNT_NAME",
        "AZURE_AI_PROJECT_NAME",
        "AZURE_OPENAI_ENDPOINT",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_CONTAINER_REGISTRY_ENDPOINT",
        "AZURE_CONTAINER_REGISTRY_RESOURCE_ID",
        "AZURE_AI_PROJECT_ACR_CONNECTION_NAME",
        "AZURE_FOUNDRY_NETWORK_MODE",
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "AZURE_AI_FOUNDRY_ACCOUNT_ENDPOINT",
        "AZURE_AI_FOUNDRY_MODEL",
        "AZURE_AI_FOUNDRY_MODEL_MAP",
        "AZURE_AI_FOUNDRY_EMBEDDING_DEPLOYMENT",
        "AZURE_AI_SEARCH_ENDPOINT",
        "AZURE_AI_SEARCH_RESOURCE_ID",
        "AZURE_AI_FOUNDRY_SEARCH_CONNECTION_NAME",
        "AZURE_AI_FOUNDRY_KB_MCP_CONNECTION_NAME",
        "AZURE_AI_FOUNDRY_KB_NAME",
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "HOSTED_AGENT",
        "ENABLE_HOSTED_AGENTS",
    }

    for name in required_parameters:
        assert f"param {name} " in bicep
    for name in required_outputs:
        assert f"output {name} " in bicep
    assert "loadYamlContent('../../../accelerator.yaml')" in bicep
    assert "../../../../infra/modules/foundry.bicep" in resources
    assert "../../../../infra/modules/ai-search.bicep" in resources
    assert "../../../../infra/modules/monitor.bicep" in resources
    combined = bicep + resources
    assert "container-app.bicep" not in combined
    assert "acr.bicep" not in combined
    assert "key-vault.bicep" not in combined
    assert "identity.bicep" not in combined
    assert "conditionVersion: '2.0'" in resources

    parameters = json.loads(
        (WORKSPACE / "infra" / "main.parameters.json").read_text(encoding="utf-8")
    )["parameters"]
    assert parameters["includeAcr"]["value"] is False
    assert parameters["enableNetworkIsolation"]["value"] is False
    assert parameters["principalId"]["value"] == "${AZURE_PRINCIPAL_ID}"
    assert parameters["principalType"]["value"] == "${AZURE_PRINCIPAL_TYPE=User}"
    assert parameters["deployments"]["value"][0]["name"] == "gpt-5-mini"


def test_root_azd_remains_self_hosted_and_shared_principal_type_defaults() -> None:
    root_azd = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))
    assert root_azd["services"]["api"]["host"] == "containerapp"
    assert root_azd["services"]["api"]["docker"]["remoteBuild"] is True
    assert root_azd["infra"] == {"provider": "bicep", "path": "infra", "module": "main"}

    for module_name in ("foundry.bicep", "ai-search.bicep"):
        text = (ROOT / "infra" / "modules" / module_name).read_text(encoding="utf-8")
        assert "param rbacPrincipalType string = 'ServicePrincipal'" in text
        assert "principalType: rbacPrincipalType" in text


def test_hosted_preview_docs_enter_workspace_without_c_flag() -> None:
    readme = (WORKSPACE / "README.md").read_text(encoding="utf-8")

    assert "cd deploy/hosted-preview" in readme
    assert "azd -C deploy/hosted-preview" not in readme
    assert "azd ai agent invoke hosted-supervisor" in readme
    assert "azd ai agent invoke accel-hosted-supervisor" not in readme
    assert "${AZURE_PRINCIPAL_TYPE=User}" in readme
    bootstrap = "python deploy/hosted-preview/hooks/bootstrap.py"
    preflight = "python scripts/preflight-deploy.py"
    prepare = "python deploy/hosted-preview/hooks/prepare.py"
    assert readme.index(bootstrap) < readme.index(preflight) < readme.index(prepare)
