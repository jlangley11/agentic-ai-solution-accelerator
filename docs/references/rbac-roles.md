# RBAC role inventory

Every Azure RBAC role assignment created by `infra/main.bicep` and its
modules. Use this as the answer to "what permissions does the
accelerator grant, and why?" — common ask from customer security
review boards.

The inventory is grouped by **principal** (which identity holds the
role). Each row has:

* **Role** — Azure built-in role definition
* **Scope** — what the role applies to
* **Why** — what would break if the assignment were removed
* **Source** — `infra/<file>:<line>` anchor

---

## Workload managed identity

User-assigned identity created by `infra/modules/identity.bicep` and
attached to the Container App as the workload identity. This is the
identity the FastAPI process authenticates as via
`DefaultAzureCredential`.

| Role                                      | Scope            | Why                                                                                                 | Source                          |
|-------------------------------------------|------------------|-----------------------------------------------------------------------------------------------------|---------------------------------|
| `AcrPull`                                 | Container Registry | Container App pulls the workload image at startup.                                                  | `infra/modules/acr.bicep:35`    |
| `Key Vault Secrets User`                  | Key Vault        | App resolves secrets at runtime via Key Vault references in the Container App env.                  | `infra/modules/key-vault.bicep:38` |
| `Search Index Data Contributor`           | AI Search        | FoundryIQ bootstrap creates / refreshes the knowledge-base index documents.                         | `infra/modules/ai-search.bicep:46` |
| `Search Service Contributor`              | AI Search        | Bootstrap creates the index + knowledge base + data source on first start.                          | `infra/modules/ai-search.bicep:56` |
| `Cognitive Services OpenAI User`          | Foundry account  | Workflow calls model deployments (chat + embeddings) with AAD auth.                                 | `infra/modules/foundry.bicep:224` |
| `Cognitive Services User`                 | Foundry account  | Account-level read used by the SDK for capability discovery.                                        | `infra/modules/foundry.bicep:234` |
| `Azure AI Developer`                      | Foundry project  | Workflow operates on the project (agents, threads, runs, connections) at runtime.                   | `infra/modules/foundry.bicep:244` |
| `Role Based Access Control Administrator` (ABAC-constrained) | AI Search | Bootstrap grants each Foundry agent's runtime principal access to Search at first start. **Constrained** to assigning ONLY `Search Index Data Reader/Contributor` and `Search Service Contributor`, and only to ServicePrincipal targets. | `infra/main.bicep:370` |

The ABAC condition is the lowest-privilege RBAC-Admin shape ARM
supports — the workload MI cannot grant itself or any other identity
arbitrary roles. See the comment on `infra/main.bicep:357` for the
full condition expression.

## Foundry project managed identity

System-assigned identity on the Foundry project. Created by Azure when
the project resource is provisioned.

| Role                          | Scope     | Why                                                                                  | Source                          |
|-------------------------------|-----------|--------------------------------------------------------------------------------------|---------------------------------|
| `Search Index Data Reader`    | AI Search | Project's built-in retrieval connection reads from the FoundryIQ knowledge base.     | `infra/main.bicep:284`          |

## AI Search managed identity

System-assigned identity on the AI Search service.

| Role                              | Scope           | Why                                                                                      | Source                          |
|-----------------------------------|-----------------|------------------------------------------------------------------------------------------|---------------------------------|
| `Cognitive Services OpenAI User` | Foundry account | AAD vectorizer in the index calls the embedding deployment without keys.                  | `infra/main.bicep:300`          |

---

## Removing or auditing assignments

* **`az role assignment list --all -o table`** at the resource group scope
  shows the deployed assignments. Cross-reference rows against this table.
* **Removing an assignment** breaks the runtime path noted in *Why*. If a
  customer security policy mandates removal, replace with a different
  identity model (e.g., system-assigned MI on the Container App) — do not
  simply delete the role.
* **Drift detection.** `azd provision` re-applies every assignment from
  Bicep, so portal-side removals revert on the next deploy. Track drift
  via Azure Policy `Audit role assignment` initiatives.

## When this inventory drifts from code

Any new `Microsoft.Authorization/roleAssignments@2022-04-01` resource in
`infra/` should add a row here. Grep:

```bash
rg -n "roleAssignments@" infra/
```

…and reconcile against this file before the PR merges.

## Cross-references

* Identity wiring: [`customer-runbook.md` Section 8](../customer-runbook.md#8-secret-rotation) (Managed Identity)
* ALZ-integrated overlays: `infra/alz-overlay/README.md` in the repo
* Security review checklist: [`security-review-checklist.md`](security-review-checklist.md)
