"""Pre-`azd down` teardown preflight + soft-delete sweep.

Two jobs:
  1. **Pre-teardown checklist.** Prompts the operator through the irreversible
     items they should confirm before destroying the environment (KPI export,
     data export, customer signoff, HITL approver disabled).
  2. **Post-teardown soft-delete sweep.** Cognitive Services accounts and Key
     Vaults go to soft-delete on destroy, NOT hard-delete. They block
     re-creation in the same name+region and quietly accrue retention. This
     command lists those resources for the partner to purge manually.

This script does NOT run `azd down --purge`. The destructive command is
operator-run on a separate line, after the partner reads the checklist.
Same pattern as `/scaffold-from-brief` not running `git commit`.

Usage:
    # Before tearing down: walk the checklist, get explicit ack
    python scripts/teardown-preflight.py --env <env-name>

    # After `azd down --purge`: detect lingering soft-deleted resources
    python scripts/teardown-preflight.py --env <env-name> --post-teardown

Exit codes:
  0 — checklist acknowledged (pre) or no soft-deleted lingering (post)
  1 — operator declined, or soft-deleted resources detected (post)
  2 — script broke (az CLI missing, etc.)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

CHECKLIST = [
    ("KPI export",
     "Have you exported the last 30 days of KPI panels from App Insights "
     "(Workbooks -> ROI KPIs -> Pin to dashboard / Export)?"),
    ("Cost report",
     "Have you captured the final cost report for the engagement "
     "(Cost Management -> Cost analysis -> resource group)?"),
    ("Customer data",
     "Has the customer extracted any data they need from AI Search / "
     "Storage / Foundry threads? Teardown is irreversible."),
    ("HITL approver disabled",
     "If a Logic App / webhook approver was provisioned for this env, "
     "have you disabled or rerouted it so stranded calls fail-closed?"),
    ("Customer signoff",
     "Do you have written customer acknowledgment that the environment "
     "may be destroyed?"),
    ("Final eval baseline",
     "Have you saved a final eval results.jsonl to the engagement archive "
     "for the post-mortem?"),
]


def _az(args: list[str]) -> tuple[int, str, str]:
    az_path = shutil.which("az")
    if not az_path:
        return 127, "", "az CLI not found on PATH"
    try:
        cp = subprocess.run(
            [az_path, *args], check=False, capture_output=True, text=True, timeout=60,
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "az timed out"


def _confirm(prompt: str) -> bool:
    try:
        ans = input(f"  {prompt} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def run_pre_teardown(env: str) -> int:
    print()
    print("-" * 72)
    print(f" Teardown preflight for env={env}")
    print("-" * 72)
    print(" `azd down --purge` is IRREVERSIBLE. Walk this checklist before")
    print(" running the destructive command.")
    print("-" * 72)
    declined: list[str] = []
    for name, question in CHECKLIST:
        print()
        print(f" [{name}]")
        for line in question.split(". "):
            line = line.strip()
            if line:
                print(f"   {line}")
        if not _confirm("Acknowledged"):
            declined.append(name)
    print()
    print("-" * 72)
    if declined:
        print(f" [FAIL] {len(declined)} item(s) not acknowledged: {', '.join(declined)}")
        print(" Address these before running `azd down --purge`.")
        print("-" * 72)
        return 1
    print(" [PASS] Checklist acknowledged.")
    print()
    print(" To complete teardown, run:")
    print(f"   azd down -e {env} --purge --force")
    print()
    print(" Then re-run this script with --post-teardown to sweep for")
    print(" soft-deleted resources that survive `azd down`:")
    print(f"   python scripts/teardown-preflight.py --env {env} --post-teardown")
    print("-" * 72)
    print()
    return 0


def _list_soft_deleted_cog_services() -> list[dict]:
    rc, out, _ = _az(["cognitiveservices", "account", "list-deleted", "-o", "json"])
    if rc != 0:
        return []
    try:
        return json.loads(out) or []
    except json.JSONDecodeError:
        return []


def _list_soft_deleted_keyvaults() -> list[dict]:
    rc, out, _ = _az(["keyvault", "list-deleted", "-o", "json"])
    if rc != 0:
        return []
    try:
        return json.loads(out) or []
    except json.JSONDecodeError:
        return []


def run_post_teardown(env: str) -> int:
    print()
    print("-" * 72)
    print(f" Soft-delete sweep for env={env}")
    print("-" * 72)
    print(" `azd down --purge` does NOT hard-delete every resource type.")
    print(" Cognitive Services accounts and Key Vaults go to soft-delete and")
    print(" block re-creation in the same name+region. This sweep detects")
    print(" them so you can purge manually.")
    print("-" * 72)

    cog = _list_soft_deleted_cog_services()
    kv = _list_soft_deleted_keyvaults()

    # Filter heuristically by env name in resource name; soft-deleted records
    # don't carry tags so name-substring is the best signal.
    cog_match = [a for a in cog if env.lower() in (a.get("name") or "").lower()]
    kv_match = [a for a in kv if env.lower() in (a.get("name") or "").lower()]

    if not cog_match and not kv_match:
        print(" [PASS] No soft-deleted Cognitive Services accounts or Key Vaults")
        print(f"    matching env name '{env}'.")
        print()
        print(f" Other matches (different env names): {len(cog)} cog svc, {len(kv)} key vault.")
        print(" Those are unrelated to this teardown.")
        print("-" * 72)
        print()
        return 0

    print(f" [WARN] Found {len(cog_match)} Cognitive Services + {len(kv_match)} Key Vault")
    print("    soft-deleted resources matching this env name.")
    print()

    if cog_match:
        print(" Cognitive Services accounts (purge to free name+region):")
        for a in cog_match:
            name = a.get("name", "?")
            location = a.get("location") or (a.get("properties") or {}).get("location", "?")
            print(f"   - {name}  (region: {location})")
            print(f"     az cognitiveservices account purge -n {name} -l {location} -g <original-rg>")
        print()

    if kv_match:
        print(" Key Vaults (purge to free name+region):")
        for v in kv_match:
            name = v.get("name", "?")
            location = (v.get("properties") or {}).get("location", "?")
            print(f"   - {name}  (region: {location})")
            print(f"     az keyvault purge -n {name} -l {location}")
        print()

    print(" These commands are DESTRUCTIVE and CANNOT be undone. Confirm with")
    print(" the customer (and any partner DR / retention policy) BEFORE running")
    print(" them. The script does not auto-purge.")
    print("-" * 72)
    print()
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--env", required=True,
                   help="azd environment name being torn down (matches `deploy/environments.yaml`).")
    p.add_argument("--post-teardown", action="store_true",
                   help="Run the soft-delete sweep instead of the pre-teardown checklist.")
    args = p.parse_args()

    if not shutil.which("az"):
        print("teardown-preflight: az CLI not found on PATH.", file=sys.stderr)
        return 2

    return run_post_teardown(args.env) if args.post_teardown else run_pre_teardown(args.env)


if __name__ == "__main__":
    sys.exit(main())
