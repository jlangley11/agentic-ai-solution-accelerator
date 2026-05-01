# How to run the Solution Brief workshop

> A partner-facing guide to producing a complete `solution-brief.md` with a customer. Target: 2 hours with the right people in the room.

## Who must be there
- **Sponsor** — pays for it and owns the outcome
- **Process owner** — knows the current-state workflow in enough detail to describe one journey end-to-end
- **IT / security representative** — answers residency, identity, compliance
- **Partner lead** — drives the agenda; uses `/discover-scenario` live
- *Optional:* analytics owner (for KPI baselines), an actual end user

## Agenda (2 hours)

| Time | Section | Outcome |
|---|---|---|
| 0:00–0:15 | Context set | Shared understanding of what an agentic solution is and is not |
| 0:15–0:35 | 1. Business context | Problem statement agreed in one sentence |
| 0:35–0:55 | 2. Users & journeys | 3 journeys named; 1 chosen as the wedge |
| 0:55–1:15 | 3. Success criteria | Concrete metrics with current + target |
| 1:15–1:30 | 4. ROI hypothesis | Baseline cost + target savings + payback |
| 1:30–1:45 | 5. Solution shape | Pattern chosen; tools listed; HITL gates named |
| 1:45–1:55 | 6. Constraints & RAI | Residency, identity, compliance, 3–5 risks |
| 1:55–2:00 | Close | Next steps: `/scaffold-from-brief`, provisioning date |

Section 7 (acceptance evals) is derived post-workshop from sections 3 and 6.

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
- If there are ≥2 distinct capabilities (research · score · write · route), that's **supervisor-routing**.
- If there's one capability with simple Q&A + one write-back, **single-agent**.
- If the UX is a chat thread, **chat-with-actioning**.
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
2. `/scaffold-from-brief` applies it to the repo.
3. `azd up` to dev environment; smoke test.
4. First CI-gated PR iterates on the flagship prompt.
