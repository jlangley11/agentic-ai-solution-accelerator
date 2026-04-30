# Security review checklist

A pre-`azd up` checklist for the partner to walk through with the
customer's security / CCoE team. Every item links to where the control
is enforced — Bicep file, lint rule, `accelerator.yaml` field, or
runbook section.

The accelerator's defaults satisfy these for **standalone** and **AVM**
landing-zone tiers without changes. The `alz-integrated` tier (Tier 3)
adds private endpoints + DNS + hub peering — see
`infra/alz-overlay/README.md` in the repo and
[the landing-zone pattern](../patterns/azure-ai-landing-zone/README.md).

!!! tip "When to use"
    Run this with the customer security lead **before** committing to a
    deployment date. Most items are pre-satisfied; a handful (rotation
    cadence, breakglass, allowed locations) are customer-specific
    decisions you record in the [handover packet](../handover/handover-packet-template.md).

---

## Identity

- [ ] **Workload uses managed identity, not keys or service principals.**
      Enforced by the user-assigned identity in
      `infra/modules/identity.bicep` + role assignments in
      `infra/main.bicep`. See [RBAC roles](rbac-roles.md).
- [ ] **`DefaultAzureCredential` is the only auth path in code.**
      `accelerator-lint.py` rule `no_direct_openai_client` blocks
      `openai.OpenAI()` / `AzureOpenAI()` instantiation.
- [ ] **Workload MI's RBAC-Admin grant is ABAC-constrained.**
      `infra/main.bicep:370` — the workload can only assign Search-data
      roles to ServicePrincipal targets; cannot escalate itself.
- [ ] **Breakglass identity** for emergency tenant access is documented
      out-of-band (customer's standard process, not the accelerator's).

## Secrets

- [ ] **Key Vault is the only persistence for secrets.**
      `controls.key_vault: true` in `accelerator.yaml`. Bicep deploys
      the vault with RBAC auth and Key Vault Secrets User role to the
      workload MI (`infra/modules/key-vault.bicep:38`).
- [ ] **Container App env vars use Key Vault references** for any
      secret value. See `infra/modules/container-app.bicep`.
- [ ] **Soft-delete + purge protection enabled.**
      Defaults applied by `infra/modules/key-vault.bicep`. Required
      because `azd down --purge` does not hard-delete the vault — see
      [customer-runbook → Re-provisioning and rollback](../customer-runbook.md#11-re-provisioning-and-rollback)
      and the [`/teardown`](../../.github/agents/teardown.agent.md) agent.
- [ ] **Rotation cadence agreed with CCoE** (federated cred, HITL
      endpoint URL if non-rotating). Recorded in handover packet.

## Network

- [ ] **Private endpoints required for regulated workloads.**
      `accelerator.yaml.controls.private_endpoints: required` flips
      the deployment to Tier 2 (AVM) or Tier 3 (ALZ-integrated). Lint
      rule `landing_zone_mode_consistent` blocks mismatch.
- [ ] **Public network access on Foundry / Search / Key Vault is
      Disabled** when `enablePrivateLink: true`. See
      `infra/main.parameters.alz.json`.
- [ ] **Container App ingress is internal-only** for Tier 3
      (`externalIngress: false`).
- [ ] **NSG denies inbound from Internet** on the workload subnet
      (Tier 3 — `infra/alz-overlay/main.bicep`).
- [ ] **Allowed locations** match customer ALZ policy initiative.
      Verify with `scripts/validate-alz.py` (Tier 3) or the
      `--region` arg of `scripts/preflight-deploy.py`.

## Content filters & Responsible AI

- [ ] **Content filter policy is IaC-attached, not portal-edited.**
      `accelerator.yaml.controls.content_filters: iac`. Deployed by
      `infra/modules/foundry.bicep`; portal drift overwritten by the
      next `azd provision`.
- [ ] **XPIA + jailbreak baseline evals pass.**
      `evals/redteam/run.py` covers 10 baseline cases across 3
      technique families. See `evals/redteam/README.md` in the repo.
- [ ] **PII handling is documented** in the [solution brief](../discovery/solution-brief.md).
      RAI risks mapped to eval cases per
      [`patterns/rai/README.md`](../patterns/rai/README.md).
- [ ] **HITL gates every side-effect tool.** Verified by
      `accelerator-lint.py` rule `tools_must_use_hitl`. Policy
      declared in `accelerator.yaml.solution.hitl`.

## Observability

- [ ] **Application Insights wired via `azure-monitor-opentelemetry`**
      on FastAPI startup (`src/main.py`).
- [ ] **ROI workbook auto-deployed** by Bicep
      (`infra/modules/monitor.bicep`). See
      [customer-runbook §2](../customer-runbook.md#2-monitoring).
- [ ] **`tool.hitl_misconfigured` alert wired** in customer's Azure
      Monitor — fires if production ever runs without an HITL approver.
- [ ] **Diagnostic settings** route Container App + Foundry + Search +
      Key Vault logs to the customer Log Analytics workspace.
- [ ] **30-day retention minimum** on the Log Analytics workspace
      (default in `infra/modules/monitor.bicep`).

## Decommission

- [ ] **Teardown plan written** before deploy. The
      [`/teardown`](../../.github/agents/teardown.agent.md) agent walks the 5-step
      decommission flow including the post-`azd down --purge`
      soft-delete sweep that is otherwise easy to miss.
- [ ] **Customer data export** (Search index, KV secrets, telemetry)
      cadence agreed. See `scripts/teardown-preflight.py`.
- [ ] **GitHub Environment cleanup** (federated creds + repo vars) is
      part of the decommission runbook.

---

## How to use this checklist with the customer

1. Walk through each section in order with the customer's security
   reviewer.
2. For items pre-satisfied by the accelerator: confirm the enforcement
   pointer is acceptable to the customer's policy.
3. For items requiring customer input (rotation cadence, allowed
   locations, breakglass): record the agreed value in the
   [handover packet](../handover/handover-packet-template.md).
4. Close the review by running `python scripts/preflight-deploy.py
   --region <chosen-region>` and (if Tier 3) `python
   scripts/validate-alz.py` so any quota / permission / placeholder
   issues surface before `azd up`.
