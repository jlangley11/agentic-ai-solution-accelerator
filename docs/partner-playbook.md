# Partner playbook — end-to-end delivery motion

This playbook is the narrative companion to the `/delivery-guide` custom agent. It
is written for a **Microsoft partner delivery lead** running an engagement from
SOW to production handover using this accelerator. It explains **why** the
motion is shaped this way and **what "done" looks like** at each stage.

`accel next` is the executable companion: it reads persistent artifacts and
returns the current stage, blockers, approval level, and next command.

> **Looking for the step-by-step?** Use the [partner walkthrough](start/index.md) — *Get ready* (one-time) + *Deliver to a customer* (per engagement). This playbook is the reasoning behind the motion; the walkthrough is the action list.

---

## The motion, in one picture

```
discover ──► design + scaffold ──► provision ──► iterate ──► UAT ──► handover ──► measure
   (1)         (2)          (3)          (4)        (5)        (6)          (7)
   │           │            │            │          │          │            │
   │           │            │            │          │          │            └─ monthly KPI review
   │           │            │            │          │          └─ alerting on App Insights KPI events
   │           │            │            │          └─ acceptance thresholds in accelerator.yaml
   │           │            │            └─ PR-gated: lint + quality evals + redteam
   │           │            └─ accel deploy resolves the target from deploy/environments.yaml
   │           └─ accel design recommends/records architecture; scaffold applies it
   └─ accel intake/discover + specialist interview produce approved intent and requirements
```

Stages **1–2** are partner-facing ("co-build with the customer in real time"). Stages
**3–7** are engineering execution with the customer's Azure tenant in the loop.

!!! info "Why is the accelerator shaped this way?"
    The non-obvious decisions — MAF + Foundry, repo-owned instructions, supervisor + workers, HITL as a primitive, governed retrieval, ABAC-constrained RBAC, and the three-layer worker module — are recorded in [Architecture decision records](adr/index.md). Read those before deviating from a default; each ADR documents what breaks if you flip it.

---

## What the accelerator gives you vs. what you still own

This matters for scoping the SOW honestly.

| Concern                      | In the accelerator                                                                 | Partner owns                                        |
|------------------------------|-------------------------------------------------------------------------------------|-----------------------------------------------------|
| Discovery structure          | `accel intake/discover`, private evidence ledger, `/discover-scenario`, brief template | Workshop facilitation, disclosure decisions, stakeholder map |
| Architecture selection       | Deterministic `accel design` recommendation, comparison, fingerprint, and approval record | Review assumptions, approve or document override rationale |
| Scenario scaffold            | `accel design/scaffold` + specialist worker/tool agents | Scenario-specific prompts, tools, grounding sources |
| Infra                        | `infra/` (AVM-based) + `azure.yaml` + `deploy/environments.yaml`                     | Customer network / private-link overlay if required |
| CI / CD                      | `.github/workflows/{deploy,evals,lint}.yml` + `scripts/accelerator-lint.py`         | Branch protection, required reviewers               |
| Quality + safety evals       | `evals/quality/`, `evals/redteam/`                                                  | Customer golden cases, customer-specific redteam    |
| Agent definitions            | Bootstrap script + agent-spec docs (`docs/agent-specs/`)                            | Customer-specific spec content + Foundry portal catalog-tool attachment (instructions themselves are spec-driven, not portal-edited) |
| Telemetry baseline           | `src/accelerator_baseline/` (telemetry / HITL / killswitch / cost / evals helpers)  | Customer dashboards, alerting thresholds            |
| Landing-zone overlay         | `infra/avm-reference/` + `infra/modules/` (Tier 2 `avm`) and `infra/alz-overlay/` (Tier 3 `alz-integrated`) | Customer ALZ alignment, change control              |
| End-user / app-level auth    | Service-to-service Managed Identity everywhere (Foundry, Search, Key Vault all Entra-only, no keys); HTTPS-only ingress | **Who can call the API / load the UI** — Entra Easy Auth on Container Apps, App Gateway + WAF, or Front Door. The shipped API has no end-user auth dependency. |
| State persistence            | **Nothing.** `/research/stream` is in-memory per request; no datastore in `infra/`.                                       | Cosmos / Postgres / Redis / browser IndexedDB if the customer UX needs run history, multi-user separation, or durable HITL state. |
| HITL approval surface        | The **contract**: `HITL_POLICY` constant + `checkpoint(...)` call + lint enforcement + `tool.hitl_*` events + `HITL_DEV_MODE=1` stub for labs/evals | The **production approver** — Logic Apps, Teams adaptive card, ServiceNow, email — that `HITL_APPROVER_ENDPOINT` points at. The accelerator does not ship an approval UI. |
| Customer-facing UI           | Schema-driven reference workbench plus tailored sales layout, validated streaming, citations, local demo history, and feedback telemetry | Production auth, durable multi-user state, branding, and external HITL approval service |
| SOW / commercial terms       | **Nothing**                                                                         | **You** — templates live in your partner practice   |
| Customer training material   | **Nothing shipped today.** The shipped partner-team self-paced walkthrough is `docs/enablement/hands-on-lab.md`; customer-facing training is partner-owned. | Role-based customer training, support ops |

**Call out explicitly in your SOW:** the accelerator is not a shipping product
for the customer. It is a template a partner team customizes, deploys, and
operates. The customer gets the deployed solution (their Azure, their data,
their branding) — not the template itself.

---

## Stage 1 — Discovery

**Where:** Customer workshop room (or Teams), a local terminal for `accel
intake/discover`, and a supported coding-agent client for the structured
interview. The brief lands in `docs/discovery/solution-brief.md`.

**Goal:** produce a complete `docs/discovery/solution-brief.md` and update
`accelerator.yaml` so the scaffolding step has everything it needs.

**How:** run `accel intake` for source documents, record disclosure and
requirement decisions, then use the discovery specialist for the live interview. It walks
you (or you + customer live) through
sections: business context, personas, measurable success criteria, ROI
hypothesis, solution shape, constraints/risks, acceptance evals.

> **Customer already provided a PRD / BRD / functional spec?** Register it
> with `accel intake add`, review its metadata, approve disclosure before
> model-assisted extraction, then use `/ingest-prd` and the discovery specialist
> in gap-fill mode. See [`docs/discovery/how-to-use.md`](discovery/how-to-use.md).

**What "good" looks like:**

- Every section filled — no `TBD` left by the time you exit the session
- Success criteria are **numeric** (baseline → target, with %)
- 3–6 concrete KPI event names picked — these become typed telemetry events
  in `src/accelerator_baseline/telemetry.py` and App Insights alerts later
- Solution pattern chosen: **supervisor-routing** (flagship default),
  **single-agent**, or **chat-with-actioning**
- RAI risks listed as 3–5 concrete statements — these become redteam cases

**What to push back on:**

- "We want it fast" → "What's the current time, and what does 'fast enough'
  mean to the executive sponsor?"
- "Just use AI Search" → walk through `docs/foundry-tool-catalog.md` to pick
  the right grounding tool (File Search vs Azure AI Search vs SharePoint vs
  Fabric — they each have different prereqs and auth stories)
- Missing HITL gates → "Which tool calls are irreversible? Those need approval
  thresholds, not just logging."

**Deliverable:** local evidence/requirements traceability,
`docs/discovery/solution-brief.md` + edits to
`accelerator.yaml` (`solution.pattern`, `solution.hitl`,
`solution.data_residency`, `solution.identity`, `acceptance.*`, `kpis[].name`).

---

## Stage 2 — Design + scaffold

**Where:** local terminal plus the partner's preferred coding-agent client and
editor.

**Goal:** approve the correct Foundry/application architecture, then adapt the
repo with a clean, explainable diff.

**How:** use the CLI for readiness and structural changes, then specialist
agents for customer-specific authoring:

```
accel design
accel design --approved-by "<partner architect>" --apply
accel scaffold --scenario-id <id> --dry-run
accel scaffold --scenario-id <id> --apply
/define-grounding       →  per-worker FoundryIQ vs none + Search indexes + read-only catalog intent
/implement-workers      →  fills every stub prompt.py / transform.py / validate.py + Foundry agent spec
```

The Architecture Advisor compares prompt and Hosted agents, selects
`managed-prompt`, `harness`, or `custom-workflow`, then separately selects the
orchestration pattern, application shell, and deployment target. Requirements
changes invalidate the approval automatically.

`accel scaffold` wraps `scripts/scaffold-scenario.py` transactionally; that
script and `scaffold-agent.py` auto-seed
`evals/quality/golden_cases.jsonl` with a stub `q-001` so lint stays green
without manual eval-file edits.

**What `accel scaffold` materializes:**

- `src/scenarios/<package>/{__init__,schema,workflow,retrieval}.py`
- A `primary` package/spec for prompt-agent or Harness decisions, or a
  `supervisor` package/spec for hosted custom orchestration
- `data/samples/<package>.json`
- A transactionally updated `accelerator.yaml` scenario block
- A stub `q-001` in `evals/quality/golden_cases.jsonl` (refine the
  `query` and `expected` fields to encode real customer success criteria)

For hosted multi-agent decisions, **`/define-grounding` writes:** per-worker `retrieval:` blocks
(mode = `foundry_tool` or `none`) and read-only `catalog_tools:` lists in
`accelerator.yaml -> scenario.agents[]`, plus matching entries in
`scenario.retrieval.indexes[]`. FoundryIQ is the consolidated enterprise
knowledge layer; AI Search lives underneath it. **Always start with
`foundry_tool` unless the worker is purely transformational** (router,
formatter, aggregator). Shared provisioning creates the Knowledge Sources, KBs,
and managed attachments on deployment.

**What `/implement-workers` writes:** real `prompt.py`, `transform.py`,
`validate.py`, and `docs/agent-specs/<foundry_name>.md` for every
scaffolded-but-unfinished worker, walked in dependency order off the
`WORKERS` registry in `src/scenarios/<id>/workflow.py`. Use
`/implement-worker <worker_id>` to fill a single worker (same code path,
narrower scope).

**Authoring after the structural scaffold:**

- Re-sync `solution.*`, governed grounding-source metadata, `acceptance.*`, and
  `kpis[]` from the approved brief
- Refine each golden case's `query` and `expected` fields to encode
  real customer success criteria; add 4+ more cases per scenario
- Add a redteam case per RAI risk in `evals/redteam/cases.jsonl`
- Register each KPI event in `src/accelerator_baseline/telemetry.py` and
  append a `KqlItem/1.0` entry per KPI under `items[]` in
  `infra/dashboards/roi-kpis.json`
- Create `src/tools/<tool_name>.py` per side-effect tool via `/add-tool`
  (each wrapped in `hitl.checkpoint(...)`)

**Escape hatch (advanced / fallback):** if a custom agent fails midway, the
underlying scripts run directly — `python scripts/scaffold-scenario.py
<id>`, `python scripts/scaffold-agent.py <agent_id> --scenario <scenario-id>
--capability "<one-liner>"`. The custom agents wrap these with brief-driven
customization; the scripts alone only do the structural scaffold.

**What "good" looks like:**

!!! tip "Authoring agent instructions"
    **Agent system instructions live in `docs/agent-specs/<foundry_name>.md`
    under `## Instructions`.** Edit those files, not Python. Shared
    provisioning syncs them during deployment; `prompt.py` is per-request only.

- `accel validate --full --execute` passes
- Each `prompt.py` is a **per-request input builder only** — no system
  instructions inline. The agent's system instructions live in
  `docs/agent-specs/<foundry_name>.md` (see [agent-specs README](agent-specs/README.md))
  and `src/bootstrap.py` syncs them to Foundry on every deploy.
- Every worker agent has `transform.py` returning a normalized dict and
  `validate.py` enforcing the schema. Reject any PR that skips either step.

**If the pattern is single-agent or chat-with-actioning** instead of the
flagship supervisor pattern, run `/switch-to-variant` to swap in the stub
scaffold from `patterns/single-agent/` or `patterns/chat-with-actioning/`
(each ships a single source file + a custom agent that copies it over
`src/main.py`, prunes flagship workers, and updates
`accelerator.yaml.solution.pattern`). Then finish re-authoring under
`src/scenarios/<new-id>/` using the flagship as the reference shape.

**Deliverable:** a PR-sized diff with all new files named per the scenario
ID and the build still green.

---

## Stage 3 — Provision

**Where:** coding-agent client for landing-zone/environment authoring; terminal
signed into the customer's tenant for `accel deploy/evaluate`; GitHub and Azure
portals for environment, OIDC, and resource verification.

**Goal:** deploy the scaffolded solution to the customer's Azure against a
named environment.

**How:**

1. `/configure-landing-zone` to pick the Azure AI Landing Zone tier and
   update `accelerator.yaml` + `infra/` accordingly. The custom agent covers
   three tiers:
   - **Tier 1 — `standalone`** (default; pilot / SMB greenfield / partner
     self-host): public endpoints, minimal infra.
   - **Tier 2 — `avm`** (customer has a CCoE mandate for private endpoints
     + CAF guardrails on day one): private-link + AVM-shaped modules under
     `infra/modules/` and `infra/avm-reference/`.
   - **Tier 3 — `alz-integrated`** (customer already has an ALZ — hub vNet,
     shared private DNS zones, policy assignments): wires the overlay in
     `infra/alz-overlay/` and enforces the `tier3InputGuard` in
     `infra/main.bicep`.
2. `/deploy-to-env <env-name>` to register a new GitHub Environment entry in
   `deploy/environments.yaml` and scaffold the required secrets / variables
   per the "Required GitHub secrets and variables" section of `docs/getting-started/setup-and-prereqs.md`.
   Its `deployment_target` must match the approved Architecture Advisor decision.
3. From the customer's deployment-owner machine, run `accel environment list`,
   then preview/preflight/apply with `accel deploy`. First deploy takes ~15 min on a clean subscription. The
   `accel deploy` resolves the environment target and invokes the corresponding
   `azd` project:
   - `preprovision` → none (Bicep `loadYamlContent` parses `accelerator.yaml -> models[]` at compile time)
   - `postprovision` → none. Foundry agent create/update **and**
     AI Search index seeding both run inside the Container App at FastAPI startup via `src/bootstrap.py` (creates/verifies Foundry agents declared in
     `accelerator.yaml` + seeds every index declared in
     `scenario.retrieval.indexes[]`; the flagship scenario ships one
     `accounts` index, scaffolded scenarios declare their own)
4. Smoke-test the deployed endpoint — either the container URL or the SDK
   path in `src/main.py`, depending on scenario shape.
5. Confirm each Foundry agent appears in the portal with the placeholder
   instructions ready for editing. Restart the Container App revision (Container Apps -> Revisions -> Restart) or
   rerun the target-aware `accel deploy` apply flow for recovery.
6. **Establish the acceptance baseline** before exiting this stage:

   ```bash
   accel evaluate --api-url <api-url> --execute
   ```

   This full chain applies to `selfhost`. Hosted preview currently has a
   fresh-session protocol smoke, not equivalent full acceptance. For self-host,
   retain the generated acceptance artifact as the known-good baseline.

**What "good" looks like:**

- `infra/main.bicep` tags every resource with `azd-env-name` and
  `workload=<scenarioId>-accelerator` (wired from `scenarioId` param). If
  the customer needs additional tags (e.g. `engagement`, `costcenter`), add
  them to the `tags` object in `infra/main.bicep` — they do **not**
  propagate automatically from GitHub Environment variables today.
- Managed Identity on the Container App has the RBAC pairs documented in
  `docs/foundry-tool-catalog.md` for the tools this scenario uses.
- `APPLICATIONINSIGHTS_CONNECTION_STRING` is populated in the container's
  env (wired by `infra/modules/container-app.bicep`). Key Vault is
  referenced via RBAC + MI, not via a `KEY_VAULT_URI` env var; secrets are
  resolved at runtime by the SDK.
- `infra/alz-overlay/` guard passes if Tier 3 is enabled (`tier3InputGuard`
  in `infra/main.bicep` fails fast on missing inputs).

**If deployment fails:** first inspect the CLI `blocking_issues`, then see `docs/getting-started/setup-and-prereqs.md`
("Troubleshooting — top 5"). The most common failures are model-quota (wrong region),
OIDC (federated credentials not wired), and AI Search role assignment (needs
**Search Index Data Contributor** + **Search Service Contributor**, not
"Data Reader").

---

## Stage 4 — Iterate

**Where:** VS Code (Copilot Chat sidebar for prompt / tool / grounding edits and `/explain-change` preflights; integrated terminal for `git push`); github.com → repo → Pull requests / Actions to watch the four CI gates; Azure portal → App Insights for latency and KPI signals between PRs.

**Goal:** move the agent quality from "it runs" to "it meets acceptance."

**How:** partner refines prompts, tools, grounding, response schemas, and
experience metadata via a coding agent
inside the repo. Every change is a PR. CI runs four gates, all of
which must pass before merge:

- `scripts/accelerator-lint.py` — deterministic policy checks,
  fast); see the `acceptance` section of `accelerator.yaml` for the policy set
- `evals/quality/run.py` — quality evals against golden cases
- `evals/redteam/run.py` — safety evals against the scenario's RAI cases
- `build + type check` — backend build and typing gate wired in
  `.github/workflows/deploy.yml`

**Where agent instructions live:** `docs/agent-specs/<foundry_name>.md` is
the **authoring source of truth**; shared provisioning syncs the spec to the
matching Foundry agent version during deployment.
Treat the repo as the audit trail — every PR that edits a `prompt.py`, an
agent spec, a tool, or an acceptance threshold is the durable record. The
`/explain-change` custom agent is a **read-only CI preflight** — it tells you
which lint rules and evals will fire for the current diff; it does not write
changelogs.

**What "good" looks like:**

- Golden-case count > 20 by end of stage — `evals/quality/golden_cases.jsonl`
- Redteam passes on every PR — no deferred exceptions
- Cost per call trending toward the acceptance target (instrument via
  `src/accelerator_baseline/cost.py`)
- P50 / P95 latency visible in App Insights KPI events
- **At least one irreversible HITL tool exercised end-to-end before exiting Stage 4** — trigger a tool call that hits `hitl.checkpoint(...)`, the approver endpoint receives the request, the approver approves it, the tool executes, and the redteam case for that tool passes. UAT is not the place to discover that the approval flow is mis-wired; surface it here.

**When a worker is underperforming:** add a new case to `golden_cases.jsonl`
showing the failure, then fix the prompt / tool in a PR. Close the loop:
the case stays green or the PR blocks.

**Building the customer-facing UI:** the accelerator API is headless. Start
from [`patterns/sales-research-frontend/`](../patterns/sales-research-frontend/README.md)
— a minimal React + Vite + TypeScript starter that consumes `/research/stream`
and deploys to Azure Static Web Apps. Fork it as the baseline for your
customer's UX work; auth, branding, and any HITL approval surfaces are
partner-wired on top.

---

## Stage 5 — UAT

**Where:** Customer-facing sessions (browser → deployed UI for the customer's golden cases); VS Code (editor to add each customer case to `evals/quality/golden_cases.jsonl`, integrated terminal to re-run the eval chain); Azure portal → App Insights for the dashboards the sponsor walks through at sign-off.

**Goal:** customer accepts the solution against their own bar.

**How:** customer runs their golden cases on the deployed environment.
Partner adds each customer case to `evals/quality/golden_cases.jsonl` so it's
permanently regression-protected. The pass bar is
`accelerator.yaml.acceptance.*` — quality threshold, groundedness threshold,
safety pass, P50/P95 latency, cost per call.

**What "good" looks like:**

- Customer signs off against the acceptance thresholds — not against vibes
- `accel uat report` captures the reviewed acceptance result and
  `accel uat signoff` records sponsor approval
- HITL exercised end-to-end for at least one irreversible tool (e.g., CRM
  write, email send). **The accelerator does not ship a HITL approval UI:**
  the flagship HITL pattern (`docs/patterns/rai/README.md`, "Principle 3") is
  a partner-wired approval flow (Logic Apps, Teams adaptive card, ticketing
  system) that the tool blocks on until the approver endpoint
  returns. `src/accelerator_baseline/hitl.py` is the checkpoint contract.
- Killswitch flipped and verified — `src/accelerator_baseline/killswitch.py`
- Dashboards in App Insights show the KPI events the sponsor cares about

**When UAT fails:** it is almost always one of (1) grounding source coverage,
(2) prompt specificity, or (3) tool guard strictness. The delivery-guide
custom agent has a triage tree for each.

---

## Stage 6 — Production handover

**Where:** coding-agent client for environment authoring; terminal for
target-aware `accel deploy` and handover commands; Azure portal for alert
wiring; live customer ops meeting for acceptance.

**Goal:** move the solution to the customer's production environment and
hand day-2 operations over.

**How:**

1. Use `/deploy-to-env <customer-short-name>-prod` to register the production
   environment in `deploy/environments.yaml`.
2. Preview, approve, and apply `accel deploy --env <customer-short-name>-prod
   --region <region>`. The self-host target runs root `azd up`; Hosted preview
   runs nested `azd provision` followed by `azd deploy`.
3. Wire App Insights alerting on the KPIs the engagement committed to
   in `accelerator.yaml.kpis[]` (customer-owned — `kpis[]` carries
   `{name, type, baseline, target}` metadata only; the matching telemetry
   event per KPI is wired in scenario code, and neither
   alerts nor dashboards beyond `infra/dashboards/roi-kpis.json` are
   auto-created)
4. Preview `accel handover generate --env <env> --dry-run`, approve/apply the
   draft, review customer-owned fields, then record ops acceptance with
   `accel handover approve --approver <name> --apply`.

**Handover to whom:** the customer's internal owner per the SOW. If the
partner is retaining operations, skip to stage 7. If the customer's ops
team is taking over, share `docs/customer-runbook.md` — the shipped
day-2 runbook covering monitoring, killswitch, evals re-run, model swap,
secret rotation, incident response, and scaling. Add your engagement-specific
handover notes on top using [`docs/handover/handover-packet-template.md`](handover/handover-packet-template.md)
(endpoint URLs, HITL approver runbook, alert rules, killswitch, rollback
path, customer-specific deviations from shipped defaults, SLAs, contacts).

**What "good" looks like:**

- Zero manual steps outside the documented scripts — anything that isn't in
  a script or custom agent is a risk item in the handover
- Customer can reproduce `accel deploy` against a new declared environment without
  partner assistance
- The handover packet lists owner, SLA, alerting, and rollback — no
  implicit knowledge

---

## Stage 7 — Measure

**Where:** Azure portal → App Insights → Logs (the KPI events the scenario emits are the source of truth); customer monthly value-review meeting to walk the deck.

**Goal:** prove value monthly against the KPIs agreed in stage 1.

**How:** run the value review against `accelerator.yaml.kpis`. The App
Insights events the scenario emits are the **only** numbers that count —
no spreadsheets, no screenshots of runs.

**What "good" looks like:**

- Monthly value-review deck populated from App Insights queries, not from
  memory
- At least one KPI moved from baseline toward target within 30 days of go-live
- Feedback captured back to Microsoft in this repo's Issues — both what
  worked and what didn't. The accelerator improves only when partner
  teams file issues.

---

## Commands and specialist agents at a glance

| When you need to…                            | Use                                                                  |
|----------------------------------------------|----------------------------------------------------------------------|
| Determine the current stage                   | `accel next`                                                        |
| Inspect all blockers/stages                    | `accel status --verbose`                                            |
| Register and govern source documents           | `accel intake …`                                                    |
| Run structured discovery                       | `accel discover` + `/discover-scenario`                             |
| Pre-draft from approved evidence               | `/ingest-prd`                                                       |
| Recommend and approve architecture              | `accel design` → reviewed `--approved-by … --apply`                 |
| Preview/apply the initial scenario              | `accel scaffold --scenario-id <id> --dry-run/--apply`               |
| Wire FoundryIQ + Search + read-only catalog intent    | `/define-grounding`                                                  |
| Fill every scaffolded worker (3-layer + Foundry spec) | `/implement-workers` (or `/implement-worker <id>` for a single worker) |
| Add a worker agent post-scaffold             | `/add-worker-agent`                                                  |
| Add a tool (local Python or Foundry)         | `/add-tool`                                                          |
| Swap from flagship to a variant pattern      | `/switch-to-variant`                                                 |
| Choose landing-zone tier / reconfigure infra | `/configure-landing-zone`                                            |
| Register a new GitHub Environment            | `/deploy-to-env`                                                     |
| Preview/preflight/execute deployment          | `accel deploy --dry-run/--execute/--apply`                           |
| Validate the ALZ overlay (Tier 3)            | `python scripts/validate-alz.py`                                     |
| Decommission the engagement safely           | `/teardown` (or `python scripts/teardown-preflight.py --env <name>`) |
| Review current diff and impact                | `accel review`                                                       |
| Run repository validation                     | `accel validate --full --execute`                                   |
| Run acceptance                                | `accel evaluate --api-url <url> --execute`                           |
| Produce UAT/handover records                  | `accel uat …` + `accel handover …`                                  |
| Full engagement companion                     | `/accelerator` or `/delivery-guide`                                 |
| Scaffold a worker                             | `/add-worker-agent` (raw script is the debug fallback)              |
| Lint the repo against policy                 | `python scripts/accelerator-lint.py`                                 |
| Create / update Foundry agents               | target-aware `accel deploy` apply                                  |
| Seed the AI Search index                     | target-aware `accel deploy` apply                                  |
| Check SDK pin freshness                      | `python scripts/ga-sdk-freshness.py`                                 |
| Optional native Foundry evaluation            | `accel evaluate --foundry --execute`                                |

These scripts are mostly Python / Azure-SDK-based; a few utility scripts
(e.g., `explain-change.py`) shell out to
standard developer tooling (`git`, `azd`) — already installed if you
followed the "Prerequisites" section of `docs/getting-started/setup-and-prereqs.md`.

---

## Escalation and feedback

- Technical issues with the accelerator template → file a GitHub Issue on this
  repo
- Security issues → see `SECURITY.md`
- Guidance on Foundry tool choices that aren't clearly covered in
  `docs/foundry-tool-catalog.md` → file an Issue with the engagement's
  `solution.pattern` and the tool under consideration
- Engagement commercial questions → your partner practice, not this repo

---

## What this playbook is NOT

- A replacement for Microsoft Learn. Every Foundry / Azure detail in this
  accelerator has an authoritative Learn page — always check it when pricing,
  regions, or GA/preview status matter.
- A replacement for your partner practice's SOW, rate card, or staffing model.
- A promise that `azd up` will succeed on a subscription with wrong quotas,
  missing OIDC, or a conflicting ALZ policy. Stage 3 is iterative; the
  getting-started troubleshooting matrix is where failures go to die.
- A substitute for customer-specific training. The shipped partner-team
  self-paced walkthrough lives at `docs/enablement/hands-on-lab.md` —
  it gets partner engineers comfortable with the template, not a
  customer's end users. Customer end-user training is partner-owned
  either way.

---

!!! info "← Back to the partner walkthrough"
    This page is the **narrative** companion. The step-by-step actions live in the [partner walkthrough](start/ready/01-get-oriented.md) — start there, or return to whichever step sent you here. For the per-customer motion in particular: [5. Discover with the customer](start/deliver/02-discover-with-the-customer.md).