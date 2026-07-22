# Setup & prereqs

> **Walkthrough version:** [*Get ready → 2. Set up your machine*](../start/ready/02-set-up-your-machine.md) covers the same setup with the linear-flow framing. This page remains the **authoritative deep reference** for prereqs, secrets, and troubleshooting — bookmark it.

**One-time** workstation + subscription readiness. Run this once per partner
machine and once per Azure subscription. Executable CLI help and environment
manifests win on command/target details; this page is the deep explanation.

## Where you'll work

This document is the authoritative reference for prereqs, secrets, and troubleshooting — most of it is something you'll *configure* (Terminal for CLI installs, GitHub web for environment secrets, Azure portal for quota). The QUICKSTART and hands-on-lab carry the same orientation table for the partner motion itself.

| Where | What you do here |
|---|---|
| **Terminal / coding-agent CLI** | Run `accel next`, inspect previews, and execute approved operations. Use VS Code, Copilot CLI, Codex, or Claude Code for authoring and diff review. |
| **GitHub web (github.com)** | Repo → Settings → Environments → wire `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` and `AZURE_LOCATION` per environment; Settings → Secrets and variables → Actions for repo-level vars |
| **Azure portal (portal.azure.com)** | Confirm Foundry quota in the target region before deployment; inspect the resulting resources |

## What you ship

A partner clone of this template deploys a working agentic AI solution into the
customer's Azure through target-aware `accel deploy`. The flagship scenario (Sales
Research & Personalized Outreach) is runnable out of the box; swap it for your
own scenario with `accel design` and `accel scaffold --scenario-id <id>`.

## Prerequisites

You will need:

| Tool | Why |
|------|-----|
| Azure subscription (Contributor) | The approved deployment creates resources here |
| Azure CLI `>= 2.55` | fallback for targeted `az` calls |
| Azure Developer CLI (`azd`) `>= 1.10` | one-shot provision + deploy |
| GitHub CLI (`gh`) `>= 2.50` | repo bootstrap + secrets |
| Git | template clone + branch work |
| Python 3.11+ | Required for the preferred `accel` lifecycle, local tests, and authoring tools |
| PowerShell 7 *(Windows only)* | required because some `azd` lifecycle hooks (e.g. `postdeploy`) run with `pwsh` |
| Docker or Podman *(optional)* | only needed for local container builds; `azd up` uses ACR remote build by default |

> **Direct self-host `azd up` does not require the lifecycle CLI.** The preferred guided
> experience does require Python because `accel` owns lifecycle state,
> previews, evidence intake, evaluation, UAT, and handover. Direct `azd`
> remains a recovery/minimal deployment path.

Model quota: the accelerator deploys a `GlobalStandard` Azure OpenAI model
(default `gpt-5-mini`, 30k TPM — overrideable through the `accelerator.yaml`
`models:` block; see [Customizing models per agent](#customizing-models-per-agent)
below). Confirm quota in your target region before deployment.

### Install the guided CLI and development tools

- **Any CPython 3.11+** that resolves on `PATH` as `python` (Windows) or `python3` (macOS/Linux). python.org installers, winget, your distro's package manager, scoop, and **activated Conda environments** all work. Tested on **3.11–3.13**.
- The Microsoft Store Python alias (`%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`) is **not** a real interpreter — install one of the above instead, or activate a Conda env.
- Install the dev extras: `pip install -e ".[dev]"` from the repo root.
- Confirm the entry point: `accel --help`, then run `accel next`.
- Optional integrations:
  - `pip install -e ".[evals]"` for Foundry-native relevance/groundedness.
  - `pip install -e ".[mcp]"` for the `accel-mcp` stdio server.

Reference workbench checks:

```powershell
Set-Location patterns\sales-research-frontend
npm install
npm test
npm run typecheck
npm run build
npm audit
```

## Required GitHub secrets and variables

> **Lab vs. production motion.** Everything from this section through "Private
> network access" is for the production/customer motion. The sandbox lab uses
> the declared `dev` environment through `accel deploy` with local `azd`
> authentication and runs evals against that endpoint.

Every secret / variable referenced in `.github/workflows/*.yml` is listed
below. The accelerator lint (`scripts/accelerator-lint.py` →
`workflow_secrets_documented`) fails the build if a workflow references a name
that does not appear here.

This template supports **multi-environment BYO-Azure deploys**: `deploy/environments.yaml`
lists every Azure environment the pipeline can target, and each entry maps to a
**GitHub Environment** (repo → Settings → Environments) that holds its own scoped
OIDC credentials and region. Out of the box, the `dev` environment is registered.
Add more via the `/deploy-to-env` custom agent — never by hand-editing `deploy.yml`.

### Environment-scoped secrets (repo → Settings → Environments → `<env>` → Environment secrets)

Set these on **each** GitHub Environment you register (starting with `dev`). They are
read by `azd-up` inside `deploy.yml` after the `resolve-env` job picks which environment
to deploy to:

| Name | Purpose | Source |
|------|---------|--------|
| `AZURE_CLIENT_ID` | Federated-credentials client id used by `Azure/login@v2` | Entra app registration for CI |
| `AZURE_TENANT_ID` | Entra tenant id | Entra portal → Overview |
| `AZURE_SUBSCRIPTION_ID` | Subscription that hosts this environment's accelerator resources | `az account show` |

### Environment-scoped variables (repo → Settings → Environments → `<env>` → Environment variables)

| Name | Purpose | Example |
|------|---------|---------|
| `AZURE_LOCATION` | Azure region for this environment | `eastus2` |
| `AZURE_PRINCIPAL_ID` | Entra object id of the GitHub OIDC service principal; required by the `foundry-prompt` and `hosted-preview` workspaces for Foundry/Search RBAC | `az ad sp show --id <AZURE_CLIENT_ID> --query id -o tsv` |

Do **not** set `AZURE_ENV_NAME` anywhere. The azd environment name is derived from
`deploy/environments.yaml` (the `name:` field of the resolved entry). Setting it as
a variable would drift from the manifest; the `deploy_matrix_matches_azure_envs`
lint rule rejects that shape.

### Repo-level variables (repo → Settings → Secrets and variables → Actions → Variables)

| Name | Purpose | Example |
|------|---------|---------|
| `EVALS_API_URL` | API base URL used by the PR-triggered `evals` workflow (`.github/workflows/evals.yml`). Only required if you run evals standalone against an already-deployed environment. | `https://<ca-name>.<region>.azurecontainerapps.io` |

The `deploy.yml` workflow does NOT need `EVALS_API_URL` — it deploys the
resolved target first and passes the API URL via a job output
(`needs.azd-up.outputs.api_url`). Only configure `EVALS_API_URL` if you want
PR-time evals to run against an existing deployment rather than waiting for a
full deploy chain.

### Local `.env` (for development, not CI)

| Name | Purpose |
|------|---------|
| `AZURE_AI_FOUNDRY_ENDPOINT` | Foundry project endpoint (Bicep output) |
| `AZURE_AI_FOUNDRY_ACCOUNT_NAME` | Parent Cognitive Services account name (Bicep output) |
| `AZURE_AI_FOUNDRY_MODEL` | Default model deployment emitted by Bicep; per-agent overrides come from `accelerator.yaml` model slugs |
| `AZURE_SUBSCRIPTION_ID` | Subscription for management-plane pre-flight checks |
| `AZURE_RESOURCE_GROUP` | RG holding the Foundry account |
| `HITL_APPROVER_ENDPOINT` | Webhook URL for side-effect approvals (prod) |
| `HITL_DEV_MODE` | Set to `1` to auto-approve in dev — never in prod |
| `AZURE_AI_FOUNDRY_OPENAI_ENDPOINT` | Model endpoint used by optional Foundry evaluators |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Model deployment fallback for optional Foundry evaluators |

## Sandbox smoke-test (no customer involvement)

> **This path intentionally bypasses the discovery workshop** so a partner engineer can validate prereqs + infra shape end-to-end in their own subscription. For the full partner motion (discover → design + scaffold → provision → iterate → UAT → handover → measure) see [`docs/partner-playbook.md`](../partner-playbook.md). For a guided walkthrough of this same smoke-test with check-your-work gates, use [`docs/enablement/hands-on-lab.md`](../enablement/hands-on-lab.md) Lab 1.

```bash
# 1. Clone the template into your sandbox repo
# Replace <your-handle> with any short name (e.g., contoso → contoso-accel-sandbox)
gh repo create <your-handle>-accel-sandbox --template Azure-Samples/agentic-ai-solution-accelerator --private --clone
cd <your-handle>-accel-sandbox
code .

# 2. Authenticate to your SANDBOX subscription (not a customer subscription for the smoke-test)
az login --tenant <your-sandbox-tenant-id>
azd auth login

# 3. Register/select a declared environment, preview, and deploy
accel environment list
accel deploy --env dev --region <region> --dry-run
accel deploy --env dev --region <region> --execute
accel deploy --env dev --region <region> --execute --apply
```

The deployment returns the API URL. Hit `/healthz` to confirm the scenario loaded;
hit the scenario's endpoint (default `/research/stream`) with a sample payload
to run the flagship end-to-end.

Cleanup when done: `azd down --purge`.

## HITL setup

Every side-effect tool (CRM write, email send, ticket create) routes through
`src/accelerator_baseline/hitl.py`. Policies declared in
`accelerator.yaml -> solution.hitl` determine which actions block on approval.

Two modes:

- **Dev / demo** — set `HITL_DEV_MODE=1` in `.env` to auto-approve every
  checkpoint. Never ship this into a production env; the accelerator lint
  (`hitl_dev_mode_not_in_prod`) will block any infra template that bakes it in.
- **Prod / pilot** — set `HITL_APPROVER_ENDPOINT` to a webhook URL that the
  runtime `POST`s to when an action needs approval. The webhook is responsible
  for holding the checkpoint and returning an approve/reject decision. Simple
  shapes: a Slack/Teams bot, a Logic App, or a custom dashboard.

**Where you set these depends on the environment:**

| Where you're running | Where to set `HITL_*` |
|---|---|
| Local dev (running `uvicorn` or `python -m src.main` against your sandbox) | `.env` file in the repo root (loaded by `load_settings()`). `HITL_DEV_MODE=1` lives here only. |
| Sandbox self-host deploy from your machine | Set `HITL_APPROVER_ENDPOINT` in the selected azd environment so it is injected into the Container App. Never persist `HITL_DEV_MODE=1` in a deployed environment. |
| CI deploys (`deploy.yml` against a GitHub Environment) | github.com → repo → Settings → Environments → `<env>` → Environment secrets. Add `HITL_APPROVER_ENDPOINT` there; the workflow forwards it into `azd env set` before `azd up`. |

Failures to reach the approver are treated as rejections (fail-closed).

## Scenario customization

1. Run `accel next`; register source documents with `accel intake`.
2. Use `/discover-scenario` for the workshop interview and approved brief.
3. Run `accel design`, preview `accel scaffold`, then apply it. The CLI updates
   the `scenario:` manifest block transactionally—no YAML copying.
4. Use specialist agents for grounding, workers, tools, prompts, and evals.
5. Run `accel review` and `accel validate --full --execute` before PR.

## Customizing models per agent

The accelerator deploys a single `gpt-5-mini` model by default. To assign
different models per agent, edit `accelerator.yaml.models[]` and
`scenario.agents[].model`. The next target-aware deployment provisions models
under the shared content-filter policy and shared provisioning updates agents.

Full mechanics, YAML example, and lint behavior live in [`docs/patterns/architecture/README.md` → Customizing models per agent](../patterns/architecture/README.md#customizing-models-per-agent).

## CI chain

`.github/workflows/deploy.yml` resolves the selected entry from
`deploy/environments.yaml`, gates both deployment targets on policy lint, and:

- runs `azd up` plus acceptance for `selfhost`;
- runs nested Foundry provisioning/readback checks for `foundry-prompt`;
- runs nested `azd provision` + `azd deploy` plus a fresh-session protocol
  smoke for `hosted-preview`.

This chain is enforced by `deploy_gated_on_lint_and_evals` in the
accelerator lint.

The separate `.github/workflows/evals.yml` runs on every PR against the
already-deployed `EVALS_API_URL` (if configured). Use this for fast feedback
between full deployment cycles.

## Private network access

For regulated customers, set the Bicep param `enablePrivateLink=true` to disable public access on Foundry and AI Search. Provisioning the actual VNet, private endpoints, and private-DNS zones is **bring-your-own** at Tier 1 (standalone) — see the full procedure and the path to Tier 2 (AVM with PEs provisioned for you) in [`docs/patterns/azure-ai-landing-zone/README.md` → Tier 1 / Going private without leaving Tier 1](../patterns/azure-ai-landing-zone/README.md#tier-1--standalone-default).

## What the self-host target provisions

- Cognitive Services account (`kind=AIServices`, GA)
- Default content filter (`accelerator-default-policy`) blocking Medium+ on Hate/Sexual/Violence/Selfharm
- Model deployment (default `gpt-5-mini`, `GlobalStandard`, 30 TPM) bound to the content filter
- Foundry project (`accelerator-default`)
- Azure AI Search, Key Vault (RBAC), Container App, Log Analytics + App Insights
- User-assigned managed identity with Cognitive Services OpenAI User + Azure AI Developer roles

## Troubleshooting — top 5

1. **`preflight: model deployment 'gpt-5-mini' not found`** — the FastAPI
   startup bootstrap (`src/bootstrap.py`) verifies the deployment exists
   before agents are created. If you changed the `models:` block in
   `accelerator.yaml` or the region lacks quota, edit the manifest and
   re-run the approved `accel deploy` flow after fixing it or requesting quota for
   `GlobalStandard <model>`.
2. **`preflight: has no RAI (content filter) policy bound`** — Bicep attaches
   the default policy; if it drifted (portal edit, partial deploy), re-run
   the deployment so ARM reapplies it. The lint rule
   `content_filter_attached` catches this at template-edit time.
3. **`scenario_manifest_valid: module:attr does not resolve`** — the
   `scenario:` block in `accelerator.yaml` points at an import path the lint
   can't find. Verify the file exists under `src/<package path>/<module>.py`
   and the attribute is defined at module scope (the lint walks the AST; no
   import is attempted, so side-effect errors in the module don't hide the
   real issue).
4. **`secrets-doc` lint failure** — a workflow added a `secrets.NEW_NAME` or
   `vars.NEW_NAME` reference, but no entry was added to the tables above.
   Add it before merging.
5. **Deployment completes but `/healthz` returns 503 / startup probe fails** —
   the FastAPI startup bootstrap (`src/bootstrap.py`) is failing inside the
   Container App. The most common cause is RBAC propagation lag: the user-
   assigned MI's role assignments (`Cognitive Services OpenAI User` +
   `Azure AI Developer` on Foundry, `Search Index Data Contributor` on AI
   Search) sometimes take 1–3 minutes to propagate. The startup probe
   budget is 10 minutes (60 retries × 10s) which absorbs this in normal
   conditions; if the probe still fails, inspect Container App logs in App
   Insights (`traces | where operation_Name == "lifespan.startup"`) and
   confirm the role assignments are present. Reapply the target-aware deploy
   after remediation.


---

!!! info "← Back to the partner walkthrough"
    This page is the **full** setup reference. The walkthrough version (with the minimal install path) lives at [2. Set up your machine](../start/ready/02-set-up-your-machine.md).