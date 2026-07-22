---
name: deploy-to-env
description: Wires up a new Azure environment (partner dev, staging, or customer-scoped subscription) so `deploy.yml` can target it without a repo fork. Covers the manifest entry, GitHub Environment, OIDC federated credential, and first dispatch run.
tools: ['codebase', 'editFiles', 'search', 'runCommands']
---

# /deploy-to-env — add a BYO-Azure environment to this template

> Compatibility adapter: environment registration remains guided here; use
> `accel environment list` and `accel deploy --dry-run` for authoritative
> deployment state and approval boundaries.

Use this when deploying the accelerator to a **new Azure environment** — a partner staging subscription, a specific customer's subscription, or a regional clone — **without forking the repo**. Everything routes through `deploy/environments.yaml` plus GitHub Environments; no `deploy.yml` edits needed for routine new envs.

## When NOT to use this
- Routine infra tweaks to an existing env → edit `infra/*.bicep`, then use the
  target-aware `accel deploy` preview/apply flow.
- Cross-tenant customer deploys via Azure Lighthouse / ARM delegation → out of scope for this custom agent; a separate bootstrap.
- Forking the repo for a customer who wants the source code → also out of scope.

## Inputs to gather
1. **Env name** (lowercase, `[a-z][a-z0-9-]{1,30}`, e.g. `staging`, `customera-prod`, `emea-dev`).
2. **Azure region** (e.g. `eastus2`, `westeurope`) — will be the GitHub `vars.AZURE_LOCATION` for the new env.
3. **Target Azure subscription id + tenant id** — will be the new env's `secrets.AZURE_SUBSCRIPTION_ID` and `secrets.AZURE_TENANT_ID`.
4. **Entra app (client) id** for OIDC — either the existing CI app or a new per-env one.
5. **Deployment target** — `selfhost` (root Container Apps default) or the explicit
   preview-only `hosted-preview` nested workspace.
6. **Short description** — one line; appears in the manifest and in workflow dispatch logs.

## Step 1 — Add the manifest entry

Edit `deploy/environments.yaml` and add an entry under `environments[]`:
```yaml
environments:
  - name: dev
    github_environment: dev
    deployment_target: selfhost
    description: Default partner sandbox — deployed automatically on push to main.
  - name: <env-name>            # e.g., uat, prod
    github_environment: <env-name>
    deployment_target: selfhost # or hosted-preview, never for default_env
    description: <one-line purpose>
```

Conventions:
- `name` — the azd env name. **Derived from the manifest** by `deploy.yml`; do NOT set `vars.AZURE_ENV_NAME`.
- `github_environment` — the GitHub Environment name (repo Settings → Environments). Usually identical to `name`; use a different value only if organizational naming forces it.
- `deployment_target` — optional for legacy entries and defaults to `selfhost`.
  Allowed values are `selfhost` and `hosted-preview`.
- Do NOT change `default_env` unless you actually want push-to-main to start deploying to this new env instead of `dev`.
- `default_env` must remain a `selfhost` entry. Hosted Agents are preview-only
  and require explicit selection and acknowledgment.

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

The deployment creates role assignments. The OIDC identity must also have
**Role Based Access Control Administrator** (or **User Access Administrator** /
Owner) at the deployment scope. Hosted preview in particular creates
cross-resource Search/Foundry assignments and a constrained RBAC-admin
assignment used by the deploy-time provisioner; Contributor alone is not
sufficient.

## Step 4 — Add scoped secrets + variables to the new GitHub Environment

On the new Environment's page:

**Secrets:**
- `AZURE_CLIENT_ID` — the Entra app's client id.
- `AZURE_TENANT_ID` — the Entra tenant id.
- `AZURE_SUBSCRIPTION_ID` — the target subscription id.

**Variables:**
- `AZURE_LOCATION` — the Azure region.
- `AZURE_PRINCIPAL_ID` — object id of the OIDC service principal (not its
  client/application id); required by the hosted-preview Bicep role assignments.

Do NOT set `AZURE_ENV_NAME` — `deploy.yml` derives it from `deploy/environments.yaml`.

## Step 5 — First deploy

Repo → **Actions → deploy → Run workflow** → pick `main` → enter your env name in the `env_name` input → **Run workflow**. The `resolve-env` job validates your name and target against the manifest.

- `selfhost` runs the unchanged root `azd-up` job, followed by full quality and
  red-team evals.
- `hosted-preview` requires explicit preview approval, runs
  `scripts/preflight-deploy.py --deployment-target hosted-preview
  --acknowledge-preview`, then executes `azd env`, `azd provision`, `azd deploy`,
  endpoint discovery, and a fresh-session Responses smoke with
  `working-directory: deploy/hosted-preview`. Full hosted eval parity is
  deferred to Phase 5. The workflow persists
  `AZURE_PRINCIPAL_TYPE=ServicePrincipal` before provisioning because GitHub
  OIDC authenticates as an application. The nested parameters file retains
  `${AZURE_PRINCIPAL_TYPE=User}` for local interactive deployments.

For an operator-run hosted deployment, select the nested workspace by changing
directory; do not use `azd -C`:

```bash
python scripts/preflight-deploy.py --region <region> \
  --deployment-target hosted-preview --acknowledge-preview
cd deploy/hosted-preview
azd env select <env-name>
azd env set AZURE_PRINCIPAL_ID "$(az ad signed-in-user show --query id -o tsv)"
azd env set AZURE_PRINCIPAL_TYPE User
azd provision
azd deploy
```

If `resolve-env` reports an unknown environment, Step 1 was not saved or the
name was mistyped. If deployment fails authentication, Step 3 or 4 is not
wired. For quota failures, change the declared region or request quota.

## Guardrails
- Never hand-edit `deploy.yml` to add envs. The manifest + resolve-env pattern is the contract.
- Never make `hosted-preview` the default environment or deploy it without the
  explicit preview acknowledgment.
- Never use `azd -C` for the nested preview workspace; `cd
  deploy/hosted-preview` (or Actions `working-directory`) is the verified path.
- Never commit secrets. Never set `AZURE_ENV_NAME` in any GitHub variable/secret — the manifest is the single source of truth.
- If the customer needs deploys from *their* repo (not this one), that's a separate bootstrap (out of scope).
- The default-env-on-push behavior applies only to `default_env` in the manifest. If `default_env` is flipped to a prod-like env, confirm the engagement actually wants merges to main to auto-deploy there.
