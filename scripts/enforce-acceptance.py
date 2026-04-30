"""Enforce every threshold in accelerator.yaml.acceptance.

Called from .github/workflows/evals.yml after quality + redteam runs.

Inputs:
  accelerator.yaml           -> acceptance block
  evals/quality/results.jsonl
  evals/redteam/results.jsonl

Exit non-zero if any threshold is violated. Prints a failure table.

When ``GITHUB_STEP_SUMMARY`` is set (CI), also writes a markdown
scoreboard there: per-case pass/fail with score / latency / cost columns
and the acceptance verdict, so the GitHub Actions run page surfaces the
result without forcing partners to download the JSONL artifact.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import yaml

from src.accelerator_baseline.evals import Acceptance, EvalResult, evaluate_acceptance

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Cap per-suite rows in the step summary so a 500-case suite doesn't
# overflow GitHub's 1MB summary limit. Failures always render in full;
# passes are truncated.
_MAX_SUMMARY_ROWS_PER_SUITE = 50


def _load_results(path: pathlib.Path, suite: str) -> list[EvalResult]:
    out: list[EvalResult] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(EvalResult(
            case_id=d["case_id"],
            suite=suite,
            passed=bool(d.get("passed", False)),
            score=d.get("score"),
            groundedness=d.get("groundedness"),
            latency_ms=d.get("latency_ms"),
            cost_usd=d.get("cost_usd"),
            reason=d.get("reason"),
        ))
    return out


def _fmt(value: object, spec: str = "") -> str:
    if value is None:
        return "—"
    try:
        return format(value, spec) if spec else str(value)
    except (TypeError, ValueError):
        return str(value)


def _render_summary(
    quality: list[EvalResult],
    redteam: list[EvalResult],
    acc: Acceptance,
    accepted: bool,
    failures: list[str],
) -> str:
    lines: list[str] = []
    verdict = "✅ ACCEPT" if accepted else "❌ REJECT"
    lines.append(f"## Eval acceptance: {verdict}\n")
    lines.append(
        f"| Gate | Threshold |\n"
        f"|---|---|\n"
        f"| `quality_threshold` | ≥ {acc.quality_threshold} |\n"
        f"| `groundedness_threshold` | ≥ {acc.groundedness_threshold} |\n"
        f"| `p95_latency_ms` | ≤ {acc.p95_latency_ms} |\n"
        f"| `cost_per_call_usd` | ≤ {acc.cost_per_call_usd} |\n"
        f"| `redteam_must_pass` | {acc.redteam_must_pass} |\n"
    )
    if failures:
        lines.append("\n### Acceptance failures\n")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    for suite_name, results in (("Quality", quality), ("Redteam", redteam)):
        lines.append(f"\n### {suite_name} ({len(results)} cases)\n")
        # failures first, then passes
        sorted_results = sorted(results, key=lambda r: (r.passed, r.case_id))
        rendered = sorted_results[:_MAX_SUMMARY_ROWS_PER_SUITE]
        truncated = len(sorted_results) - len(rendered)
        lines.append("| case_id | passed | score | latency_ms | cost_usd | reason |")
        lines.append("|---|---|---|---|---|---|")
        for r in rendered:
            mark = "✅" if r.passed else "❌"
            lines.append(
                f"| `{r.case_id}` | {mark} | {_fmt(r.score, '.3f')} "
                f"| {_fmt(r.latency_ms)} | {_fmt(r.cost_usd, '.4f')} "
                f"| {_fmt(r.reason)} |"
            )
        if truncated > 0:
            lines.append(f"\n_…{truncated} additional passing cases truncated._")

    lines.append(
        "\n---\n"
        "**Trace each failure:** open the App Insights ROI-KPIs workbook → "
        "*Latest failures and rejected actions* panel → click `operation_Id` "
        "(see `docs/customer-runbook.md#from-kpi-to-trace`)."
    )
    return "\n".join(lines) + "\n"


def _write_step_summary(text: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError as exc:
        # Don't fail the gate just because the summary file is unwritable.
        print(f"warning: could not write GITHUB_STEP_SUMMARY ({exc})", file=sys.stderr)


def main() -> int:
    manifest = yaml.safe_load((ROOT / "accelerator.yaml").read_text(encoding="utf-8"))
    acc_block = manifest.get("acceptance", {}) or {}
    acc = Acceptance(
        quality_threshold=float(acc_block.get("quality_threshold", 0.0)),
        groundedness_threshold=float(acc_block.get("groundedness_threshold", 0.0)),
        p95_latency_ms=int(acc_block.get("p95_latency_ms", 0)),
        cost_per_call_usd=float(acc_block.get("cost_per_call_usd", 0.0)),
        redteam_must_pass=bool(acc_block.get("redteam_must_pass", True)),
    )

    quality = _load_results(ROOT / "evals/quality/results.jsonl", "quality")
    redteam = _load_results(ROOT / "evals/redteam/results.jsonl", "redteam")

    if not quality:
        print("::error::no quality results (evals/quality/results.jsonl is empty)")
        _write_step_summary(
            "## Eval acceptance: ❌ REJECT\n\nNo quality results found "
            "(`evals/quality/results.jsonl` empty).\n"
        )
        return 1
    if not redteam:
        print("::error::no redteam results (evals/redteam/results.jsonl is empty)")
        _write_step_summary(
            "## Eval acceptance: ❌ REJECT\n\nNo redteam results found "
            "(`evals/redteam/results.jsonl` empty).\n"
        )
        return 1

    accepted, failures = evaluate_acceptance(quality + redteam, acc)
    _write_step_summary(_render_summary(quality, redteam, acc, accepted, failures))
    if accepted:
        print("ACCEPT: all acceptance gates passed.")
        return 0
    for f in failures:
        print(f"::error::{f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
