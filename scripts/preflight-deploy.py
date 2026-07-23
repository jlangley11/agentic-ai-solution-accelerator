"""Read-only deploy preflight for the selected deployment target.

Runs deterministic ``az`` checks against the partner's currently-logged-in
Azure context to surface documented deployment failures before provisioning.
The default ``selfhost`` target preserves the root ``azd up`` checks. The
``foundry-prompt`` target checks the agent-only Foundry workspace. The
``hosted-preview`` target additionally gates preview runtime, CLI, extension,
and region requirements.

Scope:
  - ``az account show`` parity (logged in, expected tenant if --tenant given)
  - Target-specific required-RP registration check
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
    python scripts/preflight-deploy.py --region eastus2 \
      --deployment-target foundry-prompt
    python scripts/preflight-deploy.py --region westus3 \
      --deployment-target hosted-preview --acknowledge-preview

Exit codes:
  0 — all hard checks pass (warnings allowed)
  1 — at least one hard check failed; the selected deployment will likely fail
  2 — preflight itself broke (az CLI missing, accelerator.yaml malformed)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import total_ordering

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Resource providers that infra/main.bicep depends on. Missing registrations
# manifest as `azd up` failures partway through provision.
SELFHOST_REQUIRED_RPS = [
    "Microsoft.CognitiveServices",
    "Microsoft.Search",
    "Microsoft.App",
    "Microsoft.OperationalInsights",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.ManagedIdentity",
]

HOSTED_PREVIEW_REQUIRED_RPS = [
    "Microsoft.CognitiveServices",
    "Microsoft.Search",
    "Microsoft.OperationalInsights",
    "Microsoft.Insights",
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

HOSTED_PREVIEW_REGIONS = {
    "australiaeast",
    "brazilsouth",
    "canadacentral",
    "canadaeast",
    "eastus",
    "eastus2",
    "francecentral",
    "germanywestcentral",
    "italynorth",
    "japaneast",
    "japanwest",
    "koreacentral",
    "northcentralus",
    "norwayeast",
    "polandcentral",
    "southafricanorth",
    "southcentralus",
    "southindia",
    "southeastasia",
    "spaincentral",
    "swedencentral",
    "switzerlandnorth",
    "switzerlandwest",
    "uaenorth",
    "ukwest",
    "westcentralus",
    "westeurope",
    "westus",
    "westus3",
}

MIN_AZD_VERSION = "1.27.1"
RECOMMENDED_AZD_VERSION = "1.28.0"
MIN_AGENTS_EXTENSION_VERSION = "1.0.0-beta.6"
MIN_FOUNDRY_EXTENSION_VERSION = "1.0.0-beta.1"


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    fix: str | None = None


@total_ordering
@dataclass(frozen=True)
class ParsedVersion:
    major: int
    minor: int
    patch: int
    prerelease_rank: int = 4
    prerelease_number: int = 0

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ParsedVersion):
            return NotImplemented
        return (
            self.major,
            self.minor,
            self.patch,
            self.prerelease_rank,
            self.prerelease_number,
        ) < (
            other.major,
            other.minor,
            other.patch,
            other.prerelease_rank,
            other.prerelease_number,
        )


_VERSION_RE = re.compile(
    r"(?<!\d)(\d+)\.(\d+)\.(\d+)"
    r"(?:[-.]?(alpha|a|beta|b|preview|pre|rc)[.-]?(\d+)?)?",
    re.IGNORECASE,
)
_PRERELEASE_RANK = {
    "alpha": 0,
    "a": 0,
    "preview": 1,
    "pre": 1,
    "beta": 2,
    "b": 2,
    "rc": 3,
}


def parse_version(value: str) -> ParsedVersion | None:
    """Extract a comparable semantic version from stable or prerelease output."""
    match = _VERSION_RE.search(value)
    if not match:
        return None
    label = (match.group(4) or "").lower()
    rank = _PRERELEASE_RANK.get(label, 4)
    return ParsedVersion(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        rank,
        int(match.group(5) or 0),
    )


def _command_argv(executable: str, args: list[str]) -> list[str]:
    """Execute the fully resolved command path with its arguments."""
    return [executable, *args]


def _run_command(command: str, args: list[str]) -> tuple[int, str, str]:
    executable = shutil.which(command)
    if not executable:
        return 127, "", f"{command} not found on PATH"
    try:
        cp = subprocess.run(
            _command_argv(executable, args),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124 if isinstance(exc, subprocess.TimeoutExpired) else 126, "", str(exc)


def _az(args: list[str], *, capture: bool = True) -> tuple[int, str, str]:
    """Run an ``az`` command and return (rc, stdout, stderr).

    Never raises. ``az`` not installed → rc=127 with a synthetic stderr.

    On Windows ``az`` is a ``.cmd`` shim, so we resolve the full path via
    ``shutil.which`` rather than relying on PATH lookup inside CreateProcess.
    """
    if capture:
        return _run_command("az", args)
    executable = shutil.which("az")
    if not executable:
        return 127, "", "az CLI not found on PATH"
    try:
        cp = subprocess.run(
            _command_argv(executable, args),
            check=False,
            capture_output=False,
            text=True,
            timeout=60,
        )
        return cp.returncode, "", ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124 if isinstance(exc, subprocess.TimeoutExpired) else 126, "", str(exc)


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


def check_resource_providers(deployment_target: str = "selfhost") -> CheckResult:
    required_rps = (
        HOSTED_PREVIEW_REQUIRED_RPS
        if deployment_target in {"foundry-prompt", "hosted-preview"}
        else SELFHOST_REQUIRED_RPS
    )
    not_registered: list[str] = []
    for rp in required_rps:
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
        f"{len(required_rps)}/{len(required_rps)} registered",
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


def check_hosted_preview_region(region: str) -> CheckResult:
    normalized = region.strip().lower().replace(" ", "")
    if normalized in HOSTED_PREVIEW_REGIONS:
        return CheckResult("Hosted Agents available in region", "pass", normalized)
    return CheckResult(
        "Hosted Agents available in region",
        "fail",
        f"'{region}' is not in the documented 29-region Hosted Agents preview list",
        fix=(
            "Choose a region listed at "
            "https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents"
            "#region-availability."
        ),
    )


def check_preview_acknowledged(acknowledged: bool) -> CheckResult:
    if acknowledged:
        return CheckResult(
            "Hosted preview explicitly acknowledged",
            "pass",
            "preview limitations accepted for this deployment",
        )
    return CheckResult(
        "Hosted preview explicitly acknowledged",
        "fail",
        "`--acknowledge-preview` is required for hosted-preview",
        fix=(
            "Review deploy/hosted-preview/README.md, obtain the engagement's preview "
            "approval, then re-run with `--acknowledge-preview`."
        ),
    )


def check_python_version(
    version_info: tuple[int, int, int] | None = None,
) -> CheckResult:
    current = version_info or (
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    )
    rendered = ".".join(str(part) for part in current[:3])
    if current[:2] >= (3, 13):
        return CheckResult("Python >= 3.13", "pass", rendered)
    return CheckResult(
        "Python >= 3.13",
        "fail",
        f"found Python {rendered}",
        fix="Install/select Python 3.13 before deploying the hosted preview.",
    )


def check_azd_version() -> CheckResult:
    rc, out, err = _run_command("azd", ["version"])
    if rc != 0:
        return CheckResult(
            "azd >= 1.27.1",
            "fail",
            err.strip() or "could not run `azd version`",
            fix="Install Azure Developer CLI 1.28.0 (verified) or newer.",
        )
    actual = parse_version(out)
    minimum = parse_version(MIN_AZD_VERSION)
    recommended = parse_version(RECOMMENDED_AZD_VERSION)
    if actual is None or minimum is None or recommended is None:
        return CheckResult(
            "azd >= 1.27.1",
            "fail",
            f"could not parse version from: {out.strip()!r}",
            fix="Install the stable azd 1.28.0 release.",
        )
    if actual < minimum:
        return CheckResult(
            "azd >= 1.27.1",
            "fail",
            f"found {out.strip()}",
            fix="Upgrade to azd 1.28.0 (verified) or newer.",
        )
    status = "pass" if actual >= recommended else "warn"
    fix = None if status == "pass" else "Upgrade to the verified azd 1.28.0 release."
    return CheckResult("azd >= 1.27.1", status, out.strip(), fix=fix)


def check_agents_extension_version() -> CheckResult:
    rc, out, err = _run_command("azd", ["ext", "list", "-o", "json"])
    if rc != 0:
        return CheckResult(
            "azure.ai.agents >= 1.0.0-beta.6",
            "fail",
            err.strip() or "could not list azd extensions",
            fix=(
                "Run `azd ext install azure.ai.agents "
                "--version 1.0.0-beta.6 --force`."
            ),
        )
    try:
        extensions = json.loads(out) or []
    except json.JSONDecodeError:
        return CheckResult(
            "azure.ai.agents >= 1.0.0-beta.6",
            "fail",
            "azd extension list returned non-JSON",
            fix="Reinstall the azure.ai.agents 1.0.0-beta.6 extension.",
        )
    entry = next(
        (
            item
            for item in extensions
            if isinstance(item, dict) and item.get("id") == "azure.ai.agents"
        ),
        None,
    )
    installed = (entry or {}).get("installedVersion") or ""
    actual = parse_version(installed)
    minimum = parse_version(MIN_AGENTS_EXTENSION_VERSION)
    if actual is None or minimum is None or actual < minimum:
        found = installed or "not installed"
        return CheckResult(
            "azure.ai.agents >= 1.0.0-beta.6",
            "fail",
            f"found {found}",
            fix=(
                "Run `azd ext install azure.ai.agents "
                "--version 1.0.0-beta.6 --force`."
            ),
        )
    return CheckResult(
        "azure.ai.agents >= 1.0.0-beta.6",
        "pass",
        installed,
    )


def check_foundry_extension_version() -> CheckResult:
    rc, out, err = _run_command("azd", ["ext", "list", "-o", "json"])
    if rc != 0:
        return CheckResult(
            "microsoft.foundry >= 1.0.0-beta.1",
            "fail",
            err.strip() or "could not list azd extensions",
            fix=(
                "Run `azd ext install microsoft.foundry "
                "--version 1.0.0-beta.1 --force --no-prompt`."
            ),
        )
    try:
        extensions = json.loads(out) or []
    except json.JSONDecodeError:
        return CheckResult(
            "microsoft.foundry >= 1.0.0-beta.1",
            "fail",
            "azd extension list returned non-JSON",
            fix="Reinstall the microsoft.foundry 1.0.0-beta.1 extension.",
        )
    entry = next(
        (
            item
            for item in extensions
            if isinstance(item, dict) and item.get("id") == "microsoft.foundry"
        ),
        None,
    )
    installed = (entry or {}).get("installedVersion") or ""
    actual = parse_version(installed)
    minimum = parse_version(MIN_FOUNDRY_EXTENSION_VERSION)
    if actual is None or minimum is None or actual < minimum:
        found = installed or "not installed"
        return CheckResult(
            "microsoft.foundry >= 1.0.0-beta.1",
            "fail",
            f"found {found}",
            fix=(
                "Run `azd ext install microsoft.foundry "
                "--version 1.0.0-beta.1 --force --no-prompt`."
            ),
        )
    return CheckResult(
        "microsoft.foundry >= 1.0.0-beta.1",
        "pass",
        installed,
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

def _print_report(
    results: list[CheckResult],
    deployment_target: str = "selfhost",
) -> int:
    icon = {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}
    bar = "-" * 72
    print()
    print(bar)
    print(
        " Deploy preflight - "
        f"target={deployment_target}, read-only checks against your current az context"
    )
    print(bar)
    for r in results:
        print(f"  {icon[r.status]} {r.name:<42} {r.message}")
    fails = [r for r in results if r.status == "fail"]
    warns = [r for r in results if r.status == "warn"]
    print(bar)
    target_command = {
        "hosted-preview": "hosted preview provision/deploy",
        "foundry-prompt": "Foundry prompt-agent provision",
        "selfhost": "selfhost `azd up`",
    }[deployment_target]
    if fails:
        print(
            f" Result: [FAIL] {len(fails)} hard failure(s); "
            f"the selected {target_command} will likely fail."
        )
    elif warns:
        print(
            f" Result: [WARN] {len(warns)} warning(s); "
            f"the selected {target_command} may proceed but watch for these."
        )
    else:
        print(
            f" Result: [PASS] all checks passed; the selected {target_command} is ready."
        )
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
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    p.add_argument("--region", required=True,
                   help="Target Azure region for the selected deployment (e.g. eastus2).")
    p.add_argument("--tenant", default=None,
                   help="Expected tenant GUID; preflight fails if mismatched.")
    p.add_argument("--subscription", default=None,
                   help="Expected subscription GUID; preflight fails if mismatched.")
    p.add_argument(
        "--deployment-target",
        choices=("selfhost", "foundry-prompt", "hosted-preview"),
        default="selfhost",
        help="Deployment shape to validate (default: selfhost).",
    )
    p.add_argument(
        "--acknowledge-preview",
        action="store_true",
        help="Explicitly acknowledge Hosted Agents preview limitations.",
    )
    args = p.parse_args()

    default_model = _load_default_model()
    if default_model is None:
        print("preflight: accelerator.yaml has no `models[]` block", file=sys.stderr)
        return 2

    results: list[CheckResult] = []
    if args.deployment_target == "hosted-preview":
        results.extend([
            check_preview_acknowledged(args.acknowledge_preview),
            check_python_version(),
            check_azd_version(),
            check_agents_extension_version(),
            check_foundry_extension_version(),
        ])
        if any(result.status == "fail" for result in results):
            return _print_report(results, args.deployment_target)
    elif args.deployment_target == "foundry-prompt":
        results.extend([
            check_azd_version(),
            check_foundry_extension_version(),
        ])
        if any(result.status == "fail" for result in results):
            return _print_report(results, args.deployment_target)

    results.append(check_az_login(args.tenant, args.subscription))
    # If the login check fails, downstream az calls will all fail too; bail early.
    if results[-1].status == "fail":
        return _print_report(results, args.deployment_target)

    results.extend([
        check_resource_providers(args.deployment_target),
        check_region_exists(args.region),
        (
            check_hosted_preview_region(args.region)
            if args.deployment_target == "hosted-preview"
            else check_foundry_region(args.region)
        ),
        check_model_available(args.region, default_model),
        check_model_quota(args.region, default_model),
    ])
    return _print_report(results, args.deployment_target)


if __name__ == "__main__":
    sys.exit(main())
