---
name: teardown
description: Decommission an Azure environment safely. Walks the partner through a pre-teardown checklist (KPI/cost export, customer signoff, HITL approver disable), surfaces the destructive `azd down --purge` command without auto-running it, then runs a soft-delete sweep for Cognitive Services accounts and Key Vaults that survive teardown and block re-creation in the same name+region.
tools: ['codebase', 'editFiles', 'search', 'runCommands']
---

# /teardown — decommission an environment

Use this when winding down an engagement, retiring a partner staging
sub, or recovering from a corrupted environment. The work is destructive
and irreversible; this custom agent enforces the safety contract.

## When NOT to use this
- **Routine code rollback** → `git revert` + `azd deploy`. Don't tear down to roll back code.
- **Recovering from a single failed bootstrap** → restart the Container App revision instead. Teardown is a much heavier hammer.
- **Recovering a deleted resource within retention** → `az cognitiveservices account recover` / `az keyvault recover` are the right tools, not this agent.

## Inputs to gather
1. **Env name** — the `azd` environment being destroyed; must match an entry in `deploy/environments.yaml`.
2. **Deployment target** — `selfhost` or `hosted-preview`, matching the manifest entry.
3. **Confirmation that the customer signed off on destruction** — this is the contract that gates the destructive step.
4. **Where the partner has archived the engagement deliverables** (KPI exports, cost report, eval results, handover packet). The script's checklist asks about each.

## Step 1 — Pre-teardown checklist

Run the read-only preflight that walks 6 acknowledgments:

```bash
python scripts/teardown-preflight.py --env <env-name>
```

For Hosted Agents preview, retain the explicit target:

```bash
python scripts/teardown-preflight.py --env <env-name> \
  --deployment-target hosted-preview
```

The script asks `[y/N]` for each of:
- KPI export from App Insights (last 30 days)
- Final cost report from Cost Management
- Customer data extraction from AI Search / Storage / Foundry threads
- HITL approver (Logic App / webhook) disabled or rerouted
- Written customer signoff that the env may be destroyed
- Final eval `results.jsonl` archived for the engagement post-mortem

**If any item is declined**, the script exits non-zero and lists what's
outstanding. Do not proceed to step 2 until all are acknowledged.

## Step 2 — The destructive step (operator runs it)

The agent does NOT run this. The partner runs it themselves after the
checklist passes:

The operator identity needs Contributor plus **Role Based Access Control
Administrator** (or User Access Administrator / Owner) at the deployment
scope so `azd down` can remove the role assignments created by either target.
Contributor alone can delete resources but cannot reliably delete their RBAC
assignments.

```bash
azd down -e <env-name> --purge --force
```

For hosted preview the operator must enter the nested workspace; do not use
`azd -C`:

```bash
cd deploy/hosted-preview
azd down -e <env-name> --purge --force
```

`azd down --purge` tears down every resource in the environment. It
takes 5–10 minutes. If it fails partway, re-run it; it is idempotent.

## Step 3 — Soft-delete sweep

`azd down --purge` does NOT hard-delete every resource type:

- **Cognitive Services accounts** go to soft-delete (default 7 days).
- **Key Vaults** go to soft-delete (default 7–90 days depending on tenant policy).

The hosted-preview workspace does not provision a Key Vault, so Cognitive
Services is the primary hosted sweep. The script still checks Key Vault as a
defensive measure for same-named resources created outside that workspace.

Both block re-creation of a resource with the same name+region during
their retention window. If you tear down `customera-dev` and try to
re-deploy it with the same env name in the same region, `azd up` will
fail with a name collision error.

Run the sweep:

```bash
python scripts/teardown-preflight.py --env <env-name> --post-teardown
```

For hosted preview, append `--deployment-target hosted-preview`. The script
loads the expected hashed Foundry/Cognitive Services account name from
`deploy/hosted-preview/.azure/<env-name>/.env` using
`AZURE_AI_FOUNDRY_ACCOUNT_NAME` or `AZURE_AI_ACCOUNT_NAME`. If that file is no
longer available, provide the exact name explicitly:

```bash
python scripts/teardown-preflight.py --env <env-name> --post-teardown \
  --deployment-target hosted-preview \
  --cognitive-account-name <exact-account-name>
```

For selfhost, the same lookup uses the root `.azure/<env-name>/.env`.

The sweep:
- Matches the exact expected Cognitive Services account name, including hashed
  hosted names
- Uses env-name substring matching only when no exact account name is available
  for a legacy selfhost environment
- Lists soft-deleted Key Vaults whose name contains the env name
- Prints the exact `az ... purge` command for each — but does NOT run them

The partner runs the printed `az ... purge` commands manually after
confirming with the customer that no recovery is needed.

## Step 4 — Verify the resource group is gone

```bash
az group show -n rg-<env-name> 2>/dev/null && echo "STILL EXISTS" || echo "gone"
```

If the RG is still listed, look for resources that `azd down` couldn't
delete (locks, soft-deleted parents, or partner extensions) and remove
them manually before retrying.

## Step 5 — Decommission the GitHub Environment (optional)

If this env will not be re-used, remove its corresponding GitHub
Environment so OIDC creds are revoked:

1. Go to **GitHub → Settings → Environments → \<env-name\>**.
2. Click **Delete environment**.
3. Remove the corresponding entry from `deploy/environments.yaml` and
   commit. The `deploy_matrix_matches_azure_envs` lint rule blocks any
   drift between the manifest and the GitHub UI.

## Done when

- Pre-teardown checklist passed (all 6 items acknowledged).
- `azd down --purge` exited cleanly.
- Soft-delete sweep returned no env-matching resources (or you've run
  the printed `az ... purge` commands for each).
- Resource group `rg-<env-name>` no longer exists.
- (Optional) GitHub Environment deleted; manifest entry removed.

After completion, the engagement is decommissioned. Restoring it
requires a fresh `azd up` with a new env name, OR (if within retention)
recovering the soft-deleted resources via `az ... recover` BEFORE the
retention window expires.
