# Discovery artifacts — how they fit together

> **Following the partner walkthrough?** This page is the deep dive for *Deliver to a customer → 2. Discover with the customer*. If you haven't started there, [open the walkthrough](../start/deliver/02-discover-with-the-customer.md) — it ties this content to the rest of the engagement flow.

Five artifacts ship under `docs/discovery/` for the pre-sales through
kickoff arc of a partner engagement. Each serves one job. Use them in
this order; skipping steps is how engagements end up with a brief that
reads well but doesn't tie to measurable ROI.

## The five artifacts

| # | Artifact | Purpose | Who fills it |
|---|---|---|---|
| 1 | [`use-case-canvas.md`](use-case-canvas.md) | 1-page exec alignment before you spend workshop time | Partner lead + customer sponsor, async |
| 2 | [`SOLUTION-BRIEF-GUIDE.md`](SOLUTION-BRIEF-GUIDE.md) | How to run the discovery workshop that fills the brief | Read by partner lead; optional coaching for junior facilitators |
| 3 | [`discovery-workbook.csv`](discovery-workbook.csv) — *download* | Structured capture during the live workshop | Partner facilitator (typing) + customer SMEs (answering) |
| 4 | [`solution-brief.md`](solution-brief.md) | Canonical engagement doc — every downstream artifact derives from it | Output of `/discover-scenario` Copilot custom agent (or manually from workbook) |
| 5 | [`roi-calculator.xlsx`](roi-calculator.xlsx) — *download* | Quantifies the hypothesis in Section 4 of the brief | Partner lead, after Section 3 of the brief is filled |

> **Downloads:** the workbook ([`discovery-workbook.csv`](discovery-workbook.csv)) and ROI calculator ([`roi-calculator.xlsx`](roi-calculator.xlsx)) are partner-fillable templates — click to download, fork per engagement.

## When to use which

### Before the workshop

1. **Use-case canvas** — send to the customer sponsor after the first
   scoping call. If the sponsor can't fill it in ~30 minutes, the
   engagement isn't ready for a workshop. The canvas is a go/no-go
   gate, not a deliverable.
   - **Where:** sponsor's editor of choice (Word, Notion, Google Doc, or VS Code) — async. The shipped `use-case-canvas.md` is a Markdown template; fork it per engagement.

### If the customer already provided a PRD / BRD / functional spec

If the customer handed you a written spec (PRD, BRD, functional spec,
solution design doc, etc.) **before** the workshop, you can pre-draft
the solution brief from it instead of starting blank. This reduces
workshop time to confirming gaps rather than building from scratch.

Supported source formats: `.md`, `.txt`, `.docx`,
text-extractable `.pdf` (scanned PDFs must be OCR'd first).

Flow:

1. **Run `/ingest-prd`** in Copilot Chat and give it the file path.
   - **Where:** GitHub Copilot Chat sidebar in VS Code — point Copilot at the PRD/BRD file already in your repo or a local path.
   The custom agent invokes `scripts/extract-brief-from-doc.py`, maps
   evidence to the 7-section brief schema, and writes a **draft**
   `docs/discovery/solution-brief.md` with:
   - A `> **STATUS: AI-extracted draft**` banner at the top.
   - Per-section `<!-- evidence: ... -->` HTML comment blocks with a
     verbatim quote + citation (`chunk_id`, plus `page` for PDFs) for
     every non-TBD field.
   - Risky fields (solution pattern, HITL gates, side-effect tools,
     KPI event names, RAI risks, acceptance thresholds) set to `TBD`
     unless the source contains explicit evidence — **not** inferred.
   - A self-audit table + spot-check prompt before the draft is
     written; answer "go" only after verifying the quoted evidence
     against the source doc.
2. **Review the draft** with the customer sponsor. Treat CONFIRMED
   fields as hypotheses (the LLM read the PRD, not the customer).
   Flag anything the PRD got wrong or that's stale.
3. **Run the workshop** using the remaining `TBD`s as the agenda. The
   canvas + workbook are still useful — but now they're focused on
   gaps rather than full intake.
4. **Run `/discover-scenario`** after the workshop (or live during
   it). It will detect the draft banner and enter **gap-fill mode**:
   - Asks **only** about `TBD` fields.
   - Preserves every confirmed field byte-for-byte.
   - On exit, strips the `STATUS: AI-extracted draft` banner **and**
     every `<!-- evidence -->` block before copying values into
     `accelerator.yaml` (`solution.*`, `acceptance.*`, `kpis[]`).
5. **Quantify the hypothesis** in `roi-calculator.xlsx` once the
   brief's Section 3 and Section 4 are final.

What `/ingest-prd` does **not** do:
- Update `accelerator.yaml`. That's `/discover-scenario` gap-fill's
  job, after the TBDs are resolved.
- Run `/scaffold-from-brief`. The draft banner explicitly blocks that
  until a human has reviewed every field.
- Replace the workshop. It replaces the blank-page phase of the
  workshop, not the conversation with the customer sponsor.

### During the workshop

2. **Discovery workbook** — the facilitator types answers into the CSV
   live. One question per row keeps the conversation disciplined. The
   workbook is *scaffolding*; it gets replaced by the solution brief
   after the session.
   - **Where:** customer workshop room (or Teams) for the conversation; VS Code or Excel for the facilitator typing into `discovery-workbook.csv`.

### Immediately after

3. **Solution brief** — run `/discover-scenario` in Copilot Chat with
   the filled workbook as context (paste it, or point Copilot at the
   file). The custom agent produces the 7-section brief at
   `docs/discovery/solution-brief.md` **and** updates
   `accelerator.yaml` fields (`solution.*`, `acceptance.*`, `kpis[]`).
   It does **not** touch `scenario:` — that comes from
   `/scaffold-from-brief` + `scripts/scaffold-scenario.py` in the
   scaffold stage.
   - **Where:** GitHub Copilot Chat sidebar in VS Code.

4. **ROI calculator** — open `roi-calculator.xlsx`, fill blue cells on
   the `Inputs` sheet with numbers from brief Section 3 + Section 4. Read the `ROI`
   sheet for annual savings and payback; read the `KPIs` sheet for
   rendered baseline/target values and a copy guide that mirrors the
   `accelerator.yaml:kpis` schema. The block is a copy guide, not
   paste-ready — Excel does not expand cell addresses into text when
   copied.
   - **Where:** Excel (or compatible — Numbers, LibreOffice Calc); the file lives at `docs/discovery/roi-calculator.xlsx` in the repo.

### Before scaffolding

5. Walk the sponsor through the brief + ROI calculator together. If
   either has TBD fields or the ROI doesn't clear the customer's
   hurdle rate, iterate before running `/scaffold-from-brief`. A
   scaffold is expensive to redo; a discovery redo is cheap.

## What ships in the repo vs what's engagement-specific

**Ships in the repo (template):**
- Every file in `docs/discovery/` is a **template** partners fork per
  engagement. `solution-brief.md` and `roi-calculator.xlsx` ship
  unfilled.
- The files ship with the flagship (sales-research) scenario's
  defaults as sample values where useful, but treat those as
  placeholders.

**Engagement-specific (partner fills):**
- Customer name, sponsor, numbers, KPIs, thresholds.
- At handover, archive the filled copies with the customer engagement
  (your delivery workspace, not this template repo).

## Honesty notes

- The canvas and workbook are discovery *capture*; they don't replace
  the solution brief. If you stop at the workbook, downstream
  automation (lint, scaffold, evals) won't have the structure it
  expects.
- The ROI calculator is a hypothesis tool at discovery. Real numbers
  come from running the accelerator against the customer's data
  during iteration + UAT (partner playbook stages 4–5). Expect to
  reconcile against measured performance before production sign-off.
- `duration_ms` and `ratio` are the only KPI types wired into
  `src/accelerator_baseline/telemetry.py` today. Other types are
  partner-authored.
- The workbook .csv is plain text specifically so it diffs cleanly in
  PRs and Copilot can read it. If the customer prefers a "real"
  workshop template (.xlsx, OneNote, etc.), fork locally — don't
  bloat the template repo.

## Related

- `docs/partner-playbook.md` stage 1 drives the partner motion across
  these artifacts end-to-end.
- `docs/enablement/hands-on-lab.md` is the sandbox rehearsal; Lab 8
  walks a partner engineer through `/discover-scenario` +
  `scaffold-scenario.py`.
- `.github/agents/discover-scenario.agent.md` is the custom agent
  that produces the solution brief from workshop notes or live.
- `.github/agents/ingest-prd.agent.md` is the custom agent that
  pre-drafts the solution brief from a customer PRD/BRD/spec;
  `/discover-scenario` gap-fill mode then fills the TBDs it leaves.

---

## Next step

You now have a discovery brief (and, if you ran the ROI calculator, a
quantified hypothesis). **Continue to** [*3. Scaffold from the brief*](../start/deliver/03-scaffold-from-the-brief.md)
in the partner walkthrough to turn the brief into code, infra, evals,
and telemetry. The brief is the input to `/scaffold-from-brief`;
everything downstream (lint, evals, dashboards) keys off its fields.

> Assumes you've already cloned the customer repo (walkthrough step
> *Deliver → 1. Clone for the customer*). If you haven't, do that first
> — `/scaffold-from-brief` runs against the cloned repo.

---

!!! info "← Back to the partner walkthrough"
    This page is the **full** discovery guide. The walkthrough version (with the per-engagement step-by-step) lives at [5. Discover with the customer](../start/deliver/02-discover-with-the-customer.md).