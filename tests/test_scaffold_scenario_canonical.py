"""Verify scaffold-scenario.py emits a shape that scaffold-agent.py accepts.

Regression test for a pre-existing bug where freshly-scaffolded scenarios
emitted ``from . import supervisor`` (single name) and no ``WORKERS`` dict,
causing ``/add-worker-agent`` to fail on every non-flagship scenario.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCAFFOLD_SCENARIO = ROOT / "scripts" / "scaffold-scenario.py"
SCAFFOLD_AGENT = ROOT / "scripts" / "scaffold-agent.py"


def _load_scaffold_agent():
    spec = importlib.util.spec_from_file_location("scaffold_agent", SCAFFOLD_AGENT)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    sys.modules["scaffold_agent"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fresh_scenario():
    """Scaffold a temp scenario; clean up after the test."""
    sid = "contoso-canonical-test"
    leaf = sid.replace("-", "_")
    paths = [
        ROOT / "src" / "scenarios" / leaf,
        ROOT / "docs" / "agent-specs" / f"accel-{sid}-supervisor.md",
        ROOT / "data" / "samples" / f"{leaf}.json",
    ]
    for p in paths:
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    # Snapshot golden_cases.jsonl since scaffold-scenario rewrites it.
    golden = ROOT / "evals" / "quality" / "golden_cases.jsonl"
    golden_backup = golden.read_bytes() if golden.exists() else None
    result = subprocess.run(  # noqa: S603 — fixed argv, not user input
        [sys.executable, str(SCAFFOLD_SCENARIO), sid],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"scaffold failed: {result.stderr}"
    yield ROOT / "src" / "scenarios" / leaf
    for p in paths:
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    if golden_backup is not None:
        golden.write_bytes(golden_backup)


def test_scaffolded_workflow_has_canonical_workers_dict(fresh_scenario):
    workflow_py = (fresh_scenario / "workflow.py").read_text(encoding="utf-8")
    tree = ast.parse(workflow_py)
    workers_nodes = [
        n for n in tree.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "WORKERS"
        and isinstance(n.value, ast.Dict)
    ]
    assert len(workers_nodes) == 1, "expected exactly one annotated WORKERS dict"
    assert workers_nodes[0].value.keys == [], "freshly scaffolded WORKERS must be empty"


def test_scaffolded_agents_init_uses_tuple_import(fresh_scenario):
    agents_init = (fresh_scenario / "agents" / "__init__.py").read_text(encoding="utf-8")
    import re
    pkg_re = re.compile(
        r"^from \. import \(\s*([^)]*?)\s*\)\s*$",
        re.MULTILINE | re.DOTALL,
    )
    all_re = re.compile(
        r"^__all__\s*=\s*\[\s*([^\]]*?)\s*\]\s*$",
        re.MULTILINE | re.DOTALL,
    )
    assert pkg_re.search(agents_init), \
        "agents/__init__.py must use `from . import (...)` tuple form"
    assert all_re.search(agents_init), \
        "agents/__init__.py must use `__all__ = [...]` list form"


def test_scaffold_agent_can_patch_freshly_scaffolded_scenario(fresh_scenario):
    """The full contract: scaffold-agent.py's patch fns must accept the output."""
    sa = _load_scaffold_agent()
    agents_init_path = fresh_scenario / "agents" / "__init__.py"
    workflow_path = fresh_scenario / "workflow.py"

    patched_init = sa._patch_agents_init(
        agents_init_path.read_text(encoding="utf-8"), "risk_scoring"
    )
    patched_wf = sa._patch_workflow(
        workflow_path.read_text(encoding="utf-8"), "risk_scoring", [], True
    )
    ast.parse(patched_init)
    ast.parse(patched_wf)

    assert "risk_scoring" in patched_init
    assert '"risk_scoring": WorkerSpec(' in patched_wf
    assert "_build_input_risk_scoring" in patched_wf
