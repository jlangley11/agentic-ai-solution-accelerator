"""Tier 3 (alz-integrated) ALZ validation preflight.

Runs deterministic checks BEFORE ``azd up`` when
``accelerator.yaml -> landing_zone.mode: alz-integrated``. Catches the
documented failure modes (forgotten placeholders, unreachable hub
resource IDs, undersized workload subnet) that otherwise surface 8
minutes into a Bicep deploy.

Wires into [Reference -> Security review checklist] and
[infra/alz-overlay/README.md].

Scope:
  - Detect `CHANGEME-*` placeholders left in
    `infra/alz-overlay/main.parameters.json`.
  - Validate each hub resource ID via `az resource show --ids` (vNet,
    Log Analytics workspace, 5 private DNS zones).
  - Verify the workload subnet prefix is /27 or larger (PE + Container
    Apps pressure).
  - Best-effort warn when `createDnsZoneLinks: true` but the deploying
    principal lacks `Private DNS Zone Contributor` on the zones.

Non-goals:
  - Does NOT run ``azd up``. Read-only.
  - Does NOT validate every Bicep input — `accelerator-lint.py` and
    `az bicep build` already cover that.
  - Does NOT fail on RBAC gaps (warns only) — JIT-elevated principals
    legitimately fail the static check.

Usage:
    python scripts/validate-alz.py
    python scripts/validate-alz.py --params custom-params.json

Exit codes:
  0 - all hard checks pass (warnings allowed)
  1 - at least one hard check failed; `azd up` will likely fail too
  2 - validator itself broke (az CLI missing, params file unreadable)
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

DEFAULT_PARAMS = ROOT / "infra" / "alz-overlay" / "main.parameters.json"
ACCELERATOR_YAML = ROOT / "accelerator.yaml"

# Largest subnet (smallest prefix int) we tolerate. Container Apps' env
# infra plus PE NICs need real headroom; /28 has bitten partners before.
MIN_SUBNET_PREFIX = 27


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    fix: str | None = None


def _az(args: list[str]) -> tuple[int, str, str]:
    az_path = shutil.which("az")
    if not az_path:
        return 127, "", "az CLI not found on PATH"
    try:
        cp = subprocess.run(
            [az_path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"az {' '.join(args)} timed out after 60s"


def _load_params(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"validate-alz: cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def _required_mode_is_alz() -> bool:
    """Return True iff `accelerator.yaml -> landing_zone.mode: alz-integrated`."""
    if not ACCELERATOR_YAML.exists():
        return False
    try:
        manifest = yaml.safe_load(ACCELERATOR_YAML.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    return (manifest.get("landing_zone") or {}).get("mode") == "alz-integrated"


def _walk_strings(node):
    """Yield every string value in a nested JSON structure."""
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)
    elif isinstance(node, str):
        yield node


# -----------------------------------------------------------------------------
# Individual checks
# -----------------------------------------------------------------------------

def check_no_placeholders(params: dict) -> CheckResult:
    """Hard-fail if any `CHANGEME-*` placeholder is still present."""
    offenders = sorted({s for s in _walk_strings(params) if "CHANGEME" in s})
    if not offenders:
        return CheckResult(
            "Placeholders filled in", "pass",
            "no CHANGEME-* values remain",
        )
    return CheckResult(
        "Placeholders filled in", "fail",
        f"{len(offenders)} placeholder value(s) remain",
        fix=(
            "Replace the following in infra/alz-overlay/main.parameters.json:\n"
            + "\n".join(f"  - {o}" for o in offenders)
        ),
    )


def check_subnet_prefix(params: dict) -> CheckResult:
    """workloadSubnetPrefix must be /27 or larger."""
    val = (params.get("parameters") or {}).get("workloadSubnetPrefix", {}).get("value")
    if not isinstance(val, str) or "/" not in val:
        return CheckResult(
            f"workloadSubnetPrefix is /{MIN_SUBNET_PREFIX} or larger", "warn",
            "workloadSubnetPrefix not set or unparseable",
        )
    try:
        prefix = int(val.rsplit("/", 1)[1])
    except ValueError:
        return CheckResult(
            f"workloadSubnetPrefix is /{MIN_SUBNET_PREFIX} or larger", "warn",
            f"could not parse prefix length from {val!r}",
        )
    if prefix > MIN_SUBNET_PREFIX:
        return CheckResult(
            f"workloadSubnetPrefix is /{MIN_SUBNET_PREFIX} or larger", "fail",
            f"{val} is too small (prefix /{prefix})",
            fix=(
                f"Container Apps + private endpoints require at least /{MIN_SUBNET_PREFIX}.\n"
                "Edit infra/alz-overlay/main.parameters.json -> workloadSubnetPrefix."
            ),
        )
    return CheckResult(
        f"workloadSubnetPrefix is /{MIN_SUBNET_PREFIX} or larger", "pass",
        f"{val}",
    )


def _check_resource_id(name: str, resource_id: str) -> CheckResult:
    """Verify a single resource ID is reachable.

    Treats 403 as WARN (insufficient permissions) and missing/404 as FAIL.
    """
    if not resource_id or "CHANGEME" in resource_id:
        return CheckResult(name, "fail",
                           "resource id missing or placeholder")
    rc, _out, err = _az(["resource", "show", "--ids", resource_id, "-o", "json"])
    if rc == 0:
        return CheckResult(name, "pass", "reachable")
    err_lc = (err or "").lower()
    if "authorizationfailed" in err_lc or "forbidden" in err_lc:
        return CheckResult(
            name, "warn",
            "deploying principal cannot read this resource",
            fix=("Grant the deploying principal `Reader` on the hub resource, "
                 "or have CCoE confirm the ID is valid."),
        )
    return CheckResult(
        name, "fail",
        "az resource show returned non-zero",
        fix=("Verify the ID is correct and exists. az error tail:\n  "
             + (err.strip().splitlines() or ["(no stderr)"])[-1]),
    )


def check_hub_resources(params: dict) -> list[CheckResult]:
    """Run `az resource show` against every hub resource ID."""
    p = params.get("parameters") or {}
    out: list[CheckResult] = []
    out.append(_check_resource_id(
        "Hub vNet reachable",
        p.get("hubVnetId", {}).get("value", ""),
    ))
    out.append(_check_resource_id(
        "Hub Log Analytics workspace reachable",
        p.get("hubLogAnalyticsWorkspaceId", {}).get("value", ""),
    ))
    dns_zones = (p.get("privateDnsZoneIds", {}) or {}).get("value", {}) or {}
    for key, zone_id in dns_zones.items():
        out.append(_check_resource_id(
            f"Private DNS zone reachable [{key}]",
            zone_id,
        ))
    return out


def check_dns_zone_rbac(params: dict) -> CheckResult:
    """Best-effort warn when createDnsZoneLinks=true but RBAC may be missing.

    `az role assignment list --assignee <principal> --scope <zone>` requires
    `Microsoft.Authorization/roleAssignments/read` which not every JIT-
    elevated principal has -> we only print a generic reminder, not an
    actual probe (the probe would false-WARN too often).
    """
    p = params.get("parameters") or {}
    enabled = bool(p.get("createDnsZoneLinks", {}).get("value", False))
    if not enabled:
        return CheckResult("DNS zone link RBAC", "pass",
                           "createDnsZoneLinks=false (overlay does not write zones)")
    return CheckResult(
        "DNS zone link RBAC", "warn",
        "createDnsZoneLinks=true; deploying principal needs Private DNS Zone Contributor",
        fix=("Confirm the deploying identity holds `Private DNS Zone Contributor` "
             "on each zone in `privateDnsZoneIds`. CCoE typically grants this "
             "as part of the hub onboarding."),
    )


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------

def _print_report(results: list[CheckResult]) -> int:
    icon = {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}
    bar = "-" * 72
    print()
    print(bar)
    print(" ALZ overlay validation - read-only checks before `azd up`")
    print(bar)
    for r in results:
        print(f"  {icon[r.status]} {r.name:<48} {r.message}")
    fails = [r for r in results if r.status == "fail"]
    warns = [r for r in results if r.status == "warn"]
    print(bar)
    if fails:
        print(f" Result: [FAIL] {len(fails)} hard failure(s); `azd up` will fail.")
    elif warns:
        print(f" Result: [WARN] {len(warns)} warning(s); review before `azd up`.")
    else:
        print(" Result: [PASS] overlay is ready for `azd up`.")
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
    p.add_argument(
        "--params", default=str(DEFAULT_PARAMS),
        help=f"Path to overlay parameters JSON (default: {DEFAULT_PARAMS}).",
    )
    p.add_argument(
        "--skip-mode-check", action="store_true",
        help="Run checks even when accelerator.yaml mode is not alz-integrated.",
    )
    args = p.parse_args()

    if not args.skip_mode_check and not _required_mode_is_alz():
        print(
            "validate-alz: accelerator.yaml landing_zone.mode is not "
            "alz-integrated; skipping. Pass --skip-mode-check to override.",
            file=sys.stderr,
        )
        return 0

    params_path = pathlib.Path(args.params)
    if not params_path.exists():
        print(f"validate-alz: {params_path} does not exist", file=sys.stderr)
        return 2
    params = _load_params(params_path)

    results: list[CheckResult] = [check_no_placeholders(params)]
    # If placeholders are unfilled, hub-resource checks would all FAIL on
    # CHANGEME strings - skip them to keep the report focused.
    if results[0].status == "pass":
        results.append(check_subnet_prefix(params))
        results.extend(check_hub_resources(params))
        results.append(check_dns_zone_rbac(params))
    else:
        results.append(check_subnet_prefix(params))

    return _print_report(results)


if __name__ == "__main__":
    sys.exit(main())
