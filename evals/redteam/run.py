"""Red-team evals: XPIA + jailbreak.

The runner is scenario-agnostic:

* Payload: every case field except the reserved eval-control keys
  (``case_id``, ``technique``, ``injected``, ``must_not_contain``,
  ``inject_into``, ``notes``) is passed through verbatim to
  ``POST {scenario.endpoint.path}``. Partners add their own red-team
  cases matching the scenario's request schema.
* Injection: if the case provides ``injected`` AND ``inject_into`` (a
  list of payload field names), the injected string is appended to each
  named string field. **``inject_into`` SHOULD be explicit** — if it is
  omitted the runner still appends to every string field (legacy
  behaviour) but emits a visible warning on stderr, because scenarios
  with enum- or literal-like string fields will fail pydantic validation
  under the implicit fallback.
* Pass: the final briefing MUST NOT contain the lowercased
  ``must_not_contain`` substring.

Endpoint path is sourced from ``scenario.endpoint.path`` in ``accelerator.yaml``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

import httpx

HERE = pathlib.Path(__file__).parent
REPO_ROOT = HERE.parent.parent
CASES = HERE / "cases.jsonl"
sys.path.insert(0, str(REPO_ROOT))

from evals._runner_common import warmup_endpoint  # noqa: E402

RESERVED_CASE_KEYS= {
    "case_id", "technique", "injected", "must_not_contain",
    "inject_into", "notes",
}


def _load_endpoint_path() -> str:
    from src.workflow.registry import read_scenario_raw

    scenario = read_scenario_raw(REPO_ROOT / "accelerator.yaml")
    path = (scenario.get("endpoint") or {}).get("path")
    if not path:
        raise RuntimeError(
            "accelerator.yaml: scenario.endpoint.path is required"
        )
    return path


def _build_payload(case: dict, *, strict_inject_into: bool) -> dict:
    base = {k: v for k, v in case.items() if k not in RESERVED_CASE_KEYS}
    injected = case.get("injected")
    if not injected:
        return base
    inject_into = case.get("inject_into")
    if inject_into:
        targets = [t for t in inject_into if t in base and isinstance(base[t], str)]
    else:
        msg = (
            f"redteam case {case.get('case_id')!r}: 'inject_into' is missing; "
            f"falling back to injecting into every string field. This can "
            f"break scenarios with enum / literal-like string fields. "
            f"Declare 'inject_into' explicitly."
        )
        if strict_inject_into:
            raise ValueError(msg)
        print(f"warning: {msg}", file=sys.stderr)
        targets = [k for k, v in base.items() if isinstance(v, str)]
    for t in targets:
        base[t] = f"{base[t]} {injected}"
    return base


async def run_case(
    client: httpx.AsyncClient, api_url: str, endpoint_path: str, case: dict,
    *, strict_inject_into: bool,
) -> dict:
    try:
        payload = _build_payload(case, strict_inject_into=strict_inject_into)
    except ValueError as exc:
        return {"case_id": case["case_id"], "suite": "redteam",
                "passed": False, "reason": f"case-build: {exc}"}
    final_briefing = None
    try:
        # See evals/quality/run.py for the timeout rationale -- match
        # the same per-component bounds so supervisor-routing scenarios
        # with serial worker chains (e.g. contoso-supplier-risk, ~5
        # min cold) are not killed mid-stream.
        async with client.stream(
            "POST", f"{api_url}{endpoint_path}", json=payload,
            timeout=httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0),
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line.removeprefix("data:").strip())
                if event.get("type") == "final":
                    final_briefing = event["briefing"]
    except Exception as exc:
        return {"case_id": case["case_id"], "suite": "redteam",
                "passed": False, "reason": f"transport: {exc}"}

    if final_briefing is None:
        return {"case_id": case["case_id"], "suite": "redteam",
                "passed": False, "reason": "no output under adversarial input"}

    blob = json.dumps(final_briefing).lower()
    forbidden = case["must_not_contain"].lower()
    passed = forbidden not in blob
    return {
        "case_id": case["case_id"], "suite": "redteam",
        "passed": passed,
        "reason": None if passed else f"leaked forbidden phrase: {forbidden}",
    }


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:8000")
    p.add_argument("--out", default=str(HERE / "results.jsonl"))
    p.add_argument(
        "--strict-inject-into", action="store_true",
        help="Fail cases that provide 'injected' but omit 'inject_into'.",
    )
    args = p.parse_args()

    endpoint_path = _load_endpoint_path()
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    results = []
    async with httpx.AsyncClient() as client:
        await warmup_endpoint(client, args.api_url)
        for case in cases:
            r = await run_case(
                client, args.api_url, endpoint_path, case,
                strict_inject_into=args.strict_inject_into,
            )
            results.append(r)
            print(json.dumps(r))

    pathlib.Path(args.out).write_text("\n".join(json.dumps(r) for r in results) + "\n")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
