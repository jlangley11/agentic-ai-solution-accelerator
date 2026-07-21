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
    python scripts/teardown-preflight.py --env <env-name> \
      --deployment-target hosted-preview

    # After `azd down --purge`: detect lingering soft-deleted resources
    python scripts/teardown-preflight.py --env <env-name> --post-teardown
    python scripts/teardown-preflight.py --env <env-name> --post-teardown \
      --deployment-target hosted-preview \
      --cognitive-account-name <exact-account-name>

Exit codes:
  0 — checklist acknowledged (pre) or no soft-deleted lingering (post)
  1 — operator declined, or soft-deleted resources detected (post)
  2 — script broke or a hosted account name could not be resolved safely
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACCOUNT_NAME_KEYS = (
    "AZURE_AI_FOUNDRY_ACCOUNT_NAME",
    "AZURE_AI_ACCOUNT_NAME",
)
_ENV_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

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


def teardown_commands(env: str, deployment_target: str = "selfhost") -> list[str]:
    if deployment_target == "hosted-preview":
        return [
            "cd deploy/hosted-preview",
            f"azd down -e {env} --purge --force",
        ]
    return [f"azd down -e {env} --purge --force"]


def azd_environment_file(
    env: str,
    deployment_target: str = "selfhost",
    *,
    root: pathlib.Path = ROOT,
) -> pathlib.Path:
    workspace = (
        root / "deploy" / "hosted-preview"
        if deployment_target == "hosted-preview"
        else root
    )
    return workspace / ".azure" / env / ".env"


def _read_account_name(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_ASSIGNMENT_RE.match(line)
        if not match or match.group(1) not in ACCOUNT_NAME_KEYS:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[match.group(1)] = value
    return next((values[key] for key in ACCOUNT_NAME_KEYS if values.get(key)), None)


def resolve_cognitive_account_name(
    env: str,
    deployment_target: str = "selfhost",
    *,
    override: str | None = None,
    root: pathlib.Path = ROOT,
) -> str | None:
    if override and override.strip():
        return override.strip()
    return _read_account_name(azd_environment_file(env, deployment_target, root=root))


def run_pre_teardown(env: str, deployment_target: str = "selfhost") -> int:
    print()
    print("-" * 72)
    print(f" Teardown preflight for env={env} target={deployment_target}")
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
    for command in teardown_commands(env, deployment_target):
        print(f"   {command}")
    print()
    print(" Then re-run this script with --post-teardown to sweep for")
    print(" soft-deleted resources that survive `azd down`:")
    target_arg = (
        " --deployment-target hosted-preview"
        if deployment_target == "hosted-preview"
        else ""
    )
    print(
        f"   python scripts/teardown-preflight.py --env {env}"
        f" --post-teardown{target_arg}"
    )
    print("-" * 72)
    print()
    return 0


def _list_soft_deleted_cog_services() -> list[dict]:
    rc, out, err = _az(["cognitiveservices", "account", "list-deleted", "-o", "json"])
    if rc != 0:
        raise RuntimeError(
            "could not list soft-deleted Cognitive Services accounts: "
            + (err.strip() or f"az exited {rc}")
        )
    try:
        return json.loads(out) or []
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "soft-deleted Cognitive Services query returned invalid JSON"
        ) from exc


def _list_soft_deleted_keyvaults() -> list[dict]:
    rc, out, err = _az(["keyvault", "list-deleted", "-o", "json"])
    if rc != 0:
        raise RuntimeError(
            "could not list soft-deleted Key Vaults: "
            + (err.strip() or f"az exited {rc}")
        )
    try:
        return json.loads(out) or []
    except json.JSONDecodeError as exc:
        raise RuntimeError("soft-deleted Key Vault query returned invalid JSON") from exc


def run_post_teardown(
    env: str,
    deployment_target: str = "selfhost",
    cognitive_account_name: str | None = None,
    *,
    root: pathlib.Path = ROOT,
) -> int:
    print()
    print("-" * 72)
    print(f" Soft-delete sweep for env={env} target={deployment_target}")
    print("-" * 72)
    print(" `azd down --purge` does NOT hard-delete every resource type.")
    if deployment_target == "hosted-preview":
        print(" Hosted preview can leave Cognitive Services accounts soft-deleted.")
        print(" It does not provision a Key Vault; the Key Vault query remains as")
        print(" a defensive sweep for same-named resources created outside the workspace.")
    else:
        print(" Cognitive Services accounts and Key Vaults go to soft-delete and")
        print(" block re-creation in the same name+region. This sweep detects")
        print(" them so you can purge manually.")
    print("-" * 72)

    expected_account = resolve_cognitive_account_name(
        env,
        deployment_target,
        override=cognitive_account_name,
        root=root,
    )
    env_file = azd_environment_file(env, deployment_target, root=root)
    if deployment_target == "hosted-preview" and not expected_account:
        print(" [FAIL] Cannot resolve the hosted Cognitive Services account name.")
        print(f"    Checked: {env_file}")
        print(
            "    Restore the selected azd environment file or pass "
            "`--cognitive-account-name <account-name>`."
        )
        print("    Refusing to report PASS from env-name substring matching alone.")
        print("-" * 72)
        print()
        return 2
    if expected_account:
        print(f" Expected Cognitive Services account: {expected_account}")
    else:
        print(" Expected account name unavailable; using legacy env-name fallback.")
    print("-" * 72)

    try:
        cog = _list_soft_deleted_cog_services()
        kv = _list_soft_deleted_keyvaults()
    except RuntimeError as exc:
        print(f" [FAIL] {exc}")
        print("    Refusing to report a clean teardown without authoritative Azure results.")
        print("-" * 72)
        print()
        return 2

    expected_lower = (expected_account or "").lower()
    env_lower = env.lower()
    if expected_lower:
        cog_match = [
            account
            for account in cog
            if (account.get("name") or "").lower() == expected_lower
        ]
    else:
        cog_match = [
            account
            for account in cog
            if env_lower in (account.get("name") or "").lower()
        ]
    kv_match = [a for a in kv if env.lower() in (a.get("name") or "").lower()]

    if not cog_match and not kv_match:
        print(" [PASS] No soft-deleted Cognitive Services accounts or Key Vaults")
        if expected_account:
            print(f"    matching exact account '{expected_account}'.")
        else:
            print(f"    matching legacy env name '{env}'.")
        print()
        print(f" Other matches (different env names): {len(cog)} cog svc, {len(kv)} key vault.")
        print(" Those are unrelated to this teardown.")
        print("-" * 72)
        print()
        return 0

    print(f" [WARN] Found {len(cog_match)} Cognitive Services + {len(kv_match)} Key Vault")
    print("    soft-deleted resources matching the expected account or legacy env name.")
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
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    p.add_argument("--env", required=True,
                   help="azd environment name being torn down (matches `deploy/environments.yaml`).")
    p.add_argument("--post-teardown", action="store_true",
                   help="Run the soft-delete sweep instead of the pre-teardown checklist.")
    p.add_argument(
        "--deployment-target",
        choices=("selfhost", "hosted-preview"),
        default="selfhost",
        help="Deployment workspace being torn down (default: selfhost).",
    )
    p.add_argument(
        "--cognitive-account-name",
        default=None,
        help=(
            "Expected Cognitive Services account name. Overrides values from the "
            "selected azd environment file."
        ),
    )
    args = p.parse_args()

    if not shutil.which("az"):
        print("teardown-preflight: az CLI not found on PATH.", file=sys.stderr)
        return 2

    if args.post_teardown:
        return run_post_teardown(
            args.env,
            args.deployment_target,
            args.cognitive_account_name,
        )
    return run_pre_teardown(args.env, args.deployment_target)


if __name__ == "__main__":
    sys.exit(main())
