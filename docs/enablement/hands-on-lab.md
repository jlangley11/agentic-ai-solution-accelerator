# Hands-on lab — first deployment walkthrough

> **Walkthrough version:** [*Get ready → 3. Rehearse in a sandbox*](../start/ready/03-rehearse-in-a-sandbox.md) frames this lab as the third step of the partner onboarding flow. This page is the full lab content with check-your-work gates.

**Sandbox rehearsal** for a **partner engineer** new to the agentic AI
solution accelerator. Recommended **before your first customer-facing engagement**; not required per customer (returning engineers skip straight to `QUICKSTART.md`). After finishing, you'll be comfortable enough
with the template to run a real customer engagement against it.

This is not training for the customer's end users — that's partner-owned,
separately. And it's not a substitute for reading `docs/getting-started/setup-and-prereqs.md`
(the authoritative prereqs + troubleshooting) or `QUICKSTART.md` (the
eight-step partner motion). The lab walks you through the same surface area
with check-your-work gates so you catch misunderstandings in a sandbox,
not in front of a customer.

---

## Objectives

After the lab you can:

1. Deploy the flagship scenario through `accel deploy` and confirm it works
   end-to-end.
2. Open the reference front-end locally and drive the workflow from a
   browser.
3. Read App Insights telemetry emitted by real browser traffic, and know
   which dashboard panels require partner-wired emitters to light up.
4. Run `accel evaluate` and inspect the acceptance artifact.
5. Edit an agent's instructions the supported way (spec file + `azd
   provision`), not by portal drift.
6. Swap the model via `accelerator.yaml → models[]`.
7. Scaffold a new side-effect tool via `/add-tool` with HITL baked in,
   and know why the redteam case is not optional.
8. Review/approve an Architecture Advisor recommendation, then scaffold it.

---

## Prerequisites

1. An Azure **sandbox** subscription where you have Contributor — do
   **not** use a customer subscription for the lab. Cleanup at the
   end is `azd down --purge`.
2. Regional Foundry quota for `gpt-5-mini` on `GlobalStandard` (the
   shipped default is 30k TPM — see `infra/main.parameters.json`).
   Confirm in the Azure portal → Foundry → Quotas before starting.
3. The tools listed in the "Prerequisites" section of `docs/getting-started/setup-and-prereqs.md`
   (Azure CLI, `azd`, `gh`, `git`, PowerShell 7 on Windows, Python 3.11+). Docker/Podman is optional — `azd up` builds the container image remotely in Azure Container Registry by default.
4. A GitHub org/account where you can push a private template clone.
5. A supported coding-agent client. VS Code is optional; `/accelerator` and
   specialist agents are available in Copilot, while the shared skill works
   from Copilot CLI, Codex, and Claude Code.

If any prereq is missing, fix it before continuing — this lab does
not work around a broken local environment. The troubleshooting
matrix in `docs/getting-started/setup-and-prereqs.md` ("Troubleshooting — top 5") is
the first stop when something goes wrong.

> **Lab-only scope.** Other sections of `docs/getting-started/setup-and-prereqs.md`
> — GitHub Environment-scoped secrets (`AZURE_CLIENT_ID` / `TENANT_ID` /
> `SUBSCRIPTION_ID` / `AZURE_LOCATION`), repo-level `EVALS_API_URL`,
> `HITL_APPROVER_ENDPOINT`, multi-environment `deploy/environments.yaml`,
> and private-network (`enablePrivateLink`) setup — apply to the
> **production / customer motion** in `QUICKSTART.md`, not this lab. The lab
> runs `azd up` locally against a sandbox subscription (`azd auth login`
> covers auth), runs evals locally against the deployed API URL, and uses a
> single `lab-dev` environment on Tier 1 standalone. You'll meet those
> sections during your first real customer deploy.

---

## Where you'll work

You'll move between four places as you go through the lab. Every lab below opens with a **Where** line so you know which one to be in.

| Where | What you do there | How to open it |
|---|---|---|
| **Terminal / editor** | Run `accel`, edit files, review diffs, and use your chosen coding-agent client | `code .`, `copilot`, `codex`, or `claude` |
| **GitHub web (github.com)** | Watch Actions runs (optional in the lab; required for the real partner motion) | Your browser, on the cloned repo |
| **Azure portal (portal.azure.com)** | Inspect the resource group, App Insights logs and dashboards, Foundry quota | Your browser, signed into the same tenant `azd` deployed to |
| **Foundry portal (ai.azure.com)** | Visually confirm agents (Lab 5 demonstrates that portal edits get overwritten by spec files) | Your browser → https://ai.azure.com → sign in with the same tenant → select the project named in `azd env get-values` (look for `AZURE_AI_FOUNDRY_PROJECT_NAME`) → **Agents** in the left nav |

Lab 2 also has you open a local browser tab at `http://localhost:5173` for the running dev frontend — Vite opens it after `npm run dev`.

---

## Lab 1 — First deploy

**Where:** VS Code (integrated terminal for the `gh` / `az` / `azd` commands; editor to confirm the repo loaded with `.github/copilot-instructions.md`); Azure portal (portal.azure.com → your resource group) for the **Check your work** verification.

**Goal:** deploy the unmodified template to a sandbox and confirm the backend bootstrapped successfully. This is a backend smoke test — Lab 2 is where you exercise the workflow through the reference frontend.

1. Clone the template into your own private repo:

   ```bash
   # Replace <your-handle> with any short name (e.g., contoso-lab-accel becomes from <your-handle>=contoso)
   gh repo create <your-handle>-lab-accel --template Azure-Samples/agentic-ai-solution-accelerator --private --clone
   cd <your-handle>-lab-accel
   ```

   Then load the folder into your current VS Code window via **File → Open Folder** (`Ctrl+K Ctrl+O` on Windows/Linux, `Cmd+K Cmd+O` on macOS) and pick `<your-handle>-lab-accel`. If you're running these commands from a standalone shell instead, `code <your-handle>-lab-accel` opens it in a fresh window.

2. In VS Code, confirm Copilot Chat loads the repo's `.github/copilot-instructions.md`
   (you'll see it referenced in the chat sidebar). If it doesn't,
   Copilot is not going to enforce the partner guardrails — stop and
   fix before continuing.

3. Install, authenticate, preview, and deploy:

   **About preflight:** the partner motion in `QUICKSTART.md` Step 4 has you run
   `/configure-landing-zone` and `/deploy-to-env` before customer deployment. The lab skips
   both: it deploys Tier 1 (`standalone`) into a sandbox where evals run locally,
   so a GitHub Environment isn't required yet. You'll meet both custom agents during
   your first real customer deploy. Cross-reference `QUICKSTART.md` Step 4 for
   the production motion.

   ```bash
   az login
   # If your account spans multiple tenants/subscriptions, pin them explicitly
   # so azd inherits the right context:
   #   az login --tenant <sandbox-tenant-id>
   #   az account set --subscription <sandbox-subscription-id>
   azd auth login
   python -m pip install -e ".[dev]"
   accel environment list
   accel deploy --env dev --region <region> --dry-run
   accel deploy --env dev --region <region> --execute
   accel deploy --env dev --region <region> --execute --apply
   ```

   The approved apply runs `azd up`, provisioning Foundry, AI Search, Key Vault, Container
   Apps, App Insights, and the user-assigned MI. The Container App
   then runs its in-app bootstrap (`src/bootstrap.py`) at FastAPI
   startup to create/verify Foundry agents and seed the AI Search
   `accounts` index before `/healthz` returns 200. Expect ~10–15
   minutes total.

   Replace `<region>` with one that has `gpt-5-mini` `GlobalStandard` quota
   (verified in step 2 of [Prerequisites](#prerequisites)).

   > **If `/healthz` returns 503 / startup probe fails** immediately after Bicep finishes, that's typically RBAC propagation lag — the role assignments Bicep just created haven't fully propagated. The startup probe budget is 10 minutes (60 × 10s); in normal conditions this absorbs the lag without intervention. If the probe still fails after the budget, see Troubleshooting #5 in `docs/getting-started/setup-and-prereqs.md`.

**Check your work:**

This lab is a **backend smoke test**, not a workflow validation. Lab 2 is the first user-facing success signal.

- The deployment prints an API URL. Hit `/healthz` —
  expect 200 with `{"status":"ok","scenario":"sales-research"}`. This
  only proves the Container App booted and bootstrap completed; it
  does **not** prove `/research/stream` produces a usable briefing.
  That's Lab 2.
- In the Azure portal, open the resource group and confirm you have
  a Foundry AIServices account, a model deployment
  (`gpt-5-mini` by default) bound to the `accelerator-default-policy`
  content filter, an AI Search service with an `accounts` index,
  Key Vault, Container App, App Insights, and a user-assigned MI.
- If anything is missing, `docs/getting-started/setup-and-prereqs.md`
  "Troubleshooting — top 5" covers the common failure modes.

---

## Lab 2 — See it work in a browser

**Where:** VS Code (integrated terminal for `npm install` / `npm run dev`; editor for `.env`), then your browser at `http://localhost:5173` for the running frontend.

**Goal:** exercise the API the way a customer will — through a browser —
and confirm the streaming pipeline produces a usable briefing end-to-end.

The accelerator ships a reference frontend at
`patterns/sales-research-frontend/` — a minimal React + Vite + TypeScript
starter that consumes `POST /research/stream` directly. It is intentionally
plain: no auth, no state persistence, no UI framework. The customer's real
UX is the partner's value-add; this lab just proves the wiring.

**Steps:**

1. Grab the deployed API URL from the deployment output (or
   `azd env get-values | Select-String AZURE_CONTAINER_APP_URL`). You want
   the base URL — the pattern appends `/research/stream` itself.
2. From the repo root:

   ```bash
   cd patterns/sales-research-frontend
   cp .env.example .env
   # edit .env: VITE_API_BASE_URL=<deployed-api-url>
   npm install
   npm run dev
   ```

3. Open `http://localhost:5173`. The form is pre-filled with sensible
   defaults — click **Run research** and watch the streaming viewer light
   up with `status`, `partial`, and `final` events as the supervisor DAG
   executes. The result panel renders the aggregated briefing; toggle
   **Show raw JSON** to inspect the structured output.

**Check your work:**

**Primary success signal — this is the first time you're seeing the accelerator actually work end-to-end:**

- The form at `http://localhost:5173` loads with default values.
- Clicking **Run research** streams `status` → `partial` → `final` events
  into the live viewer (no errors in the browser console, no CORS rejection).
- The result panel renders a usable research briefing with citations. Toggle
  **Show raw JSON** to confirm the structured output matches the briefing.

If the stream stalls, errors, or returns an empty briefing, the workflow
has a problem that Lab 1's `/healthz` smoke test could not detect — most
common causes are model quota exhaustion, AI Search index seeding failure,
or a regression in `src/scenarios/sales_research/workflow.py`. Capture the
App Insights trace (Lab 3 walks this) before debugging.

**Deeper check (for partners customising the briefing shape):**

- Every event in the live stream maps to one yielded dict from
  `SalesResearchWorkflow.stream` (see `src/scenarios/sales_research/workflow.py`)
  or from the underlying `SupervisorDAG` (see `src/workflow/supervisor.py`).
  If a new event type appears in the stream that the UI doesn't recognise,
  add it to the `StreamEvent` union in `src/types/research.ts` and to the
  `describe()` switch in `StreamingViewer.tsx`.
- The final panel renders fields from the supervisor's
  `transform_response` (`src/scenarios/sales_research/agents/supervisor/transform.py`).
  If you customise the briefing shape for the customer, update
  `ResearchBriefing` and `ResultPanel.tsx` together.

**Going further:** see `patterns/sales-research-frontend/README.md` for the
SWA deploy flow (`swa deploy ./dist`) and the customisation map. For a real
customer engagement, plan auth (Entra ID via easy-auth on Container Apps or
App Gateway), state persistence, and an actual HITL approval surface before
the UI is customer-facing.

---

## Lab 3 — Read the telemetry

**Where:** Azure portal — sign in at https://portal.azure.com, navigate to your resource group (named `rg-<azd-env-name>`), then open the **Application Insights** resource inside it. **Logs** is in the left nav under "Monitoring"; **Workbooks** is in the same group.

**Goal:** correlate real browser traffic to App Insights events and understand
which dashboard panels require partner-wired emitters.

After clicking **Run research** in Lab 2, you have real traffic. Open App
Insights and trace it.

### Step 1 — Query the events stream

In App Insights → Logs, run:

```kql
traces
| where timestamp > ago(15m)
| where message in ("request.received","supervisor.routed","worker.completed",
                    "retrieval.returned","response.returned","tool.executed",
                    "tool.hitl_approved","tool.hitl_rejected","aggregator.composed")
| where isnotempty(customDimensions.event_name)
| project timestamp, message, operation_Id, operation_ParentId, customDimensions
| order by timestamp asc
```

You should see `request.received` → `supervisor.routed` →
one or more `worker.completed` → `retrieval.returned` →
`response.returned`. If the request actually routed through a
HITL-gated side-effect tool (`crm_write_contact`, `send_email`)
you'll also see `tool.executed` + a `tool.hitl_*` event — but
many flagship requests don't touch those tools, so don't treat
those two events as guaranteed per request. Which `tool.hitl_*`
variant fires depends on whether you set `HITL_APPROVER_ENDPOINT`
(prod) or `HITL_DEV_MODE=1` (dev-only).

> **Why `traces` and not `customEvents`?** Events are emitted by
> `src/accelerator_baseline/telemetry.py::emit_event`, which routes
> through the `accelerator` Python logger that
> `configure_azure_monitor(logger_name="accelerator")` pipes into App
> Insights. Log records land in `traces` (one row per event) with
> `message == event.name` and the event payload flattened into
> `customDimensions.<attr>`. The `isnotempty(customDimensions.event_name)`
> filter scopes the result set to accelerator events specifically, since
> `traces` also collects FastAPI/uvicorn/OTel internal log rows.

### Step 2 — Pivot one request across `requests` + `dependencies` + `traces`

The `operation_Id` column lets you correlate one stream call to its
parent `requests` row and any nested `dependencies`. Copy the **first
8 characters** of any `operation_Id` from the results above
(e.g. `89baea0c`) and paste them between the quotes in the query
below — replace only the `OPID_PREFIX_HERE` text:

```kql
let opPrefix = "OPID_PREFIX_HERE";
union requests, dependencies, traces
| where timestamp > ago(2h)
| where operation_Id startswith opPrefix
| project timestamp, itemType, name=coalesce(name, message), duration, success, customDimensions
| order by timestamp asc
```

> **Why a prefix and not the full ID?** The Logs UI display-truncates
> `operation_Id` with a trailing `…`, and that truncated string does
> not equal-match the real 32-char value. A prefix avoids the trap;
> 8 hex chars (≈ 4 billion combinations) is plenty unique within any
> realistic time window.

If you want to drive synthetic traffic without the UI, here's the
curl form:

```bash
curl -N -X POST "$API_URL/research/stream" \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Contoso","seller_intent":"Discovery call","persona":"VP of Operations"}'
```

### Step 3 — Import the ROI workbook

The repo ships `infra/dashboards/roi-kpis.json` as a paste-ready
Azure Monitor Workbook. To install it:

1. Still in your Application Insights resource, go to **Monitoring →
   Workbooks**.
2. Click **+ New** at the top of the gallery.
3. In the empty workbook, click the **Advanced Editor** icon (looks like
   `</>`) in the toolbar above the first item. The editor opens with a
   default template selected — leave the **Gallery Template** dropdown
   on its default value.
4. Select all the JSON in the editor, delete it, then paste the entire
   contents of `infra/dashboards/roi-kpis.json` from your repo.
5. Click **Apply** at the bottom of the editor. The workbook reloads
   with five panels.
6. Click **Done Editing**, then **Save** (disk icon top-left). Give it a
   name (e.g. `Accelerator ROI - <env>`) and pick a region.

All five panels should show data from your single smoke-test request:
"Responses by outcome" (one green bar — success), "Workflow runs"
(one routing decision), "Workers completed by agent" (one bar per
specialist that ran, e.g. `account_planner`, `news_signals`), and
"P95 end-to-end latency" (the orchestration time in seconds — read
the explainer above the chart for why this differs from the FastAPI
``requests`` table). "Latest failures and rejected actions" should be
empty unless the run hit an error — that's the panel to check first
when a smoke test misbehaves.

> **Note — what's deliberately missing.** The workbook does not ship
> a `$ per call` or `Groundedness eval score` panel. Both events
> (`cost.call` and `eval.result`) exist in the codebase but aren't
> emitted by live frontend traffic — cost-per-call requires partner-wired
> `record_call_cost(...)` calls and groundedness comes from
> `evals/quality/` runs in CI. Acceptance gates for both still live in
> `accelerator.yaml -> acceptance`. See `docs/customer-runbook.md`
> "What you inherited" and Section 3 (Operational dials) for the wiring
> path when you need them.

**Check your work:**

- Open each panel and read the markdown explainer that sits directly
  above the chart. Each one tells you what event populates it and how
  to interpret a red bar / unexpected gap.
- Force a failure (e.g. send a malformed payload via the curl in
  Step 2, or temporarily revoke the Foundry role assignment and
  retry) and confirm a red bar shows up in **Responses by outcome**
  and a row appears in **Latest failures and rejected actions** with
  the error message.

---

## Lab 4 — Run evals + acceptance (baseline)

**Where:** local terminal. The unified command runs all deterministic suites.

**Goal:** understand the two-step eval flow.

This is your **baseline** — every mutation lab from here on ends by re-running
this same chain.

1. From the repo root:

   ```powershell
   accel evaluate --api-url <your-api-url> --execute
   ```

   !!! note "First call may pause for ~30–60s"
       Each runner first polls `GET <api-url>/healthz` for up to 120s
       to wake a scale-to-zero Container Apps deployment. Without this,
       the very first eval case would hit cold-start and fail with
       `transport error`. You'll see `warming up endpoint via .../healthz...`
       on stderr; once the app responds, cases start streaming.

2. Read the acceptance output/artifact. It reports which
   thresholds from `accelerator.yaml.acceptance` passed or failed.
   The shipped thresholds are **baselined against the flagship
   sales-research scenario** (4-worker fan-out, ~150–180s, ~$0.45–
   $0.55). They exist to catch **regressions vs. your declared bar**,
   not to enforce a universal SLA. When you change scenarios, models,
   or worker count, **re-baseline them** to match the new reality.
3. Lower the `quality_threshold` in `accelerator.yaml` by 0.2 and
   re-run `accel evaluate`. Notice: the quality gate now
   passes trivially. **Revert** — loosening a gate to make CI green
   is the wrong move; the right move is either improving the workflow
   or *justifying* a new threshold in the brief.

**Check your work:**

- Look at the `cost_per_call_usd` line in the
  `enforce-acceptance.py` output. In the flagship scenario,
  `src/accelerator_baseline/cost.py::record_call_cost()` is not
  called from the workflow — but `evals/quality/run.py` still
  records a **best-effort** `cost_usd` per case (token-pricing
  if the workflow surfaces usage, latency-based fallback
  otherwise; see `evals/quality/run.py:107-134`). That means the
  gate produces a number from day one; it's just not a true
  workflow cost until a partner wires `record_call_cost` into the
  hot path.
- `src/accelerator_baseline/evals.py:66-75` is the branch that
  *does* fail hard — only if the runner is modified to omit
  `cost_usd` entirely. That's the "inert-is-a-failure" safety net.
- `docs/customer-runbook.md` Section 3 and Section 4 describe what a partner has
  to wire for the cost gate to reflect real model spend, not a
  latency proxy.

---

## Lab 5 — Edit an agent's instructions the supported way

**Where:** VS Code for the spec-file edit and `azd deploy` (integrated terminal), then the **Foundry portal** for the "your manual edit got overwritten" demo. To open the Foundry portal: https://ai.azure.com → sign in with the same tenant `azd` deployed to → select the project named in `azd env get-values` (`AZURE_AI_FOUNDRY_PROJECT_NAME`) → **Agents** in the left nav → click the agent → **Instructions** tab.

**Goal:** understand that the Foundry portal is not the source of
truth.

1. Open `docs/agent-specs/accel-sales-research-supervisor.md` (or
   whichever agent you want to tweak). This is the **repo-side
   source of truth** for the agent's instructions.
2. Make a small edit — change a guideline, add a sentence, whatever.
   Save.
3. Run `azd deploy`. The image rebuilds, the Container App rolls a
   new revision, and on startup `src/bootstrap.py` syncs the new
   Instructions into Foundry.
4. Now open the Foundry portal, find the same agent, and **manually
   edit** the instructions there. Save.
5. Run `azd deploy` again (or restart the Container App revision —
   Container Apps → Revisions → "Restart").

**Check your work:**

- Re-open the agent in the portal. Your manual edit is **gone** —
  overwritten by the spec file. This is the designed behavior:
  portal edits are transient. The supported rollback path for a
  bad prompt is `git revert` the spec + `azd deploy`, not
  "restore from Foundry portal history".
- `docs/customer-runbook.md` Section 6 (Model swap) is the condensed version of this
  behavior for the customer's ops team.

**Now re-run acceptance:**

```powershell
accel evaluate --api-url <your-api-url> --execute
```

Compare to your Lab 4 baseline. A prompt edit can move quality scores in either
direction; if a threshold drops below `accelerator.yaml.acceptance`, revert and
try again. The acceptance gate is the contract.

---

## Lab 6 — Swap the model

**Where:** Editor for `accelerator.yaml`; terminal for `accel deploy/evaluate`.

**Goal:** do a model swap the supported way.

1. Open `accelerator.yaml` and replace the `default: true` entry
   under `models:` with a different model your sandbox has quota
   for (e.g. `gpt-4.1-mini` instead of `gpt-5-mini`, with a valid
   `version` and a `capacity` within your quota).
2. Run `accel deploy --env dev --region <region> --execute --apply`. Bicep parses the new manifest at compile time
   (`loadYamlContent`), Foundry re-deploys the model in place, and
   on Container App restart `src/bootstrap.py` re-resolves the
   slug → deployment_name map.
3. Re-run the eval chain from Lab 4:

   ```powershell
   accel evaluate --api-url <your-api-url> --execute
   ```

   Quality may shift — that's the point. If a threshold drops, the model
   isn't a drop-in replacement.

**Check your work:**

- Try `azd env set AZURE_AI_FOUNDRY_MODEL_NAME=some-other-model`
  and re-run the approved `accel deploy` flow. Notice: Bicep ignores the env var entirely
  because the model now comes from `accelerator.yaml -> models[]`
  via `loadYamlContent` at compile time. Raw env-var overrides are
  unsupported; the manifest is the source of truth.

---

## Lab 7 — Add a side-effect tool with `/add-tool`

**Where:** VS Code — Copilot Chat sidebar for the custom agent, editor for any post-generation edits and the redteam case authoring, integrated terminal for `accelerator-lint.py` / `pytest` / the eval chain.

**Goal:** experience the scaffolded-with-HITL contract.

1. In Copilot Chat, invoke `/add-tool`. The custom agent (see
   `.github/agents/add-tool.agent.md`) asks for seven inputs:
   tool name, external system, operation, reversibility, HITL
   policy, which worker uses it, and auth approach.
2. Pick something plausible — e.g. create a ticket in a ticketing
   system, irreversible, `HITL_POLICY = "always"`, attached to an
   existing worker agent, Managed Identity auth.
3. Copilot generates `src/tools/<tool_name>.py` with HITL
   scaffolding and nudges you to register it on the appropriate
   worker, add a unit test, and add a redteam case under
   `evals/redteam/`. Confirm the worker registration actually
   landed — the custom agent instructs it but partners have to verify.
4. Run `python scripts/accelerator-lint.py` — it must report
   `0 blocking, 0 warning findings`.
5. Run `pytest -q` — the new test must pass.

### Author + run the redteam case

The `/add-tool` custom agent tells you to add a redteam case for the new tool — that's
the contract. Before calling the lab done, do both halves:

1. Add a case to `evals/redteam/cases.jsonl` exercising prompt-injection or
   jailbreak attempts to misuse the tool.
2. Run it:

   ```bash
   python evals/redteam/run.py --api-url <your-api-url>
   ```

Confirm your new case appears in the output and the safety bar in
`accelerator.yaml.acceptance.safety_pass` still holds.

### Now re-run acceptance

```powershell
accel evaluate --api-url <your-api-url> --execute
```

The redteam re-run picks up your new case; quality + acceptance ensure the tool
didn't regress the scenario.

**Check your work:**

- Remove the `checkpoint(...)` call from the tool and re-run lint.
  On any `src/tools/*.py` file that declares `HITL_POLICY`, the
  `hitl-required` rule fails loudly. Put `checkpoint(...)` back
  before continuing.
- Confirm the redteam case you authored above appears in `evals/redteam/run.py`'s
  output. The `safety_pass` threshold in `accelerator.yaml.acceptance` will
  block merge if any redteam case fails — including the one you just added.

---

## Lab 8 — Decide and scaffold a new scenario

**Where:** coding-agent client for discovery/specialist authoring; terminal for
`accel design/scaffold/validate`; editor for the generated diff.

**Goal:** understand the advisor evidence/override boundary, then use the
architecture-aware scaffold path.

1. In Copilot Chat, run `/discover-scenario` against a realistic
   sandbox scenario you make up (e.g. "summarize support tickets
   weekly"). Answer the questions. The custom agent writes
   `docs/discovery/solution-brief.md` and updates
   `accelerator.yaml` `solution.*`, `acceptance.*`, and `kpis[]`
   from your answers — it does **not** touch the `scenario:`
   block (that comes next).

2. Run:

   ```powershell
   accel design
   accel design --approved-by "Lab Partner Architect" --apply
   accel scaffold --scenario-id ticket-summary --dry-run
   accel scaffold --scenario-id ticket-summary --apply
   ```

   The CLI materialises
   `src/scenarios/ticket_summary/` (schema, workflow, retrieval,
   supervisor agent package) plus the supervisor spec stub at
   `docs/agent-specs/accel-ticket-summary-supervisor.md` and updates the
   manifest transactionally. Use specialist agents for the checklist below.

   Treat its output as a **guided checklist, not a finished
   implementation.** The scaffold gives you structure; the brief
   tells you what to fill in.

!!! info "Behind the scenes / fallback path"
    `accel scaffold` wraps `scripts/scaffold-scenario.py` and updates the
    manifest. For low-level debugging you may run the script directly, but its
    printed YAML then requires manual handling and is not the preferred path.

    ```bash
    python scripts/scaffold-scenario.py ticket-summary --display "Ticket Summary"
    ```


3. Walk the **brief → files** checklist below. The authoritative
   copy lives in `.github/agents/scaffold-from-brief.agent.md`
   — the condensed version here mirrors it for lab use. If the two
   ever diverge, update both in the same PR.

4. Run `accel validate --full --execute`. In a fresh scaffold,
   **all rules should pass `0 blocking, 0 warning findings`** — the
   scaffolder also seeded `evals/quality/golden_cases.jsonl` with a
   stub case (`q-001`, `exercises: ["supervisor"]`, `must_cite: false`,
   TODO query) so the `agent_has_golden_case` and
   `golden_cases_exercises_valid` rules pass immediately. Each
   `/add-worker-agent` run (via `scaffold-agent.py`) transparently
   appends the new agent id to that stub's `exercises` array, so lint
   stays green as you grow the scenario. The `prompt.py`,
   `transform.py`, `validate.py`, and `retrieval.py` are minimal
   placeholders, and the stub's `query`/`expected` are TODOs — the
   checklist below is what turns them into a real scenario.

### Brief → files checklist

| Brief area | Files to verify / customise |
|---|---|
| Problem + persona (Section 1) | `docs/agent-specs/<supervisor>.md` system instructions |
| UX contract (Sections 5b–5d) | Request/response Pydantic schemas + `scenario.experience` metadata |
| Solution shape (Section 5, if not supervisor-routing) | Re-shape `src/scenarios/<package>/workflow.py` for `single-agent` or `chat-with-actioning` |
| Grounding sources (Section 5) | `src/scenarios/<package>/retrieval.py` + declare indexes under `scenario.retrieval.indexes` |
| Side-effect tools + HITL (Section 5) | `src/tools/<tool_name>.py` (each wrapped in `hitl.checkpoint(...)`); `src/accelerator_baseline/hitl.py` per-tool rules |
| Constraints / controls (Section 6) | `infra/main.parameters.json` + `accelerator.yaml.controls.*` |
| Acceptance / evals (Sections 3 + 7) | `evals/quality/golden_cases.jsonl` (scaffolder seeded a stub `q-001` exercising every scaffolded worker — refine `query`/`expected` and grow the suite); `evals/redteam/cases.jsonl` (one case per RAI risk) |
| KPIs (Section 4) | Register each event in `src/accelerator_baseline/telemetry.py`; append a `KqlItem/1.0` per KPI to `infra/dashboards/roi-kpis.json` |
| Worker agents (if supervisor-routing) | Use `/add-worker-agent`, then `/define-grounding` (FoundryIQ + Search indexes + read-only catalog intent) and `/implement-workers`. |

**Check your work:**

- Open the generated prompt / transform / validate stubs under
  `src/scenarios/<package>/agents/supervisor/`. They're deliberate
  placeholders. The supervisor spec ships with generic baseline
  instructions that run as-is but aren't domain-aware — tighten
  those instructions for your scenario. Don't ship to a customer
  until real behaviour is authored, the supervisor spec reflects
  your domain, golden + redteam cases exist, and lint reports
  `0 blocking, 0 warning findings`.
- Decision rule: `accel scaffold` is the default structural path; specialist
  agents author behavior; the raw Python script is a debug fallback.

---

## Cleanup

```bash
azd down --purge
```

This tears down every resource in the lab environment. Do this
before closing the lab — a lingering Foundry deployment consumes
quota you might need for the next run.

---

## Where to go next

- Deploy the UI from Lab 2 to Azure Static Web Apps with `swa deploy ./dist`
  (`patterns/sales-research-frontend/README.md` has the full flow including
  `VITE_API_BASE_URL` for build-time API binding).
- Run the actual partner motion (`QUICKSTART.md` + `docs/partner-playbook.md`)
  against a scoped sandbox engagement — not a real customer — before
  taking the accelerator to a paying engagement.
- Read `docs/patterns/azure-ai-landing-zone/README.md` and run
  `/configure-landing-zone` against a Tier 2 `avm` overlay in your
  sandbox. Tier 3 `alz-integrated` requires a hub to peer to; if you
  don't have one, stop at Tier 2.
- Discovery artifacts live under `docs/discovery/` — five
  engagement artifacts (`use-case-canvas.md`,
  `SOLUTION-BRIEF-GUIDE.md`, `discovery-workbook.csv`,
  `solution-brief.md`, `roi-calculator.xlsx`) plus
  `how-to-use.md` as the sequencing meta-guide. Run
  `/discover-scenario` when you're ready to turn workshop notes
  into a filled brief.
- Contribution flow for external partners is documented at
  [`.github/CLA.md`](../../.github/CLA.md) — short version: on your
  first PR, a CLA bot comments with a link to
  <https://cla.opensource.microsoft.com>; sign once there and the
  `license/cla` status check turns green. Rely on the status check
  and the portal for the specific repo you're contributing to
  rather than assuming broad coverage. Partner private forks
  (outside the `microsoft`/`Azure` orgs) are outside Microsoft's
  CLA flow entirely; the bot only fires on upstream PRs.

---

## What this lab is not

- Customer training — partner-owned, separately
- A substitute for reading `docs/getting-started/setup-and-prereqs.md` and `QUICKSTART.md`
- Certification — there's no badge or quiz; the check-your-work
  gates exist so you notice your own gaps, not to score you
- A Tier 2 / Tier 3 networking lab — that's `/configure-landing-zone`
  territory and requires infrastructure beyond a dev sandbox
---

!!! info "← Back to the partner walkthrough"
    This page is the **full** lab guide. The walkthrough version (with hybrid one-line summaries + check-yourself prompts per lab) lives at [3. Rehearse in a sandbox](../start/ready/03-rehearse-in-a-sandbox.md).