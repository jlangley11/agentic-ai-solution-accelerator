# `infra/alz-overlay/` — Azure AI Landing Zone integration skeleton

**Read `docs/patterns/azure-ai-landing-zone/README.md` first** — this
folder is the Tier 3 (`landing_zone.mode: alz-integrated`) reference
material.

## What this folder is

A **subscription-scope** Bicep deployment that wires the accelerator's
spoke resources into a customer's existing AI ALZ. It is NOT part of
`infra/main.bicep` (which is resource-group-scope). The partner runs
`main.bicep` in here first (to stand up the spoke RG with diagnostics
and private DNS zone *group* references pointing at the hub), then
runs the workload `infra/main.bicep` with the Tier-3 parameter file.

This folder ships as a **skeleton** — it compiles and has the right
shape, but the hub resource IDs are placeholders. The partner fills
them in via the `/configure-landing-zone` custom agent.

## Pre-requisites (partner collects from customer CCoE)

- **Management group path** for AI workloads (e.g. `.../mg-alz/mg-landingzones/mg-ai`).
- **Spoke subscription ID** (pre-vended from the customer's subscription vending process).
- **Hub vNet resource ID** for peering.
- **Private DNS zone resource IDs** under the hub's `rg-dns` (or equivalent):
  - `privatelink.cognitiveservices.azure.com` (Foundry account endpoint)
  - `privatelink.openai.azure.com` (Foundry OpenAI model inference)
  - `privatelink.services.ai.azure.com` (Foundry project endpoint — `AZURE_AI_FOUNDRY_ENDPOINT`)
  - `privatelink.vaultcore.azure.net` (Key Vault)
  - `privatelink.search.windows.net` (AI Search)
  - `privatelink.monitor.azure.com` (for Private Link Scope, optional)
- **Log Analytics workspace resource ID** in the hub's management subscription.
- **Allowed locations** from the customer's ALZ policy initiative.

## What `main.bicep` does today

1. Creates the spoke resource group (at subscription scope).
2. Creates a spoke vNet with a `snet-workload` subnet.
3. Creates a baseline NSG on the workload subnet (allow intra-vNet,
   deny inbound from Internet) and associates it with the subnet.
4. Establishes vNet peering to the hub vNet (bidirectional config on the
   spoke side; the hub-side peering must be created by the customer's
   CCoE with `allowForwardedTraffic` + `useRemoteGateways` as appropriate).
5. **Opt-in** (`createDnsZoneLinks: true`): creates vNet-links on each
   hub private DNS zone (`privateDnsZoneIds.{cognitiveservices, openai,
   servicesai, keyvault, search}`) to the spoke vNet, so PEs resolve
   through the hub zones. Requires the deploying identity to have
   **Private DNS Zone Contributor** on each zone's RG. Default
   `false` — most regulated customers have DNS delegated to CCoE and
   want the links created out-of-band.

Outputs (`workloadSubnetId`, `workloadNsgId`, `privateDnsZoneIds`,
`hubLogAnalyticsWorkspaceId`) flow into `azd env set` before the
workload `infra/main.bicep` runs with `main.parameters.alz.json`.

## Where reachability is completed

Workload private endpoints for **Key Vault, AI Search, and Foundry**
are created by the hand-rolled modules in `infra/modules/` when
`peSubnetId` and the relevant `privateDnsZoneIds.*` values are
non-empty — i.e. when the workload deploy runs with
`main.parameters.alz.json` after the overlay. The Foundry PE registers
into **all three** AIServices DNS suffixes on one PE (account,
project, openai) so every hostname the shipped runtime produces
(`AZURE_AI_FOUNDRY_ENDPOINT`, etc.) resolves privately.

**The shipped Container App is NOT vNet-integrated** in Tier 3. The
default managed-environment mode puts the app outside the spoke vNet,
so it cannot consume the private KV / Search / Foundry PEs from its
runtime. This is an explicit partner completion step — H9 privatizes
the data plane; the app-path integration is still owned by the partner.

### Container App reachability (partner-owned)

Pick one of these to actually make the app reachable and able to talk
to the privatized back-ends:

1. **External env + App Gateway / Front Door fronted by the hub FW**
   (simplest; `externalIngress: true`, public traffic traverses the
   hub FW). Partner owns AGW/AFD provisioning. The app still talks to
   KV/Search/Foundry over their PEs once the env is vNet-integrated —
   see option 2 for that part.
2. **Internal env + vNet integration.** Partner enlarges
   `workloadSubnetPrefix` to `/23`, sets `externalIngress: false`, and
   adds `vnetConfiguration` + a PE on the managed env. The
   `/configure-landing-zone` custom agent walks through subnet enlargement;
   the PE + DNS link are authored by hand.

## What the overlay still does NOT do

- Route table forcing egress through the hub firewall (customer's FW
  private IP is CCoE-owned; add a `Microsoft.Network/routeTables`
  resource with a 0.0.0.0/0 UDR and associate via the subnet's
  `routeTable` property once you have that IP).
- Diagnostic settings binding workload resources to the hub LAW
  (Tier 3 maximal — not scoped here; workload resources emit to the
  local LAW created by `infra/modules/monitor.bicep`).
- ALZ policy assignments (inherited from the MG; customer-owned).

## Deploy sequence

```bash
# Step 1 — subscription-scope overlay (one-time per spoke)
az deployment sub create \
  --location <region> \
  --template-file infra/alz-overlay/main.bicep \
  --parameters infra/alz-overlay/main.parameters.json

# Step 2 — wire overlay outputs into the workload deploy
azd env set AZURE_PE_SUBNET_ID                       "<workloadSubnetId output>"
azd env set AZURE_PRIVATE_DNS_ZONE_KEYVAULT          "<keyvault zone id>"
azd env set AZURE_PRIVATE_DNS_ZONE_SEARCH            "<search zone id>"
# Foundry PE needs all three AIServices zones:
azd env set AZURE_PRIVATE_DNS_ZONE_COGNITIVESERVICES "<cognitiveservices zone id>"
azd env set AZURE_PRIVATE_DNS_ZONE_OPENAI            "<openai zone id>"
azd env set AZURE_PRIVATE_DNS_ZONE_SERVICESAI        "<services.ai zone id>"

# Step 3 — workload deploy
azd up   # uses infra/main.parameters.alz.json
```

## Consistency with the rest of the repo

The `landing_zone_mode_consistent` lint rule asserts that when
`accelerator.yaml.landing_zone.mode == 'alz-integrated'`:
- `infra/alz-overlay/main.bicep` exists and has no `CHANGEME`
  placeholders in `main.parameters.json`.
- `infra/alz-overlay/network.bicep` creates an NSG and associates it
  with the workload subnet.
- `infra/main.parameters.alz.json` exists and sets
  `enablePrivateLink: true` and `externalIngress: false`.
- Workload modules (`key-vault.bicep`, `container-app.bicep`) accept
  the `publicNetworkAccess` / `externalIngress` parameter rather than
  hardcoding `Enabled` / `true`.
- Workload modules (`key-vault.bicep`, `ai-search.bicep`) accept
  `peSubnetId` and `privateDnsZoneId` params; `foundry.bicep` accepts
  `peSubnetId` and the plural `privateDnsZoneIds` array (the AIServices
  PE registers into three hub zones). `infra/main.bicep` threads the
  overlay outputs into the PE resources.

Fix lint findings by completing the custom agent walkthrough.
