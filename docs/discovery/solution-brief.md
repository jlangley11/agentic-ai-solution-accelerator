# Solution Brief — <Customer>

> **STATUS: TEMPLATE.** This is the unmodified template shipped with the accelerator. Fill it via `/discover-scenario` (or `/ingest-prd` then `/discover-scenario` for gap-fill). The custom agents overwrite this banner on completion; lint exempts the brief while the banner is present.

<!-- Template-fill marker: Replace `<customer-slug>` with the engagement slug (e.g., contoso-q4-research) and `<Customer>` with the customer display name. -->

> This document records the **customer-approved intent** for the engagement.
> `accelerator.yaml` is the executable scenario/deployment contract, and the
> private evidence ledger records provenance and requirement decisions. Fill
> the brief during discovery, then use `accel design` and the preview/apply
> scaffold flow to reconcile intent with implementation.

**Engagement:** `<customer-slug>`
**Status:** Draft / Reviewed / Approved
**Last updated:** `<YYYY-MM-DD>`

---

## 1. Business context
- **Industry / segment:**
- **Customer name + size:**
- **Executive sponsor:**
- **Decision maker:**
- **Problem statement (one sentence):**
- **In scope:**
  - …
- **Out of scope (explicit):**
  - …

## 2. Target users & journeys
- **Primary persona:** (role · daily workflow · tools they live in)
- **Secondary persona (if any):**
- **Top 3 user journeys:**
  1. …
  2. …
  3. …

## 3. Success criteria (measurable)
| Metric | Current | Target | How measured |
|---|---|---|---|
| Time per task |  |  |  |
| Volume / throughput |  |  |  |
| Quality bar |  |  |  |

**Must-not-do guardrails:**
- …

## 4. ROI hypothesis
- **Baseline cost of status quo:** (FTE × rate, or $/transaction × volume)
- **Target savings ($/yr):**
- **Payback target:**
- **KPIs to instrument** (these become telemetry events in `src/accelerator_baseline/telemetry.py` and charts in `infra/dashboards/roi-kpis.json`):

| KPI event name | Type | Baseline | Target |
|---|---|---|---|
| `e.g. review_completion_time_ms` | duration_ms |  |  |
| `e.g. escalation_rate` | ratio |  |  |

## 5. Solution shape
- **Pattern:** supervisor-routing / deterministic-workflow / single-agent / chat-with-actioning
- **Rationale:**
- **Agent autonomy:** bounded response / adaptive plan-and-execute / deterministic steps
- **Runtime needs:** todos / session history / context compaction / custom tools / none
- **Grounding sources:** SharePoint / SQL / APIs / blob / other
- **Side-effect tools (list every one):**

  | Tool name | External system | Operation | Reversible? | HITL policy |
  |---|---|---|---|---|
  |  |  |  |  |  |

- **Out-of-scope tools (explicit):**

## 5a. Foundry architecture decision

`accel design` produces the recommendation after requirements are approved.
Record the reviewed decision rather than treating orchestration and hosting as
the same choice.

- **Foundry agent type:** prompt-agent / hosted-agent
- **Implementation pattern:** managed-prompt / harness / custom-workflow
- **Orchestration pattern:** single-agent / deterministic-workflow / supervisor-routing
- **Application shell:** none / existing-app / workbench / custom
- **Deployment target:** foundry-prompt / hosted-preview / selfhost
- **Advisor confidence:**
- **Recommendation rationale:**
- **Alternatives considered:**
- **Partner decision:** Accept / Override
- **Override reason (required when overridden):**
- **Approved by / date:**

> Workflow is an orchestration pattern, not a third Foundry Agent Service
> runtime type. Prompt agents and Hosted agents are the Agent Service types.
> Harness is an Agent Framework implementation pattern for adaptive Hosted
> single-agent work; it is not a third Agent Service type or an orchestration
> pattern.

## 5b. UX shape
- **`ux_shape`:** TBD — pick one of:
  - **Structured form + report** — user fills a form, agent produces a structured briefing/analysis. *Next step: fork `patterns/sales-research-frontend/` as your starter and adapt the form to your scenario's request schema.*
  - **Chat** — multi-turn conversational UX. *No chat UI pattern shipped yet; the `chat-with-actioning` backend pattern supports this shape — you build the UI on top (or use any chat UI framework).*
  - **Dashboard / viewer** — agent output renders in the customer's existing app. *No UI pattern needed from the accelerator — consume the SSE endpoint directly from the customer's app.*
  - **API-only / embed** — another system calls the agent programmatically (Power Automate, n8n, partner platform). *No UI. The accelerator's hosted SSE endpoint IS the deliverable.*
- **Rationale (one line):**

## 5c. UX inputs
*Filled only when `ux_shape` is `Structured form + report`. Each row should match a field in `src/scenarios/<pkg>/schema.py` (`ScenarioRequest`).*

| Field | Type | Description | Required |
|---|---|---|---|
| TBD | text | TBD | yes |

## 5d. UX output sections
*Filled only when `ux_shape` is `Structured form + report`. Each section is a panel rendered by the result UI; `Source agent` is the worker whose output populates it (or `supervisor` if composed).*

| Section | Content | Source agent |
|---|---|---|
| TBD | TBD | TBD |

## 5e. Data and access contract

*One row per grounding or uploaded-data source. Record the customer owner and
the access/retention behavior before connecting production data.*

| Source | Owner | Classification | Contains PII? | Caller identity / ACL enforcement | Refresh | Retention |
|---|---|---|---|---|---|---|
| TBD | TBD | public / internal / confidential / restricted | yes / no / unknown | workload MI / caller Entra / custom | TBD | TBD |

## 6. Constraints & risks
- **Data residency:** US / EU / APAC / custom
- **Identity:** Entra ID / External ID / custom
- **Compliance regime:** SOC 2 / GDPR / HIPAA / PCI / none / custom
- **RAI risks (3–5 specific to this scenario; become redteam cases):**
  1. …
  2. …
  3. …

## 7. Acceptance evals
| Gate | Threshold | Wired to |
|---|---|---|
| Quality (golden agreement) |  | `evals/quality/golden_cases.jsonl` |
| Groundedness |  | `evals/quality/` |
| Safety (redteam) | must pass | `evals/redteam/` |
| Latency (P50 ms / P95 ms) | / | App Insights |
| Cost per call ($) |  | cost attribution telemetry |

---

**Next step:** run `accel design`, preview `accel scaffold --scenario-id <id>
--dry-run`, then apply the approved structural change. Use specialist agents
to author customer-specific workers, tools, grounding, and evals.
