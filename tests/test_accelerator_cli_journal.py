from __future__ import annotations

import json
import pathlib

from src.accelerator_cli import main as cli_main
from src.accelerator_cli.repository import RepositoryContext


def test_journal_failure_does_not_replace_successful_result(
    tmp_path: pathlib.Path,
    monkeypatch,
    capsys,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".accelerator").mkdir()
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
    monkeypatch.setattr(
        cli_main,
        "record_operation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    exit_code = cli_main.main(["--json", "status"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 10
    assert payload["status"] == "needs_input"
    assert "disk full" in captured.err
