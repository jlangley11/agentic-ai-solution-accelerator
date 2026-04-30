---
name: deploy-to-env
description: Wires up a new Azure environment (partner dev, staging, or customer-scoped subscription) so `deploy.yml` can target it without a repo fork. Covers the manifest entry, GitHub Environment, OIDC federated credential, and first dispatch run.
tools: ['codebase', 'editFiles', 'search', 'runCommands']
---

# /deploy-to-env — add a BYO-Azure environment to this template

Use this when deploying the accelerator to a **new Azure environment** — a partner staging subscription, a specific customer's subscription, or a regional clone — **without forking the repo**. Everything routes through `deploy/environments.yaml` plus GitHub Environments; no `deploy.yml` edits needed for routine new envs.

## When NOT to use this
- Routine infra tweaks to an existing env → edit `infra/*.bicep` and re-run `azd up -e <existing-env>`.
- Cross-tenant customer deploys via Azure Lighthouse / ARM delegation → out of scope for this custom agent; a separate bootstrap.
- Forking the repo for a customer who wants the source code → also out of scope.

## Inputs to gather
1. **Env name** (lowercase, `[a-z][a-z0-9-]{1,30}`, e.g. `staging`, `customera-prod`, `emea-dev`).
2. **Azure region** (e.g. `eastus2`, `westeurope`) — will be the GitHub `vars.AZURE_LOCATION` for the new env.
3. **Target Azure subscription id + tenant id** — will be the new env's `secrets.AZURE_SUBSCRIPTION_ID` and `secrets.AZURE_TENANT_ID`.
4. **Entra app (client) id** for OIDC — either the existing CI app or a new per-env one.
5. **Short description** — one line; appears in the manifest and in workflow dispatch logs.

## Step 1 — Add the manifest entry

Edit `deploy/environments.yaml` and add an entry under `environments[]`:
```yaml
environments:
  - name: dev
    github_environment: dev
    description: Default partner sandbox — deployed automatically on push to main.
  - name: <env-name>            # e.g., uat, prod
    github_environment: <env-name>
    description: <one-line purpose>
```

Conventions:
- `name` — the azd env name. **Derived from the manifest** by `deploy.yml`; do NOT set `vars.AZURE_ENV_NAME`.
- `github_environment` — the GitHub Environment name (repo Settings → Environments). Usually identical to `name`; use a different value only if organizational naming forces it.
- Do NOT change `default_env` unless you actually want push-to-main to start deploying to this new env instead of `dev`.

Run `python scripts/accelerator-lint.py` after saving. The `deploy_matrix_matches_azure_envs` rule must stay at 0 findings.

## Step 2 — Create the GitHub Environment

Repo → **Settings → Environments → New environment** → name it exactly `<github_environment>` from the manifest. Optionally add protection rules (required reviewers, wait timer, branch restrictions) — recommended for prod-like envs.

## Step 3 — Configure the OIDC federated credential

Grant the Entra app the ability to get tokens for this GitHub Environment. Run once per env (replace bracketed values):

```bash
az ad app federated-credential create \
  --id <entra-app-object-id> \
  --parameters '{
    "name": "github-<repo-name>-<env-name>",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<org>/<repo>:environment:<github_environment>",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

Then, in the subscription that will host this environment's resources:
```bash
az role assignment create \
  --assignee <entra-app-client-id> \
  --role Contributor \
  --scope /subscriptions/<subscription-id>
```
(Scope down to a resource group if the env has its own RG.)

## Step 4 — Add scoped secrets + variables to the new GitHub Environment

On the new Environment's page:

**Secrets:**
- `AZURE_CLIENT_ID` — the Entra app's client id.
- `AZURE_TENANT_ID` — the Entra tenant id.
- `AZURE_SUBSCRIPTION_ID` — the target subscription id.

**Variables:**
- `AZURE_LOCATION` — the Azure region.

Do NOT set `AZURE_ENV_NAME` — `deploy.yml` derives it from `deploy/environments.yaml`.

## Step 5 — First deploy

Repo → **Actions → deploy → Run workflow** → pick `main` → enter your env name in the `env_name` input → **Run workflow**. The `resolve-env` job validates your name against the manifest, the `azd-up` job binds to the new GitHub Environment and picks up the scoped OIDC identity, and the evals job runs post-deploy regression against the fresh endpoint.

If `resolve-env` fails with "environment '<name>' not found", Step 1 wasn't saved or the name was typo'd. If `azd-up` fails auth, Step 3 or 4 isn't wired. If `azd up` fails with quota errors, switch region in Step 4 or pre-request quota.

## Guardrails
- Never hand-edit `deploy.yml` to add envs. The manifest + resolve-env pattern is the contract.
- Never commit secrets. Never set `AZURE_ENV_NAME` in any GitHub variable/secret — the manifest is the single source of truth.
- If the customer needs deploys from *their* repo (not this one), that's a separate bootstrap (out of scope).
- The default-env-on-push behavior applies only to `default_env` in the manifest. If `default_env` is flipped to a prod-like env, confirm the engagement actually wants merges to main to auto-deploy there.
