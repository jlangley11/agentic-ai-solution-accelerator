# 5. Discover with the customer

*Step 5 of 10 · Deliver to a customer*

!!! info "Step at a glance"
    **🎯 Goal** — Run the workshop (or `/ingest-prd` if a PRD/BRD/spec exists) and fill `docs/discovery/solution-brief.md` with numeric success criteria, KPI events, RAI risks.

    **📋 Prerequisite** — [4. Clone for the customer](01-clone-for-the-customer.md) complete; customer stakeholder workshop scheduled or PRD in hand.

    **💻 Where you'll work** — Customer workshop room (or Teams) for the conversation; the cloned customer repo in VS Code + Copilot Chat to drive `/discover-scenario` after the workshop.

    **✅ Done when** — `docs/discovery/solution-brief.md` has zero `TBD`; success criteria are numeric (baseline → target with %); 3–6 KPI events named; solution shape chosen; 3–5 RAI risks listed; `accelerator.yaml` updated by the custom agent.

!!! tip "Custom agents used here"
    [`/ingest-prd`](../../../.github/agents/ingest-prd.agent.md) *(optional, if customer provided a PRD)* · [`/discover-scenario`](../../../.github/agents/discover-scenario.agent.md)

    Full reference: [Custom agents overview](../../agents-index.md).

---

The brief is the **single source of truth** for the engagement. Every downstream artifact — prompts, tools, retrieval schema, HITL gates, eval thresholds, dashboards — derives from it. A weak brief makes every later step harder.

## The five discovery artifacts

Five artifacts ship under `docs/discovery/`. Use them in this order:

| # | Artifact | Purpose | Who fills it |
|---|---|---|---|
| 1 | [`use-case-canvas.md`](../../discovery/use-case-canvas.md) | 1-page exec alignment before you spend workshop time | Partner lead + customer sponsor, async |
| 2 | [`SOLUTION-BRIEF-GUIDE.md`](../../discovery/SOLUTION-BRIEF-GUIDE.md) | How to run the workshop that fills the brief | Read by partner lead; optional coaching for junior facilitators |
| 3 | [`discovery-workbook.csv`](../../discovery/discovery-workbook.csv) — *download* | Structured capture during the live workshop | Partner facilitator (typing) + customer SMEs (answering) |
| 4 | [`solution-brief.md`](../../discovery/solution-brief.md) | Canonical engagement doc | Output of `/discover-scenario` |
| 5 | [`roi-calculator.xlsx`](../../discovery/roi-calculator.xlsx) — *download* | Quantifies the hypothesis in Section 4 of the brief | Partner lead, after Section 3 of the brief is filled |

## The flow

### Before the workshop

1. **Use-case canvas** — send to the customer sponsor after the first scoping call. If the sponsor can't fill it in ~30 minutes, the engagement isn't ready for a workshop. The canvas is a go/no-go gate, not a deliverable.

### If the customer already provided a PRD / BRD / functional spec

If the customer handed you a written spec **before** the workshop, you can pre-draft the brief from it instead of starting blank:

```
/ingest-prd
```

…in Copilot Chat, pointed at the file (path inside the cloned repo or local path). Supported formats: `.md`, `.txt`, `.docx`, text-extractable `.pdf`. The custom agent runs `scripts/extract-brief-from-doc.py`, maps evidence to the 7-section brief schema, and writes a **draft** `docs/discovery/solution-brief.md` with a `STATUS: AI-extracted draft` banner and per-section `<!-- evidence: ... -->` comment blocks.

Treat every CONFIRMED field as a hypothesis (the LLM read the PRD, not the customer). Run the workshop on the remaining `TBD`s.

The full PRD-ingestion flow lives in [Reference → Discovery how-to → "If the customer already provided a PRD"](../../discovery/how-to-use.md#if-the-customer-already-provided-a-prd--brd--functional-spec).

### During the workshop

2. **Discovery workbook** — the facilitator types answers into the CSV live. One question per row keeps the conversation disciplined. The workbook is *scaffolding*; it gets replaced by the solution brief after the session.

### Immediately after

3. **Solution brief** — in Copilot Chat:

   ```
   /discover-scenario
   ```

   The custom agent produces the 7-section brief at `docs/discovery/solution-brief.md` **and** updates `accelerator.yaml` fields (`solution.*`, `acceptance.*`, `kpis[]`). It does **not** touch `scenario:` — that comes from `/scaffold-from-brief` in the next step.

   If you ran `/ingest-prd` first, `/discover-scenario` detects the draft banner and enters **gap-fill mode** — asks only about `TBD` fields, preserves every confirmed field byte-for-byte, strips the banner and evidence comments on exit.

4. **ROI calculator** — open `docs/discovery/roi-calculator.xlsx`, fill blue cells on the `Inputs` sheet with numbers from brief Section 3 + Section 4. Read the `ROI` sheet for annual savings and payback; read the `KPIs` sheet for rendered baseline/target values.

### Before scaffolding

5. Walk the sponsor through the brief + ROI calculator together. If either has `TBD` fields or the ROI doesn't clear the customer's hurdle rate, **iterate before running `/scaffold-from-brief`**. A scaffold is expensive to redo; a discovery redo is cheap.

## What "good" looks like

- Every section filled — no `TBD` left when you exit the session.
- Success criteria are **numeric** (baseline → target, with %).
- 3–6 concrete KPI event names picked — these become typed telemetry events in `src/accelerator_baseline/telemetry.py` and App Insights alerts later.
- Solution pattern chosen: **supervisor-routing** (flagship default), **single-agent**, or **chat-with-actioning**.
- RAI risks listed as 3–5 concrete statements — these become redteam cases.

## What to push back on (workshop facilitation)

- *"We want it fast"* → "What's the current time, and what does 'fast enough' mean to the executive sponsor?"
- *"Just use AI Search"* → walk through the [Tool catalog](../../foundry-tool-catalog.md) to pick the right grounding tool (File Search vs Azure AI Search vs SharePoint vs Fabric — they each have different prereqs and auth stories).
- *"Skip HITL, we trust the model"* → walk the customer through the side-effect catalogue and ask which writes they're willing to defend without an approval trail.

## Honesty notes

- The canvas and workbook are discovery *capture*; they don't replace the solution brief. If you stop at the workbook, downstream automation (lint, scaffold, evals) won't have the structure it expects.
- The ROI calculator is a hypothesis tool at discovery. Real numbers come from running the accelerator against the customer's data during *Iterate & evaluate*. Expect to reconcile against measured performance before production sign-off.

---

**Continue →** [6. Scaffold from the brief](03-scaffold-from-the-brief.md)
