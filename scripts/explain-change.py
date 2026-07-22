"""scripts/explain-change.py — preflight report for the current change.

Reads ``git diff --name-only <base>...HEAD`` (plus the index and the
worktree), categorizes each file against the accelerator's static rule
catalog, and prints a concise report covering:

  * which ``scripts/accelerator-lint.py`` checks are likely to fire,
  * which evals run,
  * what the deploy pipeline will do on the next ``azd up``,
  * which ``accelerator.yaml`` manifest sections are affected,
  * a recommended pre-commit command list tailored to the diff.

Usage:
    python scripts/explain-change.py                      # diff vs main
    python scripts/explain-change.py --base origin/main   # custom base
    python scripts/explain-change.py --json               # machine-readable
    python scripts/explain-change.py --quiet              # summary only

Exit code is always 0 unless the underlying ``git`` call fails — this is
a preflight aid, not a gate. The CI gates (``accelerator-lint``,
``evals``) remain authoritative.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Static catalog: glob pattern -> (category id, impact block).
#
# The first matching pattern wins. Order matters: narrow patterns first,
# generic catch-alls last. The ``impact`` block is free-form text that
# names specific ``@check`` functions in ``scripts/accelerator-lint.py``
# and specific ``evals/*`` entry points. Kept in sync by hand; the
# ``category_catalog_matches_lint`` quickcheck at the end of main() warns
# if any referenced rule isn't actually defined in the lint file.
# ---------------------------------------------------------------------------
@dataclass
class Category:
    id: str
    title: str
    impact: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)


CATEGORIES: list[Category] = [
    Category(
        id="accelerator-cli",
        title="Unified accelerator CLI",
        impact=[
            "tests: accelerator CLI protocol, lifecycle, intake, command, and MCP suites",
            "docs: regenerate docs/reference/accelerator-cli.md when command help changes",
            "portability: sync .agents/skills/accelerator into .claude/skills/accelerator",
        ],
        patterns=[
            "src/accelerator_cli/**",
            "src/accelerator_mcp/**",
            ".agents/skills/**",
            ".claude/skills/**",
            "scripts/sync-agent-skill.py",
            "scripts/generate-cli-docs.py",
        ],
    ),
    Category(
        id="agent-three-layer",
        title="Worker agent (prompt/transform/validate)",
        impact=[
            "lint: agents_three_layer, no_print_statements, no_hardcoded_secrets",
            "evals: quality/run.py exercises this worker through every golden case that lists it under `exercises[]`",
            "if this is a NEW agent: also expect agent_has_golden_case + agents_registered_in_manifest_match_code to fire until the golden-case exercises[] and accelerator.yaml -> scenario.agents[] are updated",
        ],
        patterns=[
            "src/scenarios/*/agents/*/prompt.py",
            "src/scenarios/*/agents/*/transform.py",
            "src/scenarios/*/agents/*/validate.py",
            "src/scenarios/*/agents/*/__init__.py",
        ],
    ),
    Category(
        id="agents-init",
        title="Scenario agents/__init__.py (scaffold-managed)",
        impact=[
            "lint: agents_three_layer verifies every agent still has the 3-layer shape",
            "risk: hand edits that break the ``from . import (...)`` / ``__all__`` shape flip the file to 'no longer scaffold-managed' and block future scripts/scaffold-agent.py runs",
            "remediation: restore canonical shape (see src/scenarios/sales_research/agents/__init__.py) or re-scaffold",
        ],
        patterns=[
            "src/scenarios/*/agents/__init__.py",
        ],
    ),
    Category(
        id="scenario-workflow",
        title="Scenario workflow.py (WORKERS registry + DAG)",
        impact=[
            "lint: agents_three_layer, agents_registered_in_manifest_match_code, agent_has_golden_case",
            "evals: full quality + redteam suite against the flagship endpoint",
            "if the WORKERS dict shape changed: scripts/scaffold-agent.py may no longer be able to patch it; keep the single-form shape documented in the scaffolder",
        ],
        patterns=[
            "src/scenarios/*/workflow.py",
        ],
    ),
    Category(
        id="scenario-manifest",
        title="accelerator.yaml (scenario manifest)",
        impact=[
            "lint: manifest_present, scenario_manifest_valid, agent_has_golden_case, acceptance_wired_to_evals, agent_specs_no_hardcoded_model, models_block_shape, agent_model_refs_exist",
            "evals: acceptance thresholds come from accelerator.yaml -> acceptance; changes here move the quality gate",
            "runtime: src/main.py reads this file at startup to mount /<scenario.endpoint.path>; path changes are breaking",
            "models: changes to the `models:` block are parsed at compile time by `infra/main.bicep` via `loadYamlContent` and re-shape foundry.bicep deployments (slug->deployment_name map). Removing the block converges back to template defaults (gpt-5-mini / 2025-08-07 / cap 30); raw env-var overrides of the default are NOT supported.",
        ],
        patterns=[
            "accelerator.yaml",
        ],
    ),
    Category(
        id="golden-cases",
        title="Golden cases (evals/quality/golden_cases.jsonl)",
        impact=[
            "lint: golden_cases_exercises_valid (per-case referential integrity), agent_has_golden_case (every registered worker exercised)",
            "evals: quality/run.py re-runs every case against the deployed endpoint; redteam unaffected",
        ],
        patterns=[
            "evals/quality/golden_cases.jsonl",
        ],
    ),
    Category(
        id="evals-runtime",
        title="Eval runners (evals/*/run.py)",
        impact=[
            "lint: pr_evals_installs_project (PR workflow must install the project, not just httpx/pyyaml)",
            "evals: every change here runs through the PR-time evals.yml gate + the post-deploy evals job",
            "note: evals must read the scenario.request_schema from accelerator.yaml — not hardcode fields",
        ],
        patterns=[
            "evals/quality/run.py",
            "evals/redteam/run.py",
            "evals/**/*.py",
        ],
    ),
    Category(
        id="evals-datasets",
        title="Redteam dataset / other eval data",
        impact=[
            "evals: redteam/run.py or related eval runner consumes this; full redteam pass required before deploy",
        ],
        patterns=[
            "evals/redteam/*.jsonl",
            "evals/**/*.yaml",
            "evals/**/*.yml",
        ],
    ),
    Category(
        id="infra-bicep",
        title="Infrastructure (Bicep)",
        impact=[
            "lint: bicep_has_model_deployment, bicep_has_content_filter (raiPolicies), no_preview_api_versions, key_vault_rbac_only, container_app_uses_managed_identity, uses_default_azure_credential, shared_assets_not_scenario_specific",
            "deploy: next `azd up` will re-provision affected resources; partners may hit quota or region constraints",
            "RBAC: Search roles must be Search Service Contributor + Search Index Data Contributor (the in-app FastAPI startup bootstrap, src/bootstrap.py, requires Contributor to upload seed docs as the workload MI)",
        ],
        patterns=[
            "infra/**/*.bicep",
            "infra/**/*.bicepparam",
            "infra/**/*.json",
        ],
    ),
    Category(
        id="deploy-workflow",
        title="Deploy workflow (.github/workflows/deploy.yml)",
        impact=[
            "lint: deploy_gated_on_lint_and_evals, deploy_matrix_matches_azure_envs, workflow_secrets_documented",
            "runtime: next push to main (or workflow_dispatch) exercises the chain accelerator-lint -> resolve-env -> azd-up -> evals",
            "never add Azure envs by editing this file; add a row to deploy/environments.yaml via /deploy-to-env instead",
        ],
        patterns=[
            ".github/workflows/deploy.yml",
        ],
    ),
    Category(
        id="evals-workflow",
        title="PR evals workflow (.github/workflows/evals.yml)",
        impact=[
            "lint: pr_evals_installs_project, workflow_secrets_documented",
            "runtime: this workflow is the PR merge gate — runs quality + redteam against vars.EVALS_API_URL",
        ],
        patterns=[
            ".github/workflows/evals.yml",
        ],
    ),
    Category(
        id="other-workflows",
        title="Other GitHub workflows",
        impact=[
            "lint: ci_workflows_present, workflow_secrets_documented",
            "runtime: varies per workflow (lint.yml = per-PR; version-matrix.yml = scheduled)",
        ],
        patterns=[
            ".github/workflows/*.yml",
        ],
    ),
    Category(
        id="deploy-environments",
        title="BYO-Azure manifest (deploy/environments.yaml)",
        impact=[
            "lint: deploy_matrix_matches_azure_envs (BLOCKING) — manifest shape + deploy.yml wiring cross-check",
            "partners: a new entry also needs a matching GitHub Environment + OIDC federated credential (see /deploy-to-env)",
        ],
        patterns=[
            "deploy/environments.yaml",
        ],
    ),
    Category(
        id="lint-tool",
        title="Lint tool itself (scripts/accelerator-lint.py)",
        impact=[
            "meta: every check in the file re-runs; expect the next CI run to reflect any new/removed @check function",
            "remediation: run `python scripts/accelerator-lint.py` locally BEFORE push to catch self-inflicted regressions",
        ],
        patterns=[
            "scripts/accelerator-lint.py",
        ],
    ),
    Category(
        id="scaffolders",
        title="Scaffolder scripts",
        impact=[
            "smoke test: run the scaffolder against a throwaway id, confirm lint 0/0, then revert (scripts/scaffold-agent.py supports this pattern with `git checkout` after the dry run)",
            "contract: scripts/scaffold-agent.py enforces a single-form shape on agents/__init__.py and workflow.py; changes here must keep that contract documented",
        ],
        patterns=[
            "scripts/scaffold-agent.py",
            "scripts/scaffold-scenario.py",
        ],
    ),
    Category(
        id="azure-yaml",
        title="azd project manifest (azure.yaml)",
        impact=[
            "runtime: azd reads this to resolve service projects, infra module, and pre/postprovision hooks. A shape change here affects every `azd up` and `azd deploy`.",
            "hooks: pre/postprovision shell scripts run against the azd env; add hooks here rather than wrapping azd in CI scripts.",
            "partners: if you changed hooks, verify scripts/ entries are executable and lint-clean before pushing.",
        ],
        patterns=[
            "azure.yaml",
        ],
    ),
    Category(
        id="landing-zone",
        title="Azure AI Landing Zone (Tier 2 AVM / Tier 3 ALZ) artifacts",
        impact=[
            "lint: landing_zone_mode_consistent — asserts infra/ shape matches accelerator.yaml `landing_zone.mode` (standalone | avm | alz-integrated).",
            "Tier 2 (avm): partners copy exemplars from infra/avm-reference/ into infra/modules/. Changes to exemplars should keep WAF/CAF baseline (soft-delete, purge protection, diagnostics, RBAC-only).",
            "Tier 3 (alz-integrated): subscription-scope deploy in infra/alz-overlay/ runs BEFORE the workload deploy. CHANGEME placeholders MUST be replaced; lint fails if any remain.",
            "docs: /configure-landing-zone agent walks partners between tiers. Keep docs/patterns/azure-ai-landing-zone/README.md in sync with changes here.",
        ],
        patterns=[
            "infra/avm-reference/**",
            "infra/alz-overlay/**",
            "docs/patterns/azure-ai-landing-zone/**",
        ],
    ),
    Category(
        id="other-scripts",
        title="Other helper scripts (scripts/*.py)",
        impact=[
            "no dedicated lint rule; ruff covers style. Verify the script still runs standalone after your change.",
            "if the script is called from a workflow, update both together",
        ],
        patterns=[
            "scripts/*.py",
        ],
    ),
    Category(
        id="agent-specs",
        title="Foundry agent specs (docs/agent-specs/*.md)",
        impact=[
            "lint: agent_specs_no_hardcoded_model — specs must not pin a model; model_deployment_name comes from Bicep outputs",
            "note: these `.md` files ARE the source of truth for system instructions; src/bootstrap.py rewrites the Foundry agent definition (model + instructions + tools) on every `azd deploy`. Edits in the Foundry portal are transient and overwritten on next sync.",
        ],
        patterns=[
            "docs/agent-specs/*.md",
        ],
    ),
    Category(
        id="onboarding-doc",
        title="Onboarding / getting-started docs",
        impact=[
            "lint: workflow_secrets_documented — every secret/var referenced in .github/workflows/*.yml MUST be listed in docs/getting-started/setup-and-prereqs.md",
            "partner UX: this is the authoritative setup doc; keep the 15-minute path in sync with the actual deploy chain",
        ],
        patterns=[
            "docs/getting-started/setup-and-prereqs.md",
        ],
    ),
    Category(
        id="copilot-cascade",
        title="Copilot / custom-agent cascade",
        impact=[
            "lint: copilot_assets_present, no_dead_paths",
            "cascade: AGENTS.md + .github/copilot-instructions.md + .github/agents/*.agent.md must stay coherent — partners discover features via all three surfaces",
        ],
        patterns=[
            ".github/copilot-instructions.md",
            "AGENTS.md",
            "CLAUDE.md",
            ".github/agents/*.agent.md",
        ],
    ),
    Category(
        id="container-build",
        title="Container build (Dockerfile / pyproject / ga-versions)",
        impact=[
            "lint: dockerfile_matches_ga_pins, dockerfile_copies_manifest, sdks_pinned_to_ga",
            "runtime: the container image is rebuilt on every azd deploy; pin drift here silently deploys a mismatched SDK",
        ],
        patterns=[
            "Dockerfile",
            "src/Dockerfile",
            "pyproject.toml",
            "src/pyproject.toml",
            "requirements.txt",
            "src/requirements.txt",
            "ga-versions.yaml",
        ],
    ),
    Category(
        id="tools",
        title="Side-effect tools (src/tools/*.py)",
        impact=[
            "lint: side_effect_tools_call_hitl — every tool must route writes through src/accelerator_baseline/hitl.py",
            "evals: add a redteam case exercising the tool's guardrail path",
        ],
        patterns=[
            "src/tools/*.py",
        ],
    ),
    Category(
        id="baseline",
        title="accelerator_baseline primitives",
        impact=[
            "warning: src/accelerator_baseline/ is for framework primitives only — do NOT add SDK wrappers or scenario logic here",
            "lint: emits_typed_events, uses_default_azure_credential",
        ],
        patterns=[
            "src/accelerator_baseline/*.py",
        ],
    ),
    Category(
        id="src-python",
        title="Other Python source",
        impact=[
            "lint: ruff (src/patterns/scripts), pyright (src/patterns)",
            "smoke: `python -c 'from src.main import app; print(\"OK\")'` after change",
        ],
        patterns=[
            "src/**/*.py",
            "patterns/**/*.py",
        ],
    ),
    Category(
        id="docs-other",
        title="Other documentation",
        impact=[
            "lint: no_dead_paths — removes references to deleted modules/files",
            "no pipeline impact; docs changes do not trigger redeploy",
        ],
        patterns=[
            "**/*.md",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------
def _match_posix(path: str, pattern: str) -> bool:
    # fnmatch with `**` behaves like shell globstar only when the path
    # separators are '/'; callers normalize accordingly.
    if "**" in pattern:
        prefix, suffix = pattern.split("**", 1)
        if not path.startswith(prefix):
            return False
        # suffix begins with '/'; match anywhere after prefix
        tail = suffix.lstrip("/")
        if not tail:
            return True
        # allow any depth: check against each progressive suffix
        for i in range(len(path) - len(tail) + 1):
            if fnmatch.fnmatch(path[i:], tail):
                return True
        return False
    return fnmatch.fnmatchcase(path, pattern)


def _categorize(path: str) -> Category | None:
    normalized = path.replace("\\", "/")
    for cat in CATEGORIES:
        for pattern in cat.patterns:
            if _match_posix(normalized, pattern):
                return cat
    return None


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------
def _git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        sys.exit("git is not available on PATH")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"git {args} failed: {exc.stderr.strip() or exc}")
    return result.stdout


def _diff_files(base: str) -> list[tuple[str, str]]:
    """Return a list of (status, path) tuples covering committed+staged+unstaged.

    status is a single letter: A/M/D/R/C/U/? (untracked).
    """
    seen: dict[str, str] = {}

    def record(status: str, path: str) -> None:
        path = path.strip()
        if not path:
            return
        # Prefer the "most recent" status; D wins over M if the file was
        # ultimately deleted. Simple last-write-wins suffices here.
        seen[path] = status

    # committed diff vs base
    raw = _git(["diff", "--name-status", f"{base}...HEAD"]).splitlines()
    for line in raw:
        parts = line.split("\t")
        if len(parts) >= 2:
            record(parts[0][0], parts[-1])

    # staged
    for line in _git(["diff", "--name-status", "--cached"]).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            record(parts[0][0], parts[-1])

    # unstaged worktree
    for line in _git(["diff", "--name-status"]).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            record(parts[0][0], parts[-1])

    # untracked
    for path in _git(["ls-files", "--others", "--exclude-standard"]).splitlines():
        record("?", path)

    return sorted((s, p) for p, s in seen.items())


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass
class Report:
    base: str
    files: list[tuple[str, str]]
    buckets: dict[str, list[tuple[str, str]]]  # category id -> file tuples
    uncategorized: list[tuple[str, str]]

    def to_dict(self) -> dict:
        by_cat = {c.id: {"title": c.title, "impact": c.impact, "files": self.buckets.get(c.id, [])}
                  for c in CATEGORIES if c.id in self.buckets}
        return {
            "base": self.base,
            "files": self.files,
            "categories": by_cat,
            "uncategorized": self.uncategorized,
            "recommended_commands": _recommended_commands(self.buckets),
        }


def _recommended_commands(buckets: dict[str, list]) -> list[str]:
    cmds: list[str] = []
    present = set(buckets.keys())

    # Always-run core checks.
    cmds.append("python scripts/accelerator-lint.py")
    if present & {"agent-three-layer", "agents-init", "scenario-workflow",
                  "scenario-manifest", "src-python", "baseline", "tools"}:
        cmds.append("python -c \"from src.main import app; print('OK')\"")
    if "agent-three-layer" in present or "scenario-workflow" in present:
        # round-trip the scaffolder as a regression check.
        cmds.append("python scripts/scaffold-agent.py probe_agent --scenario sales-research --capability \"probe\" --depends-on account_planner  # then revert")
    if "golden-cases" in present or "scenario-manifest" in present:
        cmds.append("python -c \"import json; [json.loads(l) for l in open('evals/quality/golden_cases.jsonl', encoding='utf-8') if l.strip()]; print('golden_cases OK')\"")
    if "deploy-workflow" in present or "deploy-environments" in present:
        cmds.append("python -c \"import yaml; yaml.safe_load(open('.github/workflows/deploy.yml', encoding='utf-8')); yaml.safe_load(open('deploy/environments.yaml', encoding='utf-8')); print('deploy YAML OK')\"")
    if "infra-bicep" in present:
        cmds.append("# manual: review infra/**.bicep diff — next `azd up` will re-provision")
    if "container-build" in present:
        cmds.append("# manual: confirm Dockerfile + pyproject + ga-versions.yaml all agree")
    return cmds


def build_report(base: str) -> Report:
    files = _diff_files(base)
    buckets: dict[str, list[tuple[str, str]]] = {}
    uncategorized: list[tuple[str, str]] = []
    for status, path in files:
        cat = _categorize(path)
        if cat is None:
            uncategorized.append((status, path))
        else:
            buckets.setdefault(cat.id, []).append((status, path))
    return Report(base=base, files=files, buckets=buckets, uncategorized=uncategorized)


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------
def _status_summary(files: Iterable[tuple[str, str]]) -> str:
    counts: dict[str, int] = {}
    for status, _ in files:
        counts[status] = counts.get(status, 0) + 1
    order = ["A", "M", "D", "R", "C", "?", "U"]
    parts = [f"{counts[s]} {s}" for s in order if s in counts]
    return ", ".join(parts) if parts else "no changes"


def render_text(report: Report, *, quiet: bool = False) -> str:
    lines: list[str] = []
    lines.append(f"change preflight vs {report.base}")
    lines.append("=" * (len(lines[0])))
    lines.append(f"files: {len(report.files)} ({_status_summary(report.files)})")
    if not report.files:
        lines.append("(nothing to do)")
        return "\n".join(lines) + "\n"
    if quiet:
        cats = ", ".join(c.title for c in CATEGORIES if c.id in report.buckets)
        lines.append(f"categories: {cats or '(none)'}")
        if report.uncategorized:
            lines.append(f"uncategorized: {len(report.uncategorized)}")
        return "\n".join(lines) + "\n"

    lines.append("")
    for cat in CATEGORIES:
        bucket = report.buckets.get(cat.id)
        if not bucket:
            continue
        lines.append(f"== {cat.title} ({len(bucket)} files)")
        for status, path in bucket:
            lines.append(f"  [{status}] {path}")
        for impact in cat.impact:
            lines.append(f"  - {impact}")
        lines.append("")

    if report.uncategorized:
        lines.append(f"== Uncategorized ({len(report.uncategorized)} files)")
        for status, path in report.uncategorized:
            lines.append(f"  [{status}] {path}")
        lines.append("  - no known lint / eval / deploy impact; still covered by ruff/pyright if python")
        lines.append("")

    lines.append("== Recommended pre-commit")
    for cmd in _recommended_commands(report.buckets):
        lines.append(f"  $ {cmd}")
    lines.append("")
    lines.append("Note: CI gates (accelerator-lint, evals) remain authoritative. This")
    lines.append("report is a preflight aid and does not run them.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight report for the current change.")
    parser.add_argument("--base", default="main",
                        help="Base ref to diff against (default: main).")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON.")
    parser.add_argument("--quiet", action="store_true",
                        help="One-line summary only.")
    args = parser.parse_args(argv)

    report = build_report(args.base)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_text(report, quiet=args.quiet), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
