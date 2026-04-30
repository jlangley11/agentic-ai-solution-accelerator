# ADR-0006 · ABAC-constrained RBAC-Admin for runtime per-agent grants

**Status:** Accepted

## Context

Foundry creates a fresh **runtime principal** (`instance_identity.principal_id`)
for each agent version when the version is created. That principal
is not knowable at deploy time — it doesn't exist until Foundry
provisions the agent. But the agent needs read access to AI Search
to use the FoundryIQ knowledge base.

The choices:

1. **Pre-grant a wildcard.** Give Foundry's account principal
   `Search Index Data Reader` ahead of time. Works, but the grant is
   broader than any single agent needs and survives agent deletion.
2. **Grant from the deploy pipeline.** Have CI run
   `az role assignment create` after `azd up` finishes. Works, but
   makes CI long-lived-credential-dependent and fragile across
   re-deploys.
3. **Bootstrap-time grant from the workload itself.** The FastAPI
   workload, running as the user-assigned MI, grants the agent's
   runtime principal read access on first start. This requires the
   workload MI to hold `Role Based Access Control Administrator`
   on Search — which by default lets it grant *any* role to *any*
   principal. That is too much.

## Decision

Use option **3 with an ABAC condition** that constrains the
grant. The workload MI holds `Role Based Access Control Administrator`
on the Search service, but the role assignment carries an ABAC
condition (`infra/main.bicep:369`) that:

* Limits writes to assigning ONLY three role definition GUIDs:
  `Search Index Data Reader`, `Search Index Data Contributor`,
  `Search Service Contributor`.
* Limits the principal type to `ServicePrincipal` only.
* Mirrors the same restrictions on delete.

This is the lowest-privilege RBAC-Admin shape ARM supports for the
delegated-grant pattern. The workload MI cannot escalate itself or
grant any role to a user account.

`src/bootstrap.py::_grant_agent_search_access` is the consumer.

## Consequences

**Positive**

* Per-agent-version grants happen automatically on first start.
* Lifetime is bounded by the Search service — `azd down` removes
  every grant the workload ever made.
* Audit trail: every assignment carries the workload MI as
  `createdBy`, so security review can attribute the grant.

**Negative**

* The ABAC condition is dense and easy to break in a refactor. The
  comment block in `main.bicep:357–369` explains every clause; the
  RBAC inventory ([`docs/references/rbac-roles.md`](../references/rbac-roles.md))
  highlights this row specifically.
* Customers whose policy *forbids* RBAC-Admin on workload identities
  (even when ABAC-constrained) must run option 2 instead — out of
  scope for the flagship.

**How to deviate**

Replace `workloadAssignsSearchRoles` in `infra/main.bicep` with a
deploy-time grant from CI or remove it and pre-grant Foundry's
account principal directly. Both lose the per-agent attribution.

## References

* `infra/main.bicep` lines 357–385 — ABAC condition + assignment
* `src/bootstrap.py` — `_grant_agent_search_access`
* [`docs/references/rbac-roles.md`](../references/rbac-roles.md) — Workload MI table
* [Azure RBAC ABAC syntax](https://learn.microsoft.com/azure/role-based-access-control/conditions-format)
