from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).parents[1]
LINT_PATH = ROOT / "scripts" / "accelerator-lint.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("harness_runtime_lint", LINT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_runtime(root: pathlib.Path, extra: str = "") -> None:
    path = root / "src/workflow/harness.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "create_harness_agent\n"
        "FoundryChatClient\n"
        "DefaultAzureCredential\n"
        "parse_agent_instructions\n"
        "tools=None\n"
        "disable_file_memory=True\n"
        "file_access_store=None\n"
        "background_agents=None\n"
        "shell_executor=None\n"
        "disable_web_search=True\n"
        "disable_tool_auto_approval=True\n"
        "loop_should_continue=None\n"
        'otel_provider_name="accelerator.harness"\n'
        f"{extra}",
        encoding="utf-8",
    )


def test_harness_safe_defaults_pass(tmp_path, monkeypatch) -> None:
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    _write_runtime(tmp_path)

    assert lint.harness_runtime_safe_defaults(lint.Ctx()) == []


def test_harness_experimental_features_are_blocked(tmp_path, monkeypatch) -> None:
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    _write_runtime(
        tmp_path,
        "background_agents=[worker]\n",
    )

    findings = lint.harness_runtime_safe_defaults(lint.Ctx())

    assert any("background_agents" in finding.message for finding in findings)
