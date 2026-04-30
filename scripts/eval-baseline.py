"""Snapshot or check redteam + quality regression baselines.

Two modes:

* ``--snapshot`` — copy the current ``evals/{quality,redteam}/results.jsonl``
  into ``evals/baseline/{suite}-baseline.jsonl``. Run after authoring or
  intentionally accepting a change to the eval set; commit the baseline
  files alongside the change.
* ``--check`` (default) — diff current results vs baseline. Fail (exit 1)
  if any case flipped ``pass -> fail`` between baseline and current.
  Skip silently (exit 0) if no baseline files exist — keeps the template
  default behavior unchanged for partners who haven't authored a baseline yet.

We intentionally only flag pass/fail flips, not score / latency / cost
deltas. Score deltas are noisy with stochastic models; the high-signal
regression is "this case used to pass and now doesn't."

Smoke-mode protection: if the current run has fewer cases than the
baseline (operator ran ``--smoke`` or ``--limit``), the diff is skipped
with a stderr note instead of false-flagging the missing cases as flips.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUITES = ("quality", "redteam")


def _results_path(suite: str) -> pathlib.Path:
    return ROOT / "evals" / suite / "results.jsonl"


def _baseline_path(suite: str) -> pathlib.Path:
    return ROOT / "evals" / "baseline" / f"{suite}-baseline.jsonl"


def _load_pass_map(path: pathlib.Path) -> dict[str, bool]:
    out: dict[str, bool] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out[d["case_id"]] = bool(d.get("passed", False))
    return out


def snapshot() -> int:
    target_dir = ROOT / "evals" / "baseline"
    target_dir.mkdir(parents=True, exist_ok=True)
    wrote = 0
    for suite in SUITES:
        src = _results_path(suite)
        if not src.exists():
            print(f"warning: {src} does not exist; skipping {suite}", file=sys.stderr)
            continue
        shutil.copy2(src, _baseline_path(suite))
        print(f"snapshot: {suite} ({_baseline_path(suite).relative_to(ROOT)})")
        wrote += 1
    if wrote == 0:
        print("error: no result files found to snapshot; run the eval suites first.",
              file=sys.stderr)
        return 1
    return 0


def check() -> int:
    flips: list[tuple[str, str]] = []  # (suite, case_id)
    any_baseline = False
    for suite in SUITES:
        baseline_p = _baseline_path(suite)
        current_p = _results_path(suite)
        if not baseline_p.exists():
            continue
        any_baseline = True
        baseline = _load_pass_map(baseline_p)
        current = _load_pass_map(current_p)
        if not current:
            print(f"warning: {suite} has a baseline but no current results; "
                  f"run the suite first.", file=sys.stderr)
            continue
        if len(current) < len(baseline):
            print(f"note: {suite} current run has {len(current)} cases vs "
                  f"baseline {len(baseline)} — assuming smoke / --limit; "
                  f"skipping regression diff.", file=sys.stderr)
            continue
        for case_id, was_passing in baseline.items():
            if was_passing and not current.get(case_id, False):
                flips.append((suite, case_id))
    if not any_baseline:
        print("no baseline files in evals/baseline/; skipping regression check.")
        return 0
    if flips:
        print("::error::regression detected: cases flipped pass -> fail since baseline:")
        for suite, case_id in flips:
            print(f"  - [{suite}] {case_id}")
        print("\nIf the regression is intentional (e.g. you tightened the "
              "eval), re-snapshot with: python scripts/eval-baseline.py --snapshot",
              file=sys.stderr)
        return 1
    print(f"baseline check: no regressions across {len(SUITES)} suites.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    g = p.add_mutually_exclusive_group()
    g.add_argument("--snapshot", action="store_true",
                   help="Copy current results to evals/baseline/.")
    g.add_argument("--check", action="store_true",
                   help="Diff current vs baseline; fail on pass->fail flips.")
    args = p.parse_args(argv)

    if args.snapshot:
        return snapshot()
    # Default = check mode (CI calls it without flags)
    return check()


if __name__ == "__main__":
    sys.exit(main())
