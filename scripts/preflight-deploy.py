"""Pre-`azd up` deploy preflight.

Runs deterministic ``az`` checks against the partner's currently-logged-in
Azure context to surface the documented `azd up` failure modes BEFORE the
12-minute provision burns. Wires into the deliver-step-7 walkthrough as
"Run this before ``azd up``."

Scope:
  - ``az account show`` parity (logged in, expected tenant if --tenant given)
  - Required-RP registration check
  - Default-model availability in the chosen region
  - Quota probe for the default model (best-effort)
  - Region capability for AI Foundry projects (best-effort)

Non-goals:
  - Does NOT run ``azd up``. Read-only.
  - Does NOT validate every Bicep input. Lint already does that.
  - Does NOT block on best-effort checks — those WARN, do not FAIL. The
    partner's trust is more valuable than catching every edge case.

Usage:
    python scripts/preflight-deploy.py --region eastus2
    python scripts/preflight-deploy.py --region westeurope --tenant <guid>
    python scripts/preflight-deploy.py --region eastus2 --subscription <guid>

Exit codes:
  0 — all hard checks pass (warnings allowed)
  1 — at least one hard check failed; ``azd up`` will likely fail too
  2 — preflight itself broke (az CLI missing, accelerator.yaml malformed)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
from dataclasses import dataclass

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Resource providers that infra/main.bicep depends on. Missing registrations
# manifest as `azd up` failures partway through provision.
REQUIRED_RPS = [
    "Microsoft.CognitiveServices",
    "Microsoft.Search",
    "Microsoft.App",
    "Microsoft.OperationalInsights",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.ManagedIdentity",
]

# AI Foundry project GA regions as of writing. Best-effort: the list grows
# over time, so a region that's NOT here gets a WARN, not a FAIL — the
# partner can override and proceed if they know better.
FOUNDRY_GA_REGIONS = {
    "eastus", "eastus2", "westus", "westus2", "westus3",
    "northcentralus", "southcentralus",
    "westeurope", "northeurope", "uksouth",
    "australiaeast", "japaneast", "swedencentral",
}


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    fix: str | None = None


def _az(args: list[str], *, capture: bool = True) -> tuple[int, str, str]:
    """Run an ``az`` command and return (rc, stdout, stderr).

    Never raises. ``az`` not installed → rc=127 with a synthetic stderr.

    On Windows ``az`` is a ``.cmd`` shim, so we resolve the full path via
    ``shutil.which`` rather than relying on PATH lookup inside CreateProcess.
    """
    az_path = shutil.which("az")
    if not az_path:
        return 127, "", "az CLI not found on PATH"
    try:
        cp = subprocess.run(
            [az_path, *args],
            check=False,
            capture_output=capture,
            text=True,
            timeout=60,
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"az {' '.join(args)} timed out after 60s"


def _load_default_model() -> dict | None:
    manifest_path = ROOT / "accelerator.yaml"
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"preflight: cannot parse accelerator.yaml: {exc}", file=sys.stderr)
        sys.exit(2)
    models = manifest.get("models") or []
    for m in models:
        if m.get("default"):
            return m
    return models[0] if models else None


# -----------------------------------------------------------------------------
# Individual checks (each returns one CheckResult)
# -----------------------------------------------------------------------------

def check_az_login(expected_tenant: str | None, expected_subscription: str | None) -> CheckResult:
    rc, out, err = _az(["account", "show", "-o", "json"])
    if rc == 127:
        return CheckResult(
            "az CLI installed", "fail", "az not on PATH",
            fix="Install Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli",
        )
    if rc != 0:
        return CheckResult(
            "az logged in", "fail", "az account show failed",
            fix=f"Run `az login --tenant <customer-tenant>`. Error: {err.strip() or 'unknown'}",
        )
    try:
        acct = json.loads(out)
    except json.JSONDecodeError:
        return CheckResult("az logged in", "fail", "az returned non-JSON", fix="Re-run `az login`.")
    sub_id = acct.get("id", "?")
    sub_name = acct.get("name", "?")
    tenant_id = acct.get("tenantId", "?")
    msg = f"sub={sub_name} ({sub_id[:8]}...), tenant={tenant_id[:8]}..."
    if expected_tenant and tenant_id != expected_tenant:
        return CheckResult(
            "az tenant matches", "fail",
            f"logged into tenant {tenant_id} but expected {expected_tenant}",
            fix=f"Run `az login --tenant {expected_tenant}` then re-run preflight.",
        )
    if expected_subscription and sub_id != expected_subscription:
        return CheckResult(
            "az subscription matches", "fail",
            f"current sub is {sub_id} but expected {expected_subscription}",
            fix=f"Run `az account set --subscription {expected_subscription}`.",
        )
    return CheckResult("az logged in", "pass", msg)


def check_resource_providers() -> CheckResult:
    not_registered: list[str] = []
    for rp in REQUIRED_RPS:
        rc, out, _ = _az([
            "provider", "show", "-n", rp, "--query", "registrationState", "-o", "tsv",
        ])
        if rc != 0:
            not_registered.append(f"{rp} (lookup failed)")
            continue
        state = out.strip()
        if state.lower() != "registered":
            not_registered.append(f"{rp} ({state or 'unknown'})")
    if not_registered:
        cmds = "\n  ".join(
            f"az provider register -n {n.split(' ')[0]}" for n in not_registered
        )
        return CheckResult(
            "Resource providers registered", "fail",
            f"{len(not_registered)} RP(s) not registered: {', '.join(not_registered)}",
            fix=f"Run:\n  {cmds}\nWait 1-2 min for propagation.",
        )
    return CheckResult(
        "Resource providers registered", "pass",
        f"{len(REQUIRED_RPS)}/{len(REQUIRED_RPS)} registered",
    )


def check_region_exists(region: str) -> CheckResult:
    rc, out, _ = _az(["account", "list-locations", "--query", "[].name", "-o", "tsv"])
    if rc != 0:
        return CheckResult(
            "Region is valid", "warn",
            "could not list Azure regions (skipping)",
        )
    valid = {line.strip().lower() for line in out.splitlines() if line.strip()}
    if region.lower() not in valid:
        return CheckResult(
            "Region is valid", "fail",
            f"'{region}' is not a known Azure region for this subscription",
            fix="Check `az account list-locations -o table` for valid names.",
        )
    return CheckResult("Region is valid", "pass", region)


def check_foundry_region(region: str) -> CheckResult:
    if region.lower() in FOUNDRY_GA_REGIONS:
        return CheckResult("Foundry projects available in region", "pass", region)
    return CheckResult(
        "Foundry projects available in region", "warn",
        f"'{region}' is not in the documented Foundry GA region list",
        fix=("If `azd up` fails on Microsoft.CognitiveServices/accounts/projects, "
             "re-run with a region from FOUNDRY_GA_REGIONS in this script."),
    )


def check_model_available(region: str, model: dict) -> CheckResult:
    """Verify the default model+version is offered in the chosen region.

    Best-effort: ``az cognitiveservices model list`` requires
    Microsoft.CognitiveServices/locations/models/read on the subscription;
    if denied we WARN rather than FAIL.
    """
    model_name = model.get("model")
    version = str(model.get("version") or "")
    if not model_name:
        return CheckResult("Default model available in region", "warn",
                           "accelerator.yaml has no default model name")
    rc, out, err = _az([
        "cognitiveservices", "model", "list",
        "-l", region, "-o", "json",
    ])
    if rc != 0:
        return CheckResult(
            "Default model available in region", "warn",
            f"could not list models in {region}: {err.strip()[:80] or 'access denied'}",
            fix=("If this WARN turns into a hard failure during `azd up`, the most "
                 "common cause is the model not being offered in this region. "
                 "Check https://learn.microsoft.com/azure/ai-services/openai/concepts/models"),
        )
    try:
        models = json.loads(out) or []
    except json.JSONDecodeError:
        return CheckResult("Default model available in region", "warn", "model list returned non-JSON")
    matches = [
        m for m in models
        if (m.get("model") or {}).get("name", "").lower() == model_name.lower()
    ]
    if not matches:
        return CheckResult(
            "Default model available in region", "fail",
            f"model '{model_name}' not offered in {region}",
            fix=("Pick a region that offers the model, or change "
                 "`accelerator.yaml -> models[].model` to a model that's "
                 f"available in {region}."),
        )
    if version:
        version_match = any(
            (m.get("model") or {}).get("version", "") == version for m in matches
        )
        if not version_match:
            offered = sorted({(m.get("model") or {}).get("version", "?") for m in matches})
            return CheckResult(
                "Default model available in region", "warn",
                f"model '{model_name}' is offered in {region} but version "
                f"'{version}' is not (offered: {', '.join(offered)})",
                fix=("Update `accelerator.yaml -> models[].version` to one of "
                     "the offered versions, or accept the latest by removing "
                     "the `version:` field."),
            )
    return CheckResult(
        "Default model available in region", "pass",
        f"{model_name}@{version or 'latest'}",
    )


def check_model_quota(region: str, model: dict) -> CheckResult:
    """Best-effort TPM quota probe.

    `az cognitiveservices usage list` returns rows ONLY for resource types
    that have at least one account in the region. On a fresh subscription
    the response is empty → WARN ("could not verify"), not FAIL.
    """
    capacity = int(model.get("capacity") or 0)
    if not capacity:
        return CheckResult("Default model has TPM headroom", "warn",
                           "accelerator.yaml has no capacity declared")
    rc, out, _ = _az([
        "cognitiveservices", "usage", "list",
        "-l", region, "-o", "json",
    ])
    if rc != 0:
        return CheckResult(
            "Default model has TPM headroom", "warn",
            "quota API access denied; cannot pre-verify",
            fix=("If `azd up` fails with `InsufficientQuota` mid-provision, "
                 "request quota in Azure portal -> Quotas -> Cognitive Services."),
        )
    try:
        usages = json.loads(out) or []
    except json.JSONDecodeError:
        usages = []
    if not usages:
        return CheckResult(
            "Default model has TPM headroom", "warn",
            f"no quota data for {region} (likely a fresh subscription)",
            fix="If `azd up` fails on `InsufficientQuota`, request via the portal.",
        )
    return CheckResult(
        "Default model has TPM headroom", "pass",
        f"quota probe returned {len(usages)} rows (manual review recommended)",
    )


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------

def _print_report(results: list[CheckResult]) -> int:
    icon = {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}
    bar = "-" * 72
    print()
    print(bar)
    print(" Deploy preflight - read-only checks against your current az context")
    print(bar)
    for r in results:
        print(f"  {icon[r.status]} {r.name:<42} {r.message}")
    fails = [r for r in results if r.status == "fail"]
    warns = [r for r in results if r.status == "warn"]
    print(bar)
    if fails:
        print(f" Result: [FAIL] {len(fails)} hard failure(s); `azd up` will likely fail.")
    elif warns:
        print(f" Result: [WARN] {len(warns)} warning(s); `azd up` may proceed but watch for these.")
    else:
        print(" Result: [PASS] all checks passed; `azd up` is safe to run.")
    print(bar)
    if fails or warns:
        print(" Remediation:")
        for r in (*fails, *warns):
            if r.fix:
                print(f"   * {r.name}:")
                for line in r.fix.splitlines():
                    print(f"       {line}")
        print(bar)
    print()
    return 1 if fails else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--region", required=True,
                   help="Target Azure region for `azd up` (e.g. eastus2).")
    p.add_argument("--tenant", default=None,
                   help="Expected tenant GUID; preflight fails if mismatched.")
    p.add_argument("--subscription", default=None,
                   help="Expected subscription GUID; preflight fails if mismatched.")
    args = p.parse_args()

    default_model = _load_default_model()
    if default_model is None:
        print("preflight: accelerator.yaml has no `models[]` block", file=sys.stderr)
        return 2

    results: list[CheckResult] = [
        check_az_login(args.tenant, args.subscription),
    ]
    # If the login check fails, downstream az calls will all fail too; bail early.
    if results[0].status == "fail":
        return _print_report(results)

    results.extend([
        check_resource_providers(),
        check_region_exists(args.region),
        check_foundry_region(args.region),
        check_model_available(args.region, default_model),
        check_model_quota(args.region, default_model),
    ])
    return _print_report(results)


if __name__ == "__main__":
    sys.exit(main())
