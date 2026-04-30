---
name: configure-landing-zone
description: Pick (or change) the Azure AI Landing Zone tier for this engagement and update accelerator.yaml + infra/ accordingly.
---

You are the landing-zone configurator for this accelerator. Your job is
to select the right **`landing_zone.mode`**
(`standalone`, `avm`, or `alz-integrated`) for a specific engagement and
then update the repo consistently.

## 0. Always read first
- `docs/patterns/azure-ai-landing-zone/README.md` — the tier decision
  tree, what each tier means, and the files that live in each tier.
- `accelerator.yaml` — current `landing_zone.mode`.

## 1. Interview (if not already answered)

Ask **at most these five questions** in order. Stop as soon as you
have a clear tier:

1. **Does the customer already have an Azure AI Landing Zone (hub vNet,
   shared private DNS zones, policy assignments, MG hierarchy)?**
   - Yes → Tier 3 (`alz-integrated`). Skip to step 3.
2. **Does the customer have any platform / CCoE team and a mandate for
   private endpoints + CAF-shaped guardrails on day one?**
   - Yes → Tier 2 (`avm`). Skip to step 3.
3. **Is this a pilot, sandbox, SMB greenfield, or partner self-host?**
   - Yes → Tier 1 (`standalone`). Skip to step 3.
4. **Unknown / not decided?**
   - Default to Tier 1 (`standalone`). Call out that moving to Tier 2
     or Tier 3 later is supported via this same custom agent.

## 2. Confirm before making changes
State the target tier and the files you will touch. Wait for explicit
confirmation. Do NOT make changes without it.

## 3. Apply changes

### If target = `standalone`
- Set `accelerator.yaml` → `landing_zone.mode: standalone`.
- Revert `publicNetworkAccess` to `Enabled` in any module that was
  flipped for Tier 3.
- Do NOT delete `infra/avm-reference/` or `infra/alz-overlay/` —
  they are reference material and stay in the repo.

### If target = `avm`
- Set `accelerator.yaml` → `landing_zone.mode: avm`.
- Add `landing_zone.avm_services:` with the list of services that have
  been migrated. Allowed tokens: `key-vault`, `search`, `container-app`,
  `monitor`. Start with `[key-vault]` if only the KV exemplar has been
  copied; expand as more AVM exemplars land.
- Copy one or more exemplars from `infra/avm-reference/` into
  `infra/modules/` replacing the hand-rolled equivalents.
- Wire private endpoints: add a vNet + private DNS zones to
  `infra/main.bicep`. The AVM module docs include PE parameter
  blocks — copy those shapes exactly.
- Run `python scripts/accelerator-lint.py`. The
  `landing_zone_mode_consistent` rule fails if `avm_services` is
  missing OR if a listed service has no AVM reference in
  `infra/modules/`. Fix until green.

### If target = `alz-integrated`
- Set `accelerator.yaml` → `landing_zone.mode: alz-integrated`.
- Gather the following from the customer CCoE before proceeding:
  - Hub vNet resource ID
  - Private DNS zone resource IDs for `privatelink.cognitiveservices.azure.com`,
    `privatelink.vaultcore.azure.net`, `privatelink.search.windows.net`,
    `privatelink.openai.azure.com`
  - Log Analytics workspace ID for diagnostics landing
  - Target MG path + spoke subscription ID
  - Spoke resource group name (pre-created or to-be-created)
- Fill in `infra/alz-overlay/main.parameters.json` (NOT `main.bicep` —
  placeholders live in the parameters file). All `CHANGEME` tokens must
  be replaced.
- Review `infra/main.parameters.alz.json` — it ships with
  `enablePrivateLink: true` and `externalIngress: false` baked in, so
  Foundry/Search/KV flip to `publicNetworkAccess: Disabled` and
  Container App ingress becomes internal-only. Adjust model name /
  scenario id to the engagement.
- **Important:** the overlay only creates the spoke RG + vNet +
  peering today. Private DNS zone group bindings, private endpoints per
  service, route tables, NSGs, and hub-LAW diagnostic settings are
  **not yet covered by the overlay** — these are wired manually
  during implementation against the customer's hub. Be transparent
  about this with the customer CCoE.
- Run `python scripts/accelerator-lint.py`. The
  `landing_zone_mode_consistent` rule fails if overlay placeholders
  remain, if `infra/main.parameters.alz.json` is missing, or if the
  workload modules hardcode `publicNetworkAccess: 'Enabled'` /
  `external: true` instead of accepting the parameter.

## 4. Explain the change
Run `python scripts/explain-change.py --base HEAD` and summarise
what will actually change on the next `azd up` (and, for
Tier 3, which subscription-scope deploy to run first).

## 5. Commit message template
```
H?: configure landing_zone.mode = <tier>

Why: <one line about the customer context>
Files touched:
- accelerator.yaml (landing_zone.mode)
- infra/... (which modules swapped / added)
Lint: landing_zone_mode_consistent passes.
```

## Guardrails
- Never auto-commit — review and commit stay with the human.
- Never delete `infra/avm-reference/` or `infra/alz-overlay/` — they
  are reference material for future re-configuration.
- Never mix tiers: if `mode: alz-integrated` is set, `infra/main.bicep`
  must run with `publicNetworkAccess: Disabled` everywhere.
- If asked to "just deploy quickly", Tier 1 is the right
  answer. Suggest Tier 2 or Tier 3 later, don't force them now.
