# 8. Iterate & evaluate

*Step 8 of 10 · Deliver to a customer*

!!! info "Step at a glance"
    **🎯 Goal** — Customise prompts, tools, and retrieval; grow the eval suite; ship through PR-gated CI until acceptance thresholds from `accelerator.yaml` are green and KPI events are emitting in App Insights.

    **📋 Prerequisite** — deployment healthy, API URL captured, and smoke
    evaluation green.

    **💻 Where you'll work** — Your coding-agent client/editor, local terminal,
    and GitHub web for PRs and Actions.

    **✅ Done when** — Quality evals ≥ acceptance thresholds in `accelerator.yaml`; redteam green; lint green; KPI events emitting in App Insights against real traffic.

!!! tip "Custom agents used here"
    [`/add-tool`](../../../.github/agents/add-tool.agent.md) · [`/add-worker-agent`](../../../.github/agents/add-worker-agent.agent.md) · [`/implement-worker`](../../../.github/agents/implement-worker.agent.md) · [`/explain-change`](../../../.github/agents/explain-change.agent.md) · [`/switch-to-variant`](../../../.github/agents/switch-to-variant.agent.md)

    Full reference: [Custom agents overview](../../agents-index.md).

??? success "What success looks like"
    `accel evaluate --api-url <url> --execute` reports acceptance and writes
    the local acceptance artifact.

    ```
    ✅ All acceptance thresholds met for env=<customer>-dev
       quality       0.92  ≥ 0.85
       groundedness  0.96  ≥ 0.90
       safety        1.00  ≥ 1.00
       latency_p95   2.1s  ≤ 3.0s
       cost_per_call $0.018 ≤ $0.025
    ```

    Your PR's GitHub Actions tab shows four green checks: `accelerator-lint` · `evals/quality` · `evals/redteam` · `build`.

    App Insights → Workbooks → ROI KPIs panels are populated against real `/research/stream` traffic (no empty cards).

---

## Establish the acceptance baseline first

Before any custom changes, run the acceptance chain once against the freshly deployed flagship. Those numbers are the engagement's **known-good starting point** — every subsequent PR has to clear this same bar.

```powershell
accel evaluate --api-url <api-url>
accel evaluate --api-url <api-url> --execute
```

The unified evaluator reports every threshold in
`accelerator.yaml.acceptance`. If the unmodified flagship misses, fix the
deployment before authoring scenario-specific changes.

The result is captured under `.accelerator/artifacts/acceptance-report.json`
for the subsequent UAT report.

## Iterate with a coding agent

Use your selected coding-agent client:

> *"Add a tool to create a ticket in ServiceNow; it should require HITL for anything with priority high."*

The agent follows `AGENTS.md` (and its client-specific adapter), using
`/add-tool` when available.

For agent edits, edit the spec markdown:

```
docs/agent-specs/<agent>.md   # ## Instructions section
```

…then the next target-aware deployment syncs the spec to Foundry.

!!! warning "Never edit instructions in the Foundry portal"
    Shared provisioning overwrites portal drift. Edit
    `docs/agent-specs/<agent>.md` and deploy instead.

For new specialist workers, use `/add-worker-agent`. Its low-level mechanism is:

```bash
python scripts/scaffold-agent.py <agent_id> --scenario <scenario-id> \
  --capability "<one-sentence capability>" [--depends-on a,b]
```

The scaffolder appends to the declarative `WORKERS` registry in `src/scenarios/<id>/workflow.py`, creates the three-layer files (`prompt.py`, `transform.py`, `validate.py`), writes a Foundry agent spec stub, **and appends the new agent id to every existing case's `exercises` array in `evals/quality/golden_cases.jsonl`** so the `agent_has_golden_case` lint rule stays green automatically. It is transactional and re-run safe; refine each case's `query` and `expected` to actually exercise the new worker before the next eval run.

Then fill the stubs with `/implement-worker` or `/implement-workers`. Run
`accel review` and `accel validate --full --execute` before opening the PR.

## Ship through CI

```bash
git checkout -b feat/servicenow-tool
git add -A && git commit -m "Add ServiceNow tool"
gh pr create
```

The PR triggers four gates:

1. **`scripts/accelerator-lint.py`** — deterministic policy checks.
2. **`evals/quality/`** — must clear thresholds in `accelerator.yaml -> acceptance`.
3. **`evals/redteam/`** — XPIA + jailbreak must pass; new tools trigger new cases.
4. **build + type check** — `ruff` + `pyright`.

Any red light blocks merge. Green allows the target-aware deployment workflow
for the customer environment registered in step 7.

## Watch the dashboard

Open Azure portal → the customer's resource group → Application Insights → Workbooks. The KPI events declared in `accelerator.yaml -> kpis` are pre-wired to dashboard panels (`infra/dashboards/roi-kpis.json`). Send real traffic against `/research/stream` (or your scenario's endpoint) and confirm the panels light up.

If a panel stays empty, check that `src/accelerator_baseline/telemetry.py` actually emits the event name declared in the manifest. The lint rule `kpis_emitted_in_code` catches missing emitters at PR time.

## Optional — ship a UI for UAT demos

The shipped API is SSE-only. Many partner teams stand up a quick reference UI for UAT walkthroughs:

```bash
cd patterns/sales-research-frontend
npm install
npm test
npm run typecheck
npm run dev
# or `swa deploy` to Azure Static Web Apps
```

The workbench keeps the tailored sales UX and generates generic forms/results
from `/scenario/metadata`. It renders only final or explicitly validated
partial output. Production auth, durable multi-user state, branding, and the
external HITL approval surface remain customer deployment work.

→ [Reference → Frontend starter](../../../patterns/sales-research-frontend/README.md)

## Need a different shape?

The variants are **manual re-authoring walkthroughs** (documented in `patterns/<variant>/README.md`), not drop-in packages:

```
/switch-to-variant
```

…in Copilot Chat — pick `single-agent` (no supervisor) or `chat-with-actioning` (conversational front-end). For a **different business scenario**, see [Reference → Reference scenarios → Customer service actioning](../../references/customer-service-actioning/README.md) or [RFP response](../../references/rfp-response/README.md) for full walkthroughs.

---

**Continue →** [9. UAT & handover](06-uat-and-handover.md)
