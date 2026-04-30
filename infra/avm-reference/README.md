# `infra/avm-reference/` — AVM-equivalent module exemplars (study-only)

**Read `docs/patterns/azure-ai-landing-zone/README.md` first** — this
folder is the Tier 2 (`landing_zone.mode: avm`) reference material.

## What this folder is

Hand-picked **Azure Verified Modules** (AVM) snippets that the partner
copies into `infra/modules/` (replacing the hand-rolled equivalents)
when moving from `standalone` → `avm`. Each file is a **self-contained
Bicep block** showing the AVM module reference, the canonical
parameters, and inline comments pointing at the AVM docs.

These files are **NOT wired into `infra/main.bicep`**. They do not
deploy on their own. The `/configure-landing-zone` custom agent walks the
partner through copying them in.

## What's in here today

| Resource | Hand-rolled (Tier 1) | AVM reference (Tier 2) | Status |
|---|---|---|---|
| Key Vault | `../modules/key-vault.bicep` | `key-vault.bicep` | Drop-in exemplar |
| AI Search | `../modules/ai-search.bicep` | `ai-search.bicep` | Drop-in exemplar |
| Container App | `../modules/container-app.bicep` | `container-app.bicep` | Drop-in exemplar (⚠ managed-env orphan) |
| Monitor / Log Analytics | `../modules/monitor.bicep` | `monitor.bicep` | Drop-in exemplar |

Each exemplar mirrors the corresponding hand-rolled module's param
signature + outputs, so a partner can replace the file with `cp` and
`azd up` without editing `infra/main.bicep`. Start with the Key Vault
exemplar — it shows the pattern most cleanly.

**What "drop-in" does NOT mean.** The exemplars give you AVM's
WAF-aligned shape for that one resource. They do not bring:
- Tier 3 plumbing for Container App (PE on managed-env + vNet
  integration) — the Container App exemplar has no PE params
  because that wiring requires a /23 infrastructure subnet owned by
  the overlay, not the module. See `infra/alz-overlay/README.md`
  "Container App reachability".
- Diagnostic settings — the current exemplars match the hand-rolled
  modules' Tier 1/2 behavior (no explicit diagnostic wiring).
  Hub-central Log Analytics wiring via `diagnosticSettings:` is
  partner-authored.
- Foundry parity (no AVM module — see exception below).

The Key Vault and AI Search exemplars **do** mirror the hand-rolled
modules' `peSubnetId` / `privateDnsZoneId` parameters, so a Tier 3
swap-in creates the PE + DNS zone group via AVM's `privateEndpoints:`
array shape without losing drop-in parity.

**⚠ container-app caveat.** The `app/managed-environment` AVM module
is currently marked **orphaned** in the registry (security + bug fixes
only). The `app/container-app` module itself is actively maintained.
Check <https://aka.ms/AVM/OrphanedModules> before adopting, and — for
regulated engagements — document the choice to move off the hand-rolled
module in the engagement's landing-zone decision log. The hand-rolled
`../modules/container-app.bicep` remains fully supported.

## Why Foundry is not in here

`Microsoft.CognitiveServices/accounts` (Foundry) does not have a
fully-GA AVM res module as of this writing. Track
<https://github.com/Azure/Azure-Verified-Modules/issues?q=cognitiveservices>.
Until then, keep `infra/modules/foundry.bicep` hand-rolled in Tier 2
as well, but add the AI ALZ-recommended parameters
(`networkAcls.defaultAction: Deny`, `publicNetworkAccess: Disabled`,
private endpoint binding) when moving to Tier 3.

## Upgrade cadence

When a new AVM module becomes GA that replaces one of our hand-rolled
modules, add an exemplar here (don't rewrite `infra/modules/` directly
— partners customize that swap themselves). Update this table and open
a PR; the `ga-sdk-freshness` schedule will flag stale references.
