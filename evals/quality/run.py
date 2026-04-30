"""Run quality evals against the local API.

Usage:
    python evals/quality/run.py --api-url http://localhost:8000
    python evals/quality/run.py --api-url $API_URL --out results.jsonl
    python evals/quality/run.py --model gpt-5-mini  # pricing table

    # 30-second post-deploy smoke (after `azd up` + `/healthz` green,
    # before authoring the full customer eval set):
    python evals/quality/run.py --api-url $API_URL --smoke

Each case is a JSON line. The runner is scenario-agnostic:

* Payload: every case field except the reserved eval-control keys
  (``case_id``, ``expected``, ``technique``, ``notes``) is passed through
  verbatim to ``POST {scenario.endpoint.path}``. The active scenario's
  pydantic ``request_schema`` is therefore the source of truth; the dataset
  must match it.
* Checks: declared per-case under ``expected``:
    - ``must_mention``: list of substrings that MUST appear in the
      lowercased JSON dump of the final briefing.
    - ``must_cite``: if true, the briefing must contain a non-empty
      ``"citations"`` list somewhere in its tree.
    - ``thresholds``: ``{"<dotted.path>": {"min": N, "max": M}}`` comparing
      numeric values in the briefing.
    - Flagship back-compat: ``icp_fit_min`` (int, 0-100) is treated as
      ``thresholds: {"icp_fit.fit_score": {"min": N}}``.

Cost accounting (live gate for ``accelerator.yaml.acceptance.cost_per_call_usd``):
    The workflow emits ``briefing.usage`` with token counters when the
    Agent Framework result exposes a ``usage`` object. The runner turns
    that into ``cost_usd`` using ``MODEL_PRICING_USD_PER_MTOK[model]``.
    Partners override via ``--model`` or ``--cost-override``. When tokens
    are absent (local stub / SDK disabled path), the runner falls back to
    a deterministic latency-based estimate so the acceptance gate is
    ALWAYS live -- ``evaluate_acceptance`` fails loudly if every result
    lacks ``cost_usd`` while ``cost_per_call_usd`` is declared.

Results land in ``results.jsonl`` for CI's ``accept`` gate. The endpoint
path comes from ``scenario.endpoint.path`` in ``accelerator.yaml``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import re
import sys
import time

import httpx

HERE = pathlib.Path(__file__).parent
REPO_ROOT = HERE.parent.parent
CASES = HERE / "golden_cases.jsonl"
sys.path.insert(0, str(REPO_ROOT))

from evals._runner_common import warmup_endpoint  # noqa: E402

RESERVED_CASE_KEYS= {"case_id", "expected", "technique", "notes", "exercises"}
_CITATIONS_RE = re.compile(r'"citations"\s*:\s*\[\s*[^\]\s]')

# Public GA list prices (USD per 1M tokens). Keep conservative / partner-overridable.
# Partners on custom models override via --model + a pricing entry, or pass
# --cost-override to stamp a fixed cost_per_call during CI testing.
MODEL_PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "gpt-5-mini":   {"prompt": 0.25, "completion": 2.00},
    "gpt-5":        {"prompt": 1.25, "completion": 10.00},
    "gpt-5-nano":   {"prompt": 0.05, "completion": 0.40},
    "gpt-4o-mini":  {"prompt": 0.15, "completion": 0.60},
    "gpt-4o":       {"prompt": 2.50, "completion": 10.00},
    "gpt-4.1":      {"prompt": 2.00, "completion": 8.00},
    "gpt-4.1-mini": {"prompt": 0.40, "completion": 1.60},
    "o4-mini":      {"prompt": 1.10, "completion": 4.40},
}
# Fallback when token usage is unavailable (stub path / pre-GA SDK). A
# linear latency estimate keeps the acceptance gate live with a
# defensible upper bound. Partners tune via --cost-per-second.
_DEFAULT_COST_PER_SECOND_USD = 0.003


def _load_endpoint_path() -> str:
    from src.workflow.registry import read_scenario_raw

    scenario = read_scenario_raw(REPO_ROOT / "accelerator.yaml")
    path = (scenario.get("endpoint") or {}).get("path")
    if not path:
        raise RuntimeError(
            "accelerator.yaml: scenario.endpoint.path is required"
        )
    return path


def _get_dotted(obj: dict, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def _normalize_expected(expected: dict) -> dict:
    """Back-compat: fold `icp_fit_min` into `thresholds`."""
    exp = dict(expected or {})
    thresholds = dict(exp.get("thresholds") or {})
    if "icp_fit_min" in exp and "icp_fit.fit_score" not in thresholds:
        thresholds["icp_fit.fit_score"] = {"min": exp["icp_fit_min"]}
    exp["thresholds"] = thresholds
    return exp


def _estimate_cost_usd(
    briefing: dict,
    *,
    model: str,
    cost_override: float | None,
    cost_per_second: float,
    latency_ms: int,
) -> float:
    """Best-effort cost estimate. Always returns a finite float so the
    acceptance gate is live even when the workflow does not surface token
    usage (stub path / pre-GA SDK).
    """
    if cost_override is not None:
        return float(cost_override)
    usage = (briefing or {}).get("usage") or {}
    if isinstance(usage, dict) and usage:
        pricing = MODEL_PRICING_USD_PER_MTOK.get(model)
        if pricing:
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            if prompt_tokens or completion_tokens:
                return round(
                    (prompt_tokens / 1_000_000) * pricing["prompt"]
                    + (completion_tokens / 1_000_000) * pricing["completion"],
                    6,
                )
    # Fallback: deterministic latency-based estimate.
    return round((latency_ms / 1000.0) * cost_per_second, 6)


async def run_case(
    client: httpx.AsyncClient,
    api_url: str,
    endpoint_path: str,
    case: dict,
    *,
    model: str,
    cost_override: float | None,
    cost_per_second: float,
) -> dict:
    started = time.time()
    payload = {k: v for k, v in case.items() if k not in RESERVED_CASE_KEYS}
    final_briefing = None
    try:
        async with client.stream(
            "POST", f"{api_url}{endpoint_path}", json=payload, timeout=120.0,
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line.removeprefix("data:").strip())
                if event.get("type") == "final":
                    final_briefing = event["briefing"]
    except Exception as exc:
        return {"case_id": case["case_id"], "suite": "quality",
                "passed": False, "reason": f"transport: {exc}"}

    if final_briefing is None:
        return {"case_id": case["case_id"], "suite": "quality",
                "passed": False, "reason": "no final briefing"}

    expected = _normalize_expected(case.get("expected", {}))
    blob_raw = json.dumps(final_briefing)
    blob = blob_raw.lower()
    citations_ok = bool(_CITATIONS_RE.search(blob_raw))

    score = 1.0
    reasons: list[str] = []

    for dotted, bound in (expected.get("thresholds") or {}).items():
        val = _get_dotted(final_briefing, dotted)
        if not isinstance(val, (int, float)):
            score -= 0.4
            reasons.append(f"{dotted}: not numeric ({val!r})")
            continue
        if "min" in bound and val < bound["min"]:
            score -= 0.4
            reasons.append(f"{dotted} {val} < {bound['min']}")
        if "max" in bound and val > bound["max"]:
            score -= 0.4
            reasons.append(f"{dotted} {val} > {bound['max']}")

    for phrase in expected.get("must_mention", []):
        if phrase.lower() not in blob:
            score -= 0.2
            reasons.append(f"missing mention: {phrase}")

    groundedness = 1.0 if citations_ok else 0.0
    if expected.get("must_cite") and not citations_ok:
        reasons.append("no citations")

    latency_ms = int((time.time() - started) * 1000)
    cost_usd = _estimate_cost_usd(
        final_briefing,
        model=model,
        cost_override=cost_override,
        cost_per_second=cost_per_second,
        latency_ms=latency_ms,
    )
    passed = score >= 0.6 and (groundedness >= 0.8 or not expected.get("must_cite"))

    return {
        "case_id": case["case_id"], "suite": "quality",
        "passed": passed, "score": round(max(score, 0.0), 3),
        "groundedness": groundedness, "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "reason": "; ".join(reasons) or None,
    }


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:8000")
    p.add_argument("--out", default=str(HERE / "results.jsonl"))
    p.add_argument(
        "--model", default="gpt-5-mini",
        help="Pricing table key (see MODEL_PRICING_USD_PER_MTOK).",
    )
    p.add_argument(
        "--cost-override", type=float, default=None,
        help="Stamp a fixed cost_usd per case (CI determinism).",
    )
    p.add_argument(
        "--cost-per-second", type=float,
        default=_DEFAULT_COST_PER_SECOND_USD,
        help="Latency-based fallback rate when token usage is unavailable.",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Run only the first N cases (smoke testing / debugging). "
             "Default: run all cases.",
    )
    p.add_argument(
        "--smoke", action="store_true",
        help="30-second smoke test mode for the partner-facing post-deploy "
             "confidence check. Implies --limit 2 (unless --limit is set "
             "explicitly), suppresses per-case JSONL on stdout, writes "
             "results to smoke-results.jsonl, and prints a friendly "
             "summary table. Use after `azd up` succeeds and `/healthz` "
             "is green, BEFORE authoring the full customer eval set.",
    )
    args = p.parse_args()

    if args.smoke:
        if args.limit is None:
            args.limit = 2
        if args.out == str(HERE / "results.jsonl"):
            args.out = str(HERE / "smoke-results.jsonl")

    endpoint_path = _load_endpoint_path()
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    if args.limit is not None:
        cases = cases[: args.limit]
    async with httpx.AsyncClient() as client:
        await warmup_endpoint(client, args.api_url)
        results = []
        for case in cases:
            r = await run_case(
                client, args.api_url, endpoint_path, case,
                model=args.model,
                cost_override=args.cost_override,
                cost_per_second=args.cost_per_second,
            )
            results.append(r)
            if not args.smoke:
                print(json.dumps(r))

    pathlib.Path(args.out).write_text("\n".join(json.dumps(r) for r in results) + "\n")
    failed = [r for r in results if not r["passed"]]
    if args.smoke:
        _print_smoke_summary(results, args.out)
    return 1 if failed else 0


def _print_smoke_summary(results: list[dict], out_path: str) -> None:
    """Partner-facing 30-second post-deploy confidence summary.

    Stdout-only. Writes the same per-case JSONL to ``out_path`` for
    inspection / attachment to a triage thread when something fails.
    """
    total = len(results)
    if total == 0:
        print("smoke: no cases ran (cases file empty?)", file=sys.stderr)
        return
    passed = sum(1 for r in results if r.get("passed"))
    avg_latency = sum(int(r.get("latency_ms") or 0) for r in results) // total
    citations_ok = sum(1 for r in results if (r.get("groundedness") or 0) >= 0.8)
    verdict = "✅ READY" if passed == total else "❌ NEEDS ATTENTION"
    print()
    print("─" * 60)
    print(f" Smoke test verdict: {verdict}")
    print("─" * 60)
    print(f"  Cases run            : {total}")
    print(f"  Passed               : {passed}/{total}")
    print(f"  Citations present    : {citations_ok}/{total}")
    print(f"  Avg latency          : {avg_latency} ms")
    print(f"  Per-case JSONL       : {out_path}")
    print("─" * 60)
    if passed < total:
        print(" Failed cases:")
        for r in results:
            if not r.get("passed"):
                print(f"   - {r['case_id']}: {r.get('reason') or 'no reason recorded'}")
        print("─" * 60)
        print(" Next step: open the JSONL above, or check App Insights")
        print(" `traces` for the matching correlation IDs. Common causes:")
        print("   - RBAC propagation lag (wait 3 min, retry)")
        print("   - AI Search index not seeded (restart Container App revision)")
        print("   - Foundry agent not yet bootstrapped (check /healthz)")
    else:
        print(" The agent answered the smoke cases correctly with citations.")
        print(" You're ready to author the full customer eval set in")
        print(" evals/quality/golden_cases.jsonl and run the full suite:")
        print(" `python evals/quality/run.py --api-url <url>`")
    print()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
