# 8. Iterate & evaluate

*Step 8 of 10 · Deliver to a customer*

!!! info "Step at a glance"
    **🎯 Goal** — Customise prompts, tools, and retrieval; grow the eval suite; ship through PR-gated CI until acceptance thresholds from `accelerator.yaml` are green and KPI events are emitting in App Insights.

    **📋 Prerequisite** — [7. Provision the customer's Azure](04-provision-the-customers-azure.md) complete — `/healthz` returns 200; API URL captured. Recommended: 30-second smoke test in step 7 returned `✅ READY` (`python evals/quality/run.py --api-url <url> --smoke`) so you start this step from a known-good baseline.

    **💻 Where you'll work** — VS Code (Copilot Chat for the agent edits, integrated terminal for `git push`); GitHub web (PRs + Actions runs).

    **✅ Done when** — Quality evals ≥ acceptance thresholds in `accelerator.yaml`; redteam green; lint green; KPI events emitting in App Insights against real traffic.

!!! tip "Custom agents used here"
    [`/add-tool`](../../../.github/agents/add-tool.agent.md) · [`/add-worker-agent`](../../../.github/agents/add-worker-agent.agent.md) · [`/implement-worker`](../../../.github/agents/implement-worker.agent.md) · [`/explain-change`](../../../.github/agents/explain-change.agent.md) · [`/switch-to-variant`](../../../.github/agents/switch-to-variant.agent.md)

    Full reference: [Custom agents overview](../../agents-index.md).

??? success "What success looks like"
    `python scripts/enforce-acceptance.py` against the customer environment finishes with:

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

```bash
# Replace <api-url> with the URL azd up printed in step 7
python evals/quality/run.py --api-url <api-url>
python evals/redteam/run.py --api-url <api-url>
python scripts/enforce-acceptance.py
```

`enforce-acceptance.py` reports pass / fail against every threshold in `accelerator.yaml.acceptance` (quality, groundedness, safety, P50/P95 latency, cost per call). If a threshold fails on the unmodified flagship, fix the deploy first — quotas, model region, or grounding seed are the usual culprits — before authoring scenario-specific changes.

Capture the output (a screenshot or `> baseline.txt` in the customer fork) so the team has a reference when later PRs move a number.

## Iterate with Copilot

In VS Code, just talk to Copilot:

> *"Add a tool to create a ticket in ServiceNow; it should require HITL for anything with priority high."*

Copilot follows `.github/copilot-instructions.md` — creates `src/tools/servicenow_ticket.py` with HITL scaffolding, registers it on the right worker agent, adds a unit test, and adds a redteam case.

For agent edits, edit the spec markdown:

```
docs/agent-specs/<agent>.md   # ## Instructions section
```

…then `azd provision` (or the next `azd up`) syncs the spec to Foundry.

!!! warning "Never edit instructions in the Foundry portal"
    `bootstrap.py` overwrites portal drift on next start. Edit `docs/agent-specs/<agent>.md` and re-provision instead.

For new specialist workers, use the scaffolder:

```bash
python scripts/scaffold-agent.py <agent_id> --scenario <scenario-id> \
  --capability "<one-sentence capability>" [--depends-on a,b]
```

The scaffolder appends to the declarative `WORKERS` registry in `src/scenarios/<id>/workflow.py`, creates the three-layer files (`prompt.py`, `transform.py`, `validate.py`), writes a Foundry agent spec stub, **and appends the new agent id to every existing case's `exercises` array in `evals/quality/golden_cases.jsonl`** so the `agent_has_golden_case` lint rule stays green automatically. It is transactional and re-run safe; refine each case's `query` and `expected` to actually exercise the new worker before the next eval run.

Then fill the stubs with `/implement-worker <worker_id>` (single worker) or `/implement-workers` (every scaffolded-but-unfinished worker, walked in dependency order). Both read the brief + the worker's manifest entry and produce real `prompt.py` / `transform.py` / `validate.py` + Foundry agent spec — no manual three-layer authoring required.

## Ship through CI

```bash
git checkout -b feat/servicenow-tool
git add -A && git commit -m "Add ServiceNow tool"
gh pr create
```

The PR triggers four gates:

1. **`scripts/accelerator-lint.py`** — 30 deterministic rules.
2. **`evals/quality/`** — must clear thresholds in `accelerator.yaml -> acceptance`.
3. **`evals/redteam/`** — XPIA + jailbreak must pass; new tools trigger new cases.
4. **build + type check** — `ruff` + `pyright`.

Any red light blocks merge. Green = `azd deploy` against the customer environment via the GitHub Environment registered in step 7.

## Watch the dashboard

Open Azure portal → the customer's resource group → Application Insights → Workbooks. The KPI events declared in `accelerator.yaml -> kpis` are pre-wired to dashboard panels (`infra/dashboards/roi-kpis.json`). Send real traffic against `/research/stream` (or your scenario's endpoint) and confirm the panels light up.

If a panel stays empty, check that `src/accelerator_baseline/telemetry.py` actually emits the event name declared in the manifest. The lint rule `kpis_emitted_in_code` catches missing emitters at PR time.

## Optional — ship a UI for UAT demos

The shipped API is SSE-only. Many partner teams stand up a quick reference UI for UAT walkthroughs:

```bash
cd patterns/sales-research-frontend
npm install
npm run dev
# or `swa deploy` to Azure Static Web Apps
```

The starter is a minimal React + Vite + TypeScript SSE consumer — reference material, not a finished product. The customer's real UX is the partner's value-add. Before customer-facing UI ships, also wire end-user auth (Easy Auth / App Gateway / Front Door), state persistence (Cosmos / Postgres / Redis) and the HITL approval surface (Logic Apps / Teams / ServiceNow that `HITL_APPROVER_ENDPOINT` resolves to). The full ownership boundary lives in [Reference → Delivery context → Partner playbook](../../partner-playbook.md#what-the-accelerator-gives-you-vs-what-you-still-own).

→ [Reference → Frontend starter](../../../patterns/sales-research-frontend/README.md)

## Need a different shape?

The variants are **manual re-authoring walkthroughs** (documented in `patterns/<variant>/README.md`), not drop-in packages:

```
/switch-to-variant
```

…in Copilot Chat — pick `single-agent` (no supervisor) or `chat-with-actioning` (conversational front-end). For a **different business scenario**, see [Reference → Reference scenarios → Customer service actioning](../../references/customer-service-actioning/README.md) or [RFP response](../../references/rfp-response/README.md) for full walkthroughs.

---

**Continue →** [9. UAT & handover](06-uat-and-handover.md)
