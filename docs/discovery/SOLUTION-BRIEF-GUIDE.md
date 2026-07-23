# How to run the Solution Brief workshop

> A partner-facing guide to producing a complete `solution-brief.md` with a customer. Target: 2 hours with the right people in the room.

## Who must be there
- **Sponsor** — pays for it and owns the outcome
- **Process owner** — knows the current-state workflow in enough detail to describe one journey end-to-end
- **IT / security representative** — answers residency, identity, compliance
- **Partner lead** — drives the agenda; uses `accel discover` plus the
  discovery specialist live
- *Optional:* analytics owner (for KPI baselines), an actual end user

## Agenda (2 hours)

| Time | Section | Outcome |
|---|---|---|
| 0:00–0:15 | Context set | Shared understanding of what an agentic solution is and is not |
| 0:15–0:35 | 1. Business context | Problem statement agreed in one sentence |
| 0:35–0:55 | 2. Users & journeys | 3 journeys named; 1 chosen as the wedge |
| 0:55–1:15 | 3. Success criteria | Concrete metrics with current + target |
| 1:15–1:30 | 4. ROI hypothesis | Baseline cost + target savings + payback |
| 1:30–1:45 | 5. Solution requirements | Architecture signals captured; tools listed; HITL gates named |
| 1:45–1:55 | 6. Constraints & RAI | Residency, identity, compliance, 3–5 risks |
| 1:55–2:00 | Close | Next steps: Architecture Advisor review, scaffold, provisioning date |

Section 7 (acceptance evals) is derived post-workshop from sections 3 and 6.
Customer documents can be registered through `accel intake` as Markdown, text,
CSV, DOCX, text-layer PDF, PPTX, XLSX, or XLSM. They remain local-only until an
explicit disclosure decision; scanned PDFs require OCR.

## How to run each section well

### 1. Business context
Force a one-sentence problem statement. If you can't say it in a sentence, you're not ready to build. Example: *"Procurement analysts spend 4–6 hrs per supplier review, creating a 200-case backlog and slowing sourcing decisions."*

### 2. Users & journeys
Draw a workflow on a whiteboard. Pick **one** journey to build for in v1 — not all three.

### 3. Success criteria
Push hard against vagueness. "Faster" isn't a criterion; "4 hours → 30 minutes" is. If the customer can't answer the "how will you measure it?" question, we'll build the wrong thing. It's okay to note "baseline will be instrumented in dev sandbox first" and return here.

### 4. ROI hypothesis
Work it through aloud: baseline FTE count × loaded rate × proportion of time on the journey = baseline cost. Target savings = baseline × (1 − 1/productivity_multiplier). Name the KPI **events** — these will be emitted by the agent as typed telemetry; they become the customer's monthly value-review deck.

### 5. Solution shape
- If capabilities require independently validated specialist contracts,
  parallel ownership, or explicit aggregation, that's **supervisor-routing**.
- If there's one capability with simple Q&A + one write-back, **single-agent**.
- If the UX is a chat thread, **chat-with-actioning**.
- If a single agent must plan and execute adaptive, long-running work with
  todos, in-run history, context management, or several custom tools, capture those
  signals for the **Harness** recommendation.
- If steps, retries, aggregation, or worker ordering must remain deterministic,
  capture them for **custom-workflow**, not Harness.
- Durable cross-request session state or persistent files also require
  **custom-workflow** until the engagement defines a governed state store.
List every side-effect tool. Every one gets HITL by default; only mark HITL `never` if the action is fully reversible AND the customer explicitly accepts the risk.

### 6. Constraints & risks
Residency and identity are often non-negotiable and shape infra. RAI risks must be specific — "hallucination" is not a risk, "agent fabricates a supplier's compliance status" is.

### 7. Acceptance evals (post-workshop)
Turn every success metric into a golden-case assertion. Turn every RAI risk into a redteam case. Set thresholds the engagement will be measured against.

## Pitfalls
- **Building a chatbot:** if section 5 doesn't list a side-effect tool, you're probably building a chatbot. Challenge the scope.
- **KPIs without instrumentation plan:** every KPI must map to a named event. If it can't be measured, drop it or change it.
- **HITL optional:** HITL is a template default. Removing it needs explicit sign-off in section 6.
- **Scope creep:** one journey in v1. Park the rest in `docs/references/` or a v2 brief.

## After the workshop
1. `/discover-scenario` will have produced the brief. Review it with the sponsor.
2. Run `accel design`; review prompt versus Hosted fit, orchestration,
   application shell, deployment target, evidence, and alternatives. Approve or
   document an override.
3. Preview and approve `accel scaffold`.
4. Use the grounding/worker specialists when the approved architecture needs
   workers, then apply `accel deploy` to dev and
   run a smoke evaluation.
5. First CI-gated PR iterates on the selected primary/supervisor behavior.
