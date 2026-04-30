# Setup & prereqs

> **Walkthrough version:** [*Get ready → 2. Set up your machine*](../start/ready/02-set-up-your-machine.md) covers the same setup with the linear-flow framing. This page remains the **authoritative deep reference** for prereqs, secrets, and troubleshooting — bookmark it.

**One-time** workstation + subscription readiness.Run this once per partner machine and once per Azure subscription you'll deploy into; you do not re-read this every customer engagement. This is the authoritative reference for **setup, prereqs, secrets, and troubleshooting** — when this page and a custom agent disagree on setup mechanics, this page wins.

## Where you'll work

This document is the authoritative reference for prereqs, secrets, and troubleshooting — most of it is something you'll *configure* (Terminal for CLI installs, GitHub web for environment secrets, Azure portal for quota). The QUICKSTART and hands-on-lab carry the same orientation table for the partner motion itself.

| Where | What you do here |
|---|---|
| **VS Code** | Run installs and verify versions in the integrated terminal (`` Ctrl+` ``); run `azd up` and the eval chain there too; edit `.env` for local dev; edit `accelerator.yaml` and `infra/main.parameters.json` to override defaults |
| **GitHub web (github.com)** | Repo → Settings → Environments → wire `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` and `AZURE_LOCATION` per environment; Settings → Secrets and variables → Actions for repo-level vars |
| **Azure portal (portal.azure.com)** | Confirm Foundry quota in your target region (Foundry → Quotas) before `azd up`; inspect the deployed resource group and resources after |

## What you ship

A partner clone of this template deploys a working agentic AI solution into the
customer's Azure in ~15 minutes via `azd up`. The flagship scenario (Sales
Research & Personalized Outreach) is runnable out of the box; swap it for your
own scenario by editing `accelerator.yaml -> scenario:` and scaffolding under
`src/scenarios/<id>/` with `python scripts/scaffold-scenario.py <id>`.

## Prerequisites

You will need:

| Tool | Why |
|------|-----|
| Azure subscription (Contributor) | `azd up` creates resources here |
| Azure CLI `>= 2.55` | fallback for targeted `az` calls |
| Azure Developer CLI (`azd`) `>= 1.10` | one-shot provision + deploy |
| GitHub CLI (`gh`) `>= 2.50` | repo bootstrap + secrets |
| Git | template clone + branch work |
| PowerShell 7 *(Windows only)* | required because some `azd` lifecycle hooks (e.g. `postdeploy`) run with `pwsh` |
| Docker or Podman *(optional)* | only needed for local container builds; `azd up` uses ACR remote build by default |

> **No Python required to deploy.** Earlier versions of this accelerator required a repo-local Python hook venv (`scripts/setup-hooks`) before `azd up`. That hook surface is gone. `azd up` now goes from a fresh clone straight to a working deployment with no Python on the partner's machine — provisioning is pure Bicep, and post-provision tasks (Foundry agent creation, AI Search index seeding) run inside the Container App at FastAPI startup. Python 3.11+ is still required if you want to **work in the repo locally** — running `pytest`, `scripts/accelerator-lint.py`, scenario scaffolding, or `uvicorn src.main:app` for local dev. See "Repo development (optional)" below.

Model quota: the accelerator deploys a `GlobalStandard` Azure OpenAI model
(default `gpt-5-mini`, 30k TPM — overrideable through the `accelerator.yaml`
`models:` block; see [Customizing models per agent](#customizing-models-per-agent)
below). Confirm quota in your target region before running `azd up`.

### Repo development (optional)

Skip this section unless you plan to run scripts, tests, or the FastAPI app from your machine.

- **Any CPython 3.11+** that resolves on `PATH` as `python` (Windows) or `python3` (macOS/Linux). python.org installers, winget, your distro's package manager, scoop, and **activated Conda environments** all work. Tested on **3.11–3.13**.
- The Microsoft Store Python alias (`%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`) is **not** a real interpreter — install one of the above instead, or activate a Conda env.
- Install the dev extras: `pip install -e ".[dev]"` from the repo root.

## Required GitHub secrets and variables

> **Lab vs. production motion.** Everything from this section through "Private network access" is for the **production / customer motion** in `QUICKSTART.md` — OIDC for CI deploys, multi-environment manifests, HITL approver webhooks, and private networking. The **sandbox lab** (`docs/enablement/hands-on-lab.md`) does not need any of it: it runs `azd up` locally against a sandbox subscription (covered by `azd auth login`) and runs evals locally against the deployed API URL. Skip ahead to "Sandbox smoke-test" below if you're rehearsing in a sandbox.

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

Do **not** set `AZURE_ENV_NAME` anywhere. The azd environment name is derived from
`deploy/environments.yaml` (the `name:` field of the resolved entry). Setting it as
a variable would drift from the manifest; the `deploy_matrix_matches_azure_envs`
lint rule rejects that shape.

### Repo-level variables (repo → Settings → Secrets and variables → Actions → Variables)

| Name | Purpose | Example |
|------|---------|---------|
| `EVALS_API_URL` | API base URL used by the PR-triggered `evals` workflow (`.github/workflows/evals.yml`). Only required if you run evals standalone against an already-deployed environment. | `https://<ca-name>.<region>.azurecontainerapps.io` |

The `deploy.yml` workflow does NOT need `EVALS_API_URL` — it runs `azd up` first
and passes the API URL to the downstream evals job via a job output
(`needs.azd-up.outputs.api_url`). Only configure `EVALS_API_URL` if you want
PR-time evals to run against an existing deployment rather than waiting for a
full deploy chain.

### Local `.env` (for development, not CI)

| Name | Purpose |
|------|---------|
| `AZURE_AI_FOUNDRY_ENDPOINT` | Foundry project endpoint (Bicep output) |
| `AZURE_AI_FOUNDRY_ACCOUNT_NAME` | Parent Cognitive Services account name (Bicep output) |
| `AZURE_AI_FOUNDRY_MODEL` | Model deployment name emitted by Bicep (`infra/modules/foundry.bicep` is the source of truth — agents never declare their own model) |
| `AZURE_SUBSCRIPTION_ID` | Subscription for management-plane pre-flight checks |
| `AZURE_RESOURCE_GROUP` | RG holding the Foundry account |
| `HITL_APPROVER_ENDPOINT` | Webhook URL for side-effect approvals (prod) |
| `HITL_DEV_MODE` | Set to `1` to auto-approve in dev — never in prod |

## Sandbox smoke-test (no customer involvement)

> **This path intentionally bypasses the discovery workshop** so a partner engineer can validate prereqs + infra shape end-to-end in their own subscription. For the full partner motion (discover → scaffold → provision → iterate → UAT → handover → measure) see [`docs/partner-playbook.md`](../partner-playbook.md). For a guided walkthrough of this same smoke-test with check-your-work gates, use [`docs/enablement/hands-on-lab.md`](../enablement/hands-on-lab.md) Lab 1.

```bash
# 1. Clone the template into your sandbox repo
# Replace <your-handle> with any short name (e.g., contoso → contoso-accel-sandbox)
gh repo create <your-handle>-accel-sandbox --template Azure-Samples/agentic-ai-solution-accelerator --private --clone
cd <your-handle>-accel-sandbox
code .

# 2. Authenticate to your SANDBOX subscription (not a customer subscription for the smoke-test)
az login --tenant <your-sandbox-tenant-id>
azd auth login

# 3. Provision + deploy
azd env new sandbox-dev
azd up           # ~10-15 min: Foundry + Search + KV + ACA + App Insights
```

`azd up` returns the API URL. Hit `/healthz` to confirm the scenario loaded;
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
| Sandbox `azd up` (manual deploy from your machine) | `azd env set HITL_APPROVER_ENDPOINT "<url>"` so it's persisted in `.azure/<env-name>/.env` and injected into the Container App. Never `azd env set HITL_DEV_MODE 1` for a deployed environment. |
| CI deploys (`deploy.yml` against a GitHub Environment) | github.com → repo → Settings → Environments → `<env>` → Environment secrets. Add `HITL_APPROVER_ENDPOINT` there; the workflow forwards it into `azd env set` before `azd up`. |

Failures to reach the approver are treated as rejections (fail-closed).

## Scenario customization

1. Read `docs/discovery/SOLUTION-BRIEF-GUIDE.md` and fill
   `docs/discovery/solution-brief.md` — or run `/discover-scenario` in Copilot
   Chat to generate it from a workshop.
2. Run `python scripts/scaffold-scenario.py <id>` to materialize a new
   scenario skeleton under `src/scenarios/<id>/` plus an agent-spec stub.
3. Paste the printed `scenario:` YAML block over the block in
   `accelerator.yaml`. The accelerator lint (`scenario_manifest_valid`)
   verifies every declared import resolves and every required key is present.
4. Customize the prompts, transforms, validators, retrieval schema, seed
   data, and eval golden cases to the brief.
5. `python scripts/accelerator-lint.py` locally before PR; CI re-runs it.

## Customizing models per agent

The accelerator deploys a single `gpt-5-mini` model by default. To assign different models to different agents (e.g. supervisor on `gpt-5`, workers on `gpt-5-mini`), declare a `models:` block in `accelerator.yaml` and set `scenario.agents[].model: <slug>` per agent. Bicep provisions each deployment under the shared content-filter policy on the next `azd up`; FastAPI startup re-points each Foundry agent. Two lint rules (`models_block_shape`, `agent_model_refs_exist`) keep the block well-formed.

Full mechanics, YAML example, and lint behavior live in [`docs/patterns/architecture/README.md` → Customizing models per agent](../patterns/architecture/README.md#customizing-models-per-agent).

## CI chain

`.github/workflows/deploy.yml` runs three jobs, chained so the first deploy
of a freshly cloned repo is green without any manual URL plumbing:

1. `accelerator-lint` — ruff, pyright, `scripts/accelerator-lint.py`
2. `azd-up` (`needs: [accelerator-lint]`) — runs `azd up` and publishes
   `api_url` as a job output
3. `evals` (`needs: [azd-up]`) — pulls `needs.azd-up.outputs.api_url`,
   runs quality + red-team evals, enforces `accelerator.yaml::acceptance`

This chain is enforced by `deploy_gated_on_lint_and_evals` in the
accelerator lint.

The separate `.github/workflows/evals.yml` runs on every PR against the
already-deployed `EVALS_API_URL` (if configured). Use this for fast feedback
between full `azd up` cycles.

## Private network access

For regulated customers, set the Bicep param `enablePrivateLink=true` to disable public access on Foundry and AI Search. Provisioning the actual VNet, private endpoints, and private-DNS zones is **bring-your-own** at Tier 1 (standalone) — see the full procedure and the path to Tier 2 (AVM with PEs provisioned for you) in [`docs/patterns/azure-ai-landing-zone/README.md` → Tier 1 / Going private without leaving Tier 1](../patterns/azure-ai-landing-zone/README.md#tier-1--standalone-default).

## What `azd up` provisions

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
   re-run `azd up` after fixing it or requesting a quota increase for
   `GlobalStandard <model>`.
2. **`preflight: has no RAI (content filter) policy bound`** — Bicep attaches
   the default policy; if it drifted (portal edit, partial deploy), re-run
   `azd up` so the ARM deployment reapplies. The lint rule
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
5. **`azd up` completes but `/healthz` returns 503 / startup probe fails** —
   the FastAPI startup bootstrap (`src/bootstrap.py`) is failing inside the
   Container App. The most common cause is RBAC propagation lag: the user-
   assigned MI's role assignments (`Cognitive Services OpenAI User` +
   `Azure AI Developer` on Foundry, `Search Index Data Contributor` on AI
   Search) sometimes take 1–3 minutes to propagate. The startup probe
   budget is 10 minutes (60 retries × 10s) which absorbs this in normal
   conditions; if the probe still fails, inspect Container App logs in App
   Insights (`traces | where operation_Name == "lifespan.startup"`) and
   confirm the role assignments are present. `azd deploy` (not full `azd up`)
   triggers a revision restart that re-runs bootstrap.


---

!!! info "← Back to the partner walkthrough"
    This page is the **full** setup reference. The walkthrough version (with the minimal install path) lives at [2. Set up your machine](../start/ready/02-set-up-your-machine.md).