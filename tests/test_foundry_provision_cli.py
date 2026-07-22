"""Tests for deterministic provisioning CLI environment handling."""
from __future__ import annotations

import importlib.util
import pathlib
from unittest.mock import AsyncMock

import pytest

from src import provisioning
from src.workflow import registry

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "foundry-provision.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("foundry_provision_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_env(root: pathlib.Path, name: str, content: str) -> pathlib.Path:
    path = root / ".azure" / name / ".env"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_env_file_supports_comments_blank_lines_and_quotes(
    tmp_path: pathlib.Path,
) -> None:
    cli = _load_module()
    path = tmp_path / ".env"
    path.write_text(
        "\n# azd values\nPLAIN=value\nSINGLE='hello world'\nDOUBLE=\"a=b\"\nEMPTY=\n",
        encoding="utf-8",
    )

    assert cli.parse_env_file(path) == {
        "PLAIN": "value",
        "SINGLE": "hello world",
        "DOUBLE": "a=b",
        "EMPTY": "",
    }


def test_parse_env_file_decodes_azd_double_quoted_escapes(
    tmp_path: pathlib.Path,
) -> None:
    cli = _load_module()
    path = tmp_path / ".env"
    path.write_text(
        r'DOUBLE="dollar=\$ bang=\! tick=\` quote=\" slash=\\ '
        r'newline=\n carriage=\r tab=\t unknown=\q windows=C:\\Users\\agent"'
        "\n",
        encoding="utf-8",
    )

    assert cli.parse_env_file(path)["DOUBLE"] == (
        'dollar=$ bang=! tick=` quote=" slash=\\ '
        "newline=\n carriage=\r tab=\t unknown=\\q windows=C:\\Users\\agent"
    )


def test_parse_env_file_keeps_single_quoted_values_literal(
    tmp_path: pathlib.Path,
) -> None:
    cli = _load_module()
    path = tmp_path / ".env"
    path.write_text(
        r"SINGLE='dollar=$ bang=! tick=` quote=\' slash=\\ "
        r"newline=\n windows=C:\\Users\\agent'"
        "\n",
        encoding="utf-8",
    )

    assert cli.parse_env_file(path)["SINGLE"] == (
        "dollar=$ bang=! tick=` quote=' slash=\\ "
        "newline=\\n windows=C:\\Users\\agent"
    )


@pytest.mark.parametrize("line", ["NOT_AN_ASSIGNMENT", "1BAD=value", "BAD='open"])
def test_parse_env_file_rejects_malformed_lines(
    tmp_path: pathlib.Path,
    line: str,
) -> None:
    cli = _load_module()
    path = tmp_path / ".env"
    path.write_text(f"{line}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed|unterminated"):
        cli.parse_env_file(path)


def test_load_environment_preserves_process_values(tmp_path: pathlib.Path) -> None:
    cli = _load_module()
    selected = _write_env(tmp_path, "dev", "KEEP=file\nADD=loaded\n")
    environ = {"KEEP": "process"}

    assert cli.load_environment("dev", root=tmp_path, environ=environ) == selected
    assert environ == {"KEEP": "process", "ADD": "loaded"}


def test_select_env_file_uses_named_or_sole_environment(tmp_path: pathlib.Path) -> None:
    cli = _load_module()
    dev = _write_env(tmp_path, "dev", "A=1\n")

    assert cli.select_env_file(None, root=tmp_path, environ={"AZD_ENV_NAME": "dev"}) == dev
    assert cli.select_env_file(None, root=tmp_path, environ={}) == dev


def test_select_env_file_rejects_ambiguous_environments(tmp_path: pathlib.Path) -> None:
    cli = _load_module()
    _write_env(tmp_path, "dev", "A=1\n")
    _write_env(tmp_path, "prod", "A=2\n")

    with pytest.raises(RuntimeError, match="multiple azd environments.*--env"):
        cli.select_env_file(None, root=tmp_path, environ={})


def test_select_env_file_allows_fully_configured_process_env(
    tmp_path: pathlib.Path,
) -> None:
    cli = _load_module()
    assert cli.select_env_file(None, root=tmp_path, environ={"CONFIGURED": "1"}) is None


def test_cli_propagates_canary_and_skip_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_module()
    bundle = object()
    delegated = AsyncMock()
    monkeypatch.setattr(cli, "load_environment", lambda _env: None)
    monkeypatch.setattr(registry, "load_scenario", lambda: bundle)
    monkeypatch.setattr(provisioning, "provision", delegated)

    cli.main(["--env", "dev", "--canary", "--skip-seed"])

    delegated.assert_awaited_once_with(bundle, skip_seed=True, canary=True)
