# QUICKSTART — Deploy an Agentic AI Solution in ~15 minutes

> **Preferred interface:** run `accel next` from the repository root. The CLI
> detects the current lifecycle stage, blockers, required approvals, and next
> command. The steps below remain the printable/manual reference.

> **Recommended path:** Use the [partner walkthrough](docs/start/index.md) — *Get ready* (one-time) + *Deliver to a customer* (seven steps per engagement). This file is the printable cheat-sheet version of the per-customer steps; keep it open as a reference during an engagement.

> **First time on this accelerator?** Do *Get ready* in the walkthrough first — [1. Get oriented](docs/start/ready/01-get-oriented.md) → [2. Set up your machine](docs/start/ready/02-set-up-your-machine.md) → [3. Rehearse in a sandbox](docs/start/ready/03-rehearse-in-a-sandbox.md) — **before** Step 1 below.

> **Before Step 5:** Authenticate against the customer's Azure tenant and
> confirm you can create resources there. `accel deploy` previews the resolved
> target and cloud actions before execution.

> **Joining mid-engagement?** If discovery is complete, jump to
> [Step 3 — Decide the architecture and scaffold](#step-3--decide-the-architecture-and-scaffold).
> If a brief does not exist, return to the [Discovery kit](docs/discovery/how-to-use.md).

---

## Where you'll work

You'll move between three places as you go through this guide. Every step below opens with a **Where** line so you know which one to be in.

| Where | What you do there | How to open it |
|---|---|---|
| **Local coding-agent CLI / VS Code** | Run `accel next`, review diffs, and use Copilot CLI, Codex, Claude Code, or VS Code custom agents for conversational authoring. The CLI owns lifecycle state; specialist agents own interviews and code-generation guidance. Trust the workspace before allowing agent tools. | From the clone: `code .`, `copilot`, `codex`, or `claude` |
| **GitHub web (github.com)** | Configure repo Settings → Environments (secrets + OIDC), open PRs, watch Actions runs | Your browser, on the cloned repo |
| **Azure portal (portal.azure.com)** | Inspect the resource group, Foundry quota, Application Insights logs and dashboards | Your browser, signed into the customer's tenant |

---

## Step 1 — Clone the template

**Where:** VS Code. Run the `gh` commands from the integrated terminal (`` Ctrl+` ``), then load the cloned folder into your current VS Code window via **File → Open Folder** (`Ctrl+K Ctrl+O` on Windows/Linux, `Cmd+K Cmd+O` on macOS) and pick the new `<customer-short-name>-agents` folder. (If you're running from a standalone shell instead, `code <customer-short-name>-agents` opens it in a fresh window.)

```bash
# Replace <customer-short-name> with your customer's short name (e.g., contoso, fabrikam)
gh repo create <customer-short-name>-agents --template Azure-Samples/agentic-ai-solution-accelerator --private --clone
cd <customer-short-name>-agents
python -m pip install -e ".[dev]"
accel next
```

VS Code opens with Copilot already configured via `.github/copilot-instructions.md`. Copilot now knows the hard rules:

- Agent Framework + Foundry only
- DefaultAzureCredential only — no keys
- HITL required for every side-effect tool call
- PR evals gate merges; a post-deploy regression suite guards `main`
- Content filters configured via IaC, not the portal

---

## Step 2 — Run the discovery workshop

**Where:** VS Code (Copilot Chat sidebar). The use-case canvas and discovery workbook are partner-fillable templates you handle in your usual editor before this step.

> **The full discovery sequence** — canvas → local evidence intake → workshop
> → approved requirements → brief → ROI — is owned by the
> [Discovery kit](docs/discovery/how-to-use.md).

If source documents exist:

```powershell
accel intake add <prd> <security-doc> <workshop-file>
accel intake list
accel intake review <source-id>
```

Sources remain local-only until an explicit `approved_for_model` decision.

In Copilot Chat:

```
/discover-scenario
```

Copilot interviews you and writes `docs/discovery/solution-brief.md`. The brief
is the **customer-approved intent contract** from which downstream artifacts are
derived.

The brief is the customer-approved intent contract. `accelerator.yaml` remains
the executable deployment contract; `accel` checks the transition between them.

---

## Step 3 — Decide the architecture and scaffold

**Where:** Local terminal for deterministic preview/apply; coding-agent CLI or
VS Code for scenario-specific authoring.

```powershell
accel design
accel design --approved-by "<partner architect>" --apply
accel scaffold --scenario-id <scenario-id> --dry-run
accel scaffold --scenario-id <scenario-id> --apply
```

`accel design` explains why the requirements fit a prompt or Hosted agent,
which orchestration pattern is needed, whether an application shell is
required, and which deployment target follows. An override requires
`--override-reason`.

Then use `/define-grounding` and `/implement-workers` when the scaffold needs
customer-specific worker instructions, transforms, validators, and tools.

For a new scenario, substitute its package id for `sales_research` in the
`src/scenarios/<...>/` paths. Everything outside `src/scenarios/` remains
scenario-agnostic.

| Brief field → | Lands in (flagship paths shown; `src/scenarios/<id>/` for custom scenarios) |
|---|---|
| Problem + persona | `docs/agent-specs/<supervisor>.md` system instructions; `prompt.py` remains a per-request envelope |
| Foundry architecture | `accelerator.yaml -> architecture` recommendation, approval, rationale, and requirements fingerprint |
| Solution shape | `scenario.implementation` + architecture-aware primary/supervisor scaffold |
| Grounding sources | `scenario.agents[].retrieval` + FoundryIQ/Search index declarations |
| Side-effect tools | New files under `src/tools/` with HITL scaffolding |
| HITL gates | `src/accelerator_baseline/hitl.py` rules |
| Constraints | `infra/main.parameters.json` + `accelerator.yaml` |
| Success criteria | `evals/quality/golden_cases.jsonl` + CI gates |
| RAI risks | `evals/redteam/` custom adversarial cases |
| ROI KPIs | `src/accelerator_baseline/telemetry.py` events + `infra/dashboards/roi-kpis.json` (panels are scenario-agnostic; rename the dashboard per engagement) |

Review with `accel review`, then run `accel validate --full --execute`.

---

## Step 4 — Preflight: landing zone + GitHub Environment

**Where:** VS Code (Copilot Chat sidebar) for both custom agents. `/deploy-to-env` will also have you confirm settings on github.com → your repo → Settings → Environments at the end.

Before deployment, make two decisions and wire one piece of OIDC plumbing.
These take 5–15 minutes and prevent the most common first-deploy failures.

```
/configure-landing-zone     # pick standalone | avm | alz-integrated; updates accelerator.yaml + infra/
/deploy-to-env <env-name>   # selfhost | foundry-prompt | hosted-preview
accel environment list      # confirms the executable environment contract
```

`/configure-landing-zone` walks you through the tier decision (Tier 1 standalone for pilots / SMB; Tier 2 `avm` for private endpoints; Tier 3 `alz-integrated` for an existing customer ALZ hub). `/deploy-to-env` adds the env to `deploy/environments.yaml`, creates the matching GitHub Environment, and wires the OIDC federated credential so CI can deploy without a service-principal secret. Skip this and your first PR will fail auth.

---

## Step 5 — Provision + deploy to customer's Azure

**Where:** Local terminal, signed into the customer's Azure tenant. The
deployed API URL prints when deployment completes; keep it for Step 6.

> **Authoring agent instructions.** Agent system instructions live in
> `docs/agent-specs/<agent>.md` under the `## Instructions` heading —
> edit those Markdown files, not Python. Provisioning syncs each spec to
> Foundry (`src/bootstrap.py` for self-host; the hosted postdeploy hook for
> Hosted preview). `prompt.py` is for
> *per-request* input construction only.

```bash
# Replace <customer-tenant-id> with the customer's Azure tenant GUID, and
# <customer-short-name> with the customer's short name (e.g., contoso)
az login --tenant <customer-tenant-id>
azd auth login
accel deploy --env <environment-name> --region <region> --dry-run
accel deploy --env <environment-name> --region <region> --execute
accel deploy --env <environment-name> --region <region> --execute --apply
```

For `selfhost`, the apply path invokes root `azd up`; Hosted preview invokes
nested `azd provision` followed by `azd deploy`. Resources use managed identity
and IaC content filters. Partners wire declared KPI events and alerts.

~10–15 minutes; URL of the deployed agent prints at the end.

---

## Step 6 — Establish the acceptance baseline

**Where:** VS Code's integrated terminal (repo root). Use the same terminal session as Step 5 so the API URL is still on screen.

> **Target scope:** the full quality/red-team chain below targets the self-host
> SSE API. Hosted preview currently runs a fresh-session Responses smoke only;
> do not treat that smoke as equivalent acceptance.

Before you start iterating, run the acceptance chain once against the freshly deployed flagship. The numbers it produces are the engagement's **known-good starting point**: every PR in Step 7 has to clear this same bar.

```bash
accel evaluate --api-url <api-url>
accel evaluate --api-url <api-url> --execute

# Optional consumption-based Foundry relevance + groundedness evaluators:
accel evaluate --api-url <api-url> --foundry --execute
```

`enforce-acceptance.py` reports pass / fail against every threshold in `accelerator.yaml.acceptance` (quality, groundedness, safety, P50/P95 latency, cost per call). If a threshold fails on the unmodified flagship, fix the deploy first — quotas, model region, or grounding seed are the usual culprits — before you start authoring scenario-specific changes.

The unified run writes a local acceptance artifact for UAT:

```powershell
accel uat report
```

---

## Step 7 — Iterate with Copilot; ship through CI gates

**Where:** VS Code (Copilot Chat sidebar for the agent edits, integrated terminal for `git push`), then GitHub web (github.com → your repo → Pull requests / Actions) to watch CI.

In VS Code, just talk to Copilot:

> *"Add a tool to create a ticket in ServiceNow; it should require HITL for anything with priority high."*

Copilot follows `copilot-instructions.md` — creates `src/tools/servicenow_ticket.py` with HITL scaffolding, wires it, adds a unit test.

Before committing:

```powershell
accel review
accel validate --full --execute
```

```bash
git checkout -b feat/servicenow-tool
git add -A && git commit -m "Add ServiceNow tool"
gh pr create
```

The PR triggers:
1. `scripts/accelerator-lint.py` (deterministic policy checks)
2. `evals/quality/` (must clear thresholds in `accelerator.yaml -> acceptance`)
3. `evals/redteam/` (XPIA + jailbreak must pass)
4. `build + type check`

Any red light blocks merge. Green = `azd deploy` against customer env.

---

## Step 8 — Ship a UI

**Where:** VS Code — edit the React + Vite + TypeScript starter under `patterns/sales-research-frontend/` in the editor; run `npm install` / `npm run dev` / `swa deploy` from the integrated terminal.

For the self-host target, Steps 1–7 give you an SSE API plus
`GET /scenario/metadata`. Fork the
[Accelerator Workbench](patterns/sales-research-frontend/README.md): the
flagship keeps tailored sales layouts, while other scenarios receive a
JSON-Schema-generated form and validated result panels.

**Before customer-facing**, you also wire — none of which the accelerator ships: end-user auth (Easy Auth / App Gateway / Front Door), state persistence (Cosmos / Postgres / Redis), and the HITL approval surface (Logic Apps / Teams / ServiceNow that `HITL_APPROVER_ENDPOINT` resolves to). The full ownership boundary lives in [`docs/partner-playbook.md`](docs/partner-playbook.md#what-the-accelerator-gives-you-vs-what-you-still-own) — call it out in the SOW.

If your customer already has an internal portal or Power Platform surface,
the same pattern shows how to call the SSE endpoint from any client; lift
`src/services/scenarioClient.ts` and `src/types/scenario.ts`.

Hosted preview exposes Responses/Invocations protocols and requires a matching
client adapter; the shipped workbench is not that adapter.

---

## Need a different shape?

The variants below are **manual re-authoring walkthroughs** (documented in `patterns/<variant>/README.md`), not drop-in packages. Run `/switch-to-variant` for a guided walkthrough of re-authoring the scenario under `src/scenarios/<new-id>/`:

- **Simpler** than supervisor-routing? `/switch-to-variant` → pick `single-agent`.
- **Conversational** front-end? `/switch-to-variant` → pick `chat-with-actioning`.
- **Different business scenario?** See `docs/references/` for Customer Service and RFP Response walkthroughs.

## Need help?

- `docs/getting-started/setup-and-prereqs.md` — authoritative prereqs, secrets, troubleshooting
- `docs/discovery/SOLUTION-BRIEF-GUIDE.md` — how to run the workshop
- `docs/version-matrix.md` — known-good SDK pins
- `docs/agent-specs/README.md` — per-agent system instructions and bootstrap mechanics
- Issues in this repo — intake for feedback and new patterns
