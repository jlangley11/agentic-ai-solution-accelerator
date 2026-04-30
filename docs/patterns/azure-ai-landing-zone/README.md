# Pattern — Azure AI Landing Zone (AI ALZ) alignment

Partners deploy this accelerator into wildly different customer
environments: an SMB with a fresh tenant; a mid-market customer with a
platform team but no hub-spoke network; a regulated enterprise with a
full **Azure AI Landing Zone** already in place. One Bicep shape can't
serve all three without either forcing ALZ complexity on the SMB or
leaving the enterprise partner to rewrite the infra.

This pattern defines **three landing-zone tiers** the partner picks in
`accelerator.yaml` (`landing_zone.mode`). The framework ships reference
artifacts for each tier; Copilot helps the partner move between tiers
via the `/configure-landing-zone` custom agent.

## Tier status

| Tier | Status | What's shipped today |
|---|---|---|
| Tier 1 `standalone` | **GA** | `infra/main.bicep` + modules; `azd up` stands up a public-endpoint deploy with Entra-only auth + RAI + workspace diagnostics. |
| Tier 2 `avm` | **Preview** | Four drop-in AVM exemplars in `infra/avm-reference/` (`key-vault`, `ai-search`, `container-app`, `monitor`) — each matches the hand-rolled module's param signature + outputs so the swap is `cp` without main.bicep edits. Partner declares coverage via `landing_zone.avm_services`; lint blocks if declared services lack an exemplar or are still hand-rolled when mode=avm. **Top-level network plumbing (subnet for PE, hub private-DNS zone binding) is partner-authored** — the AVM modules expose `privateEndpoints:` / `networkAcls:` knobs but the accelerator does not wire them inline (that's Tier 3, `alz-overlay`). Foundry stays hand-rolled (no GA AVM res module for `CognitiveServices/accounts`). Container Apps managed-environment AVM module is **orphaned** — see `infra/avm-reference/README.md` before adopting. |
| Tier 3 `alz-integrated` | **Preview** | Subscription-scope overlay creates spoke RG + vNet + NSG + peering, with opt-in hub DNS zone vNet-links. Workload `infra/main.bicep` creates PEs + DNS zone groups for **Key Vault + AI Search + Foundry** (Foundry PE registers all three AIServices DNS suffixes: `cognitiveservices` / `openai` / `services.ai`). **The shipped Container App is NOT vNet-integrated**, so it cannot consume the private back-end endpoints as-deployed — the partner completes the app-path reachability by enlarging the workload subnet to /23 and enabling managed-env vNet integration, or by fronting an external env with App Gateway / Front Door routed through the hub firewall. See `infra/alz-overlay/README.md` "Container App reachability" for both paths. Route table to the hub firewall and hub-LAW diagnostic settings are still partner-authored. |

### "Disabled" vs. "Fully private & reachable"

These are not the same thing and the difference will bite you.

- **`publicNetworkAccess: Disabled`** — the data plane refuses public traffic. The Tier 3 parameter file flips this for you.
- **Fully private & reachable** — there's a private endpoint in your vNet, its IP resolves via the hub's private DNS zones, and the client runs somewhere that can route to that IP.

Tier 3 today gets you partway: when the overlay outputs are wired through `azd env set` (see `infra/alz-overlay/README.md`), the workload deploy creates PE + DNS zone groups for **Key Vault, AI Search, and Foundry** automatically. The Foundry PE registers all three DNS suffixes the shipped runtime uses (`cognitiveservices.azure.com`, `openai.azure.com`, `services.ai.azure.com`) so the `AZURE_AI_FOUNDRY_ENDPOINT` project URL actually resolves privately.

**The shipped Container App is NOT vNet-integrated.** The managed environment ships in Azure's default (non-vNet) mode, which means: (a) the app container cannot reach the privatized back-end PEs from inside the spoke vNet, and (b) ingress cannot be routed through the hub firewall. The partner picks one of:

1. **External env + App Gateway / Front Door fronted by the hub firewall** (simplest; `externalIngress: true` and public traffic traverses the hub). Requires partner to provision AGW/AFD.
2. **Internal env + vNet integration.** Partner enlarges `workloadSubnetPrefix` to `/23`, sets `externalIngress: false`, and adds `vnetConfiguration` + a PE on the managed env. The `/configure-landing-zone` custom agent walks through subnet enlargement; the PE + DNS link are authored by hand.

If you set `mode: alz-integrated`, deploy, and skip the overlay output wiring, the workload will be provisioned with public access off and the PEs uncreated — services become **unreachable**. That fails closed (intentional).

## Tier decision tree

```
Customer has an existing Azure AI Landing Zone (hub vNet, private DNS
zones, policy assignments, MG hierarchy)?
├── YES  ──→  mode: alz-integrated        (Tier 3)
│
└── NO
     ├── Customer has any platform/CCoE team and wants AVM alignment,
     │   private endpoints, and CAF-shaped guardrails from day one?
     │   ├── YES ──→  mode: avm              (Tier 2)
     │   └── NO
     │        └── Pilot / sandbox / SMB greenfield?
     │            └── YES ──→  mode: standalone   (Tier 1)
```

## Tier 1 — `standalone` (default)

**What it is.** A single resource group, hand-rolled Bicep modules in
`infra/modules/`, public endpoints on Foundry and AI Search (with
Entra-only auth + Microsoft-managed content safety filter), and the
WAF/RAI baseline (see "What's consistent across all three tiers"
below). `azd up` stands it up in ~15 minutes.

**When to use.** Self-host pilot in the partner's own subscription;
SMB customer with no existing Azure governance; hackathon / demo
environments. Also the correct starting point for any partner who
doesn't yet know the customer's answer to the decision tree.

**What the partner owns.** Network exposure (currently public endpoints
with RBAC), diagnostics, backup, quotas — nothing to inherit from a
hub. Works but is **not** the shape you put in front of a regulated
enterprise.

**Files involved.**
- `infra/main.bicep` + `infra/modules/*.bicep` (shipped)
- `infra/main.parameters.json` (shipped)
- No overlay, no AVM references required.

**Going private without leaving Tier 1.** Setting the Bicep param `enablePrivateLink=true` flips `publicNetworkAccess` to `Disabled` on both the Cognitive Services (Foundry) account and Azure AI Search, and sets `networkAcls.defaultAction` to `Deny` on the Foundry account. Creating the actual private endpoints and DNS zones requires a pre-existing VNet and subnet — this is **bring-your-own** in the accelerator and not created by `azd up`. Add private-endpoint + private DNS zone resources in your own fork when targeting a regulated customer; the accelerator's shape (GA API versions, disabled public access when requested) won't fight you. If you need this end-to-end (PEs + DNS provisioned for you), graduate to **Tier 2 (`avm`)** below.

## Tier 2 — `avm` (AVM-aligned standalone)

> **What's shipped today vs partner-authored:**
> - **Shipped:** AVM exemplars in `infra/avm-reference/{key-vault,ai-search,container-app,monitor}.bicep` (each compiles standalone with `az bicep build`); the `landing_zone_mode_consistent` lint rule; `/configure-landing-zone` custom agent for the migration walk-through.
> - **Partner authors:** the `cp` of each exemplar into `infra/modules/`, validation against their region/quota, the new vNet + subnet + private DNS zones in their subscription, and the `landing_zone.avm_services` declaration in `accelerator.yaml`. Foundry stays hand-rolled (intentionally not in AVM).
> - **Reach for:** mid-market with PEs and AVM cadence; no hub yet.

**What it is.** Same topology as Tier 1 (no hub), but the Bicep is
migrated to **Azure Verified Modules** (`br/public:avm/res/<...>`)
wherever AVM is GA. The accelerator ships **drop-in exemplars** in
`infra/avm-reference/` — each matches the hand-rolled module's param
signature + outputs so the partner can `cp` into `infra/modules/`
without editing `main.bicep`. Private endpoints, private-DNS zone
bindings, and hub-LAW diagnostics are **not** wired inline — that is
Tier 3 (alz-overlay) work. Lint rule `landing_zone_mode_consistent`
asserts each declared `avm_services` entry has an actual
`module ... 'br/public:avm/...'` declaration in the corresponding
module file.

**When to use.** Mid-market customer with a platform team who wants
CAF-shaped guardrails, private networking, and AVM maintenance cadence
— but doesn't yet have a hub or ALZ to plug into.

**What the partner owns.** The network (new vNet in the same
subscription), private DNS zones, quota requests. Everything else
inherits from AVM's opinions.

**Files involved.**
- `infra/avm-reference/README.md` — how to swap a hand-rolled module
  for its AVM equivalent (study-only exemplars).
- `infra/avm-reference/{key-vault,ai-search,container-app,monitor}.bicep`
  — AVM exemplars for the core workload services. Each compiles
  standalone (`az bicep build`) and documents which hand-rolled module
  in `infra/modules/` it replaces. Foundry intentionally excluded.
- `infra/modules/*.bicep` — partner replaces selected modules with AVM
  references via `/configure-landing-zone` when migrating to Tier 2.
- `accelerator.yaml` → `landing_zone.mode: avm` **and**
  `landing_zone.avm_services: [key-vault, ...]` listing the services
  actually migrated (lint asserts the list matches reality).

## Tier 3 — `alz-integrated` (Azure AI Landing Zone)

> **What's shipped today vs partner-authored:**
> - **Shipped:** `infra/alz-overlay/main.bicep` subscription-scope deploy (spoke RG + vNet + NSG + peering, opt-in hub DNS zone vNet-link); `infra/main.parameters.alz.json` pre-baked Tier 3 workload parameters; `/configure-landing-zone` custom agent that fills in hub resource IDs.
> - **Partner authors:** coordination with the customer's CCoE for subscription vending; the UDR (route table on spoke subnet → hub firewall) — overlay provisions the subnet + NSG, but **the UDR is not shipped**; MG placement; hub DNS zone identity access; engagement-specific env-var defaults.
> - **Reach for:** regulated enterprise; customers with an existing AI ALZ or general ALZ; Financial Services / Health / Public Sector.

**What it is.** The accelerator lands in a **spoke subscription** that
is already part of the customer's AI ALZ. Resources expose **private
endpoints only**; PE IPs register into the **hub's** private DNS
zones (not new ones); Foundry network isolation is enabled; **egress
routing to the hub firewall is partner-authored** (route table on the
spoke subnet → hub FW) — the overlay provisions the subnet + NSG but
the UDR is not shipped. Subscription-scope policy assignments
inherited from the management group enforce the `AI ALZ` initiative
(diagnostics, customer-managed keys, content safety, allowed
locations, etc).

The accelerator ships `infra/alz-overlay/` — a **subscription-scope**
Bicep deployment that is separate from `infra/main.bicep` and wires
the spoke into the hub. Partner still runs `infra/main.bicep` for the
workload itself, but with `publicNetworkAccess: Disabled`, PE
resource IDs pointing at the hub's DNS zones, and the resource group
placed under the AI ALZ MG.

**When to use.** Regulated enterprise; any customer with an existing
Azure Landing Zone or AI-specific ALZ; Financial Services / Health /
Public Sector engagements; anywhere "connect to our hub" is a hard
requirement.

**What the partner owns.** Coordinating with the customer's CCoE for
subscription vending, hub peering, DNS zone identity access, and MG
placement. The accelerator provides the Bicep scaffold; `docs/customer-runbook.md`
covers Tier 3 day-2 operations.

**Files involved.**
- `infra/alz-overlay/main.bicep` — subscription-scope deploy that
  creates the spoke RG + vNet + NSG + peering, with opt-in hub DNS
  zone vNet-link creation. Partner fills in hub resource IDs via
  `/configure-landing-zone` (in `main.parameters.json`, not
  `main.bicep`). The overlay's outputs flow into `azd env set` before
  the workload deploy.
- `infra/alz-overlay/README.md` — pre-reqs, what the overlay does /
  does not do, and the `az deployment sub create` command.
- `infra/main.parameters.alz.json` — **shipped**, pre-baked Tier 3
  workload parameters: `enablePrivateLink: true` (→
  `publicNetworkAccess: Disabled` on Foundry, Search, Key Vault) and
  `externalIngress: false` (→ Container App internal-only). Partner
  adjusts env-var defaults to match the engagement.

## What's consistent across all three tiers

Regardless of mode, **every** tier ships with:

- Entra-only auth, no shared keys.
- Repo-managed `accelerator-default-policy` content safety filter (based on `Microsoft.Default`) bound to all chat / generative model deployments. Embedding deployments have no RAI binding by design.
- App Insights + Log Analytics diagnostics (workspace-based).
- Key Vault with soft-delete + purge protection, RBAC-only.
- Managed Identity end-to-end (no SPN secrets).
- Lint check `no_preview_api_versions` in `scripts/accelerator-lint.py`
  enforces GA-only Bicep API versions; pre-GA versions are blocked
  unless explicitly allow-listed in `infra/.ga-exceptions.yaml`.

These are WAF/RAI baseline, not landing-zone-specific — they are
always on.

## Further reading

- **Azure Well-Architected Framework for AI workloads** — <https://learn.microsoft.com/azure/well-architected/ai/>
- **Cloud Adoption Framework: Scenario — AI** — <https://learn.microsoft.com/azure/cloud-adoption-framework/scenarios/ai/>
- **Azure Landing Zones (ALZ) accelerator** — <https://aka.ms/alz>
- **AI Landing Zone (AI ALZ) reference** — <https://aka.ms/ai-landing-zone>
- **Azure Verified Modules (AVM)** — <https://azure.github.io/Azure-Verified-Modules/>
- This repo: `docs/patterns/waf-alignment/README.md`, `docs/patterns/rai/README.md`.
