from __future__ import annotations

import json

from src.accelerator_cli import main as cli_main
from src.accelerator_cli.repository import RepositoryContext


def test_status_json_uses_versioned_contract(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs/discovery").mkdir(parents=True)
    (tmp_path / "docs/discovery/solution-brief.md").write_text(
        "# Brief\n> **STATUS: TEMPLATE.**\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/discovery/use-case-canvas.md").write_text(
        "# Canvas\n<Customer>\n**Process:** …\n",
        encoding="utf-8",
    )
    (tmp_path / "accelerator.yaml").write_text(
        "scenario:\n  id: demo\n  package: src.scenarios.demo\n  agents: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        RepositoryContext,
        "discover",
        classmethod(lambda cls, start=None: RepositoryContext(tmp_path)),
    )

    exit_code = cli_main.main(["--json", "status"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 10
    assert payload["schema_version"] == "1.1"
    assert payload["stage"] == "qualify"


def test_conflicting_dry_run_and_apply_fails_without_writing(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs/discovery").mkdir(parents=True)
    (tmp_path / "docs/discovery/solution-brief.md").write_text(
        "# Brief\nApproved.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/discovery/use-case-canvas.md").write_text(
        "# Canvas\n**Process:** Approved.\n",
        encoding="utf-8",
    )
    (tmp_path / "accelerator.yaml").write_text(
        "scenario:\n  id: demo\n  package: src.scenarios.demo\n  agents: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        RepositoryContext,
        "discover",
        classmethod(lambda cls, start=None: RepositoryContext(tmp_path)),
    )

    exit_code = cli_main.main(
        [
            "--json",
            "scaffold",
            "--scenario-id",
            "conflict-test",
            "--dry-run",
            "--apply",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 40
    assert payload["status"] == "failed"
    assert not (tmp_path / "src/scenarios/conflict_test").exists()


def test_global_output_flags_work_after_subcommand(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs/discovery").mkdir(parents=True)
    (tmp_path / "docs/discovery/solution-brief.md").write_text(
        "# Brief\n> **STATUS: TEMPLATE.**\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/discovery/use-case-canvas.md").write_text(
        "# Canvas\n<Customer>\n**Process:** …\n",
        encoding="utf-8",
    )
    (tmp_path / "accelerator.yaml").write_text(
        "scenario:\n  id: demo\n  package: src.scenarios.demo\n  agents: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        RepositoryContext,
        "discover",
        classmethod(lambda cls, start=None: RepositoryContext(tmp_path)),
    )

    exit_code = cli_main.main(["status", "--json", "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 10
    assert payload["stage"] == "qualify"


def test_global_flag_like_option_value_is_not_relocated() -> None:
    parser = cli_main.build_parser()
    normalized = cli_main._normalize_global_options(
        parser,
        [
            "intake",
            "requirement",
            "decide",
            "req-123",
            "approved",
            "--note",
            "--verbose",
            "--apply",
        ],
    )
    args = parser.parse_args(normalized)

    assert args.note == "--verbose"
    assert args.verbose is False


def test_double_dash_preserves_global_flag_like_positional() -> None:
    parser = cli_main.build_parser()
    normalized = cli_main._normalize_global_options(
        parser,
        ["intake", "add", "--", "--pretty"],
    )
    args = parser.parse_args(normalized)

    assert args.paths == ["--pretty"]
    assert args.pretty is False
