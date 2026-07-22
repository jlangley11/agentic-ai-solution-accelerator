# Reference: Customer Service with Actioning

> **Shape:** supervisor-routing. **Primary ROI lever:** deflection + AHT. **Variant of:** the flagship. Use as a scaffolding reference — it is NOT runnable on its own; partners adapt the flagship `src/` to this scenario via `/scaffold-from-brief`.

## When to use this
Customer has a tier-1 service desk (customer support, returns, account servicing) where most inbound asks today are:
1. "Where's my order / case / refund status?"
2. "Can you fix / change / refund this?"
3. Edge cases a human must handle.

A chatbot deflects (1) and loses (2). An agentic solution does (1) AND (2) with HITL, and escalates (3).

## Chatbot baseline vs agentic lift
| Capability | Chatbot | Agent + HITL |
|---|---|---|
| Answer from KB | ✓ | ✓ |
| Look up order / case status | sometimes | ✓ (API grounding) |
| Issue refund / credit | ✗ | ✓ with HITL approval |
| Update CRM / ticket | ✗ | ✓ with HITL approval |
| Handle multi-step cases | ✗ | ✓ (supervisor + workers) |
| Escalate with context | partial | ✓ (full conversation + actions taken) |

**ROI lever:** deflection % (from ~30% → 55–70%), AHT ↓ 40–60%, CSAT ↑ on resolved cases.

## Proposed agent graph
```
  Supervisor (intent + route)
  ├── KBResearcher      — grounded Q&A over help center
  ├── OrderLookup       — reads customer/order systems (read-only)
  ├── CaseActor         — creates/updates cases (HITL)
  ├── RefundActor       — issues refunds/credits (HITL)
  └── EscalationRouter  — constructs handoff packet
  Aggregator            — assembles response + action log
```

## Side-effect tools (all HITL-gated)
- `case_create_update` — ticketing system (ServiceNow/Zendesk/Dynamics)
- `refund_issue` — billing system
- `credit_apply` — billing system
- `crm_note_add` — CRM (Salesforce/Dynamics)
- `handoff_to_human` — routing the live conversation

## Grounding
- Help center articles (AI Search index)
- Product catalog (AI Search index)
- Order history (customer system API — grounded per request, not indexed)

## HITL policy (default)
- **always:** `refund_issue`, `credit_apply` (money out)
- **threshold:** `case_create_update` (skip HITL if case.priority ∈ {low, medium}, require HITL for {high, critical})
- **never:** none — every side effect goes through `hitl.checkpoint`

## Success criteria to fill in
- Deflection % (current → target)
- AHT (current → target in minutes)
- CSAT on agent-resolved cases (target)
- First-contact resolution rate
- % of automated actions reversed by customer (watch for over-automation)

## RAI risks specific to this scenario
1. Agent issues a refund larger than policy allows — mitigated by HITL + schema validation on `refund_issue` amount.
2. Agent hallucinates order status when upstream API errors — mitigated by `validate.py` rejecting ungrounded claims.
3. Agent exposes one customer's data to another (tenant confusion) — mitigated by auth-propagation tests + redteam case.
4. Agent escalates too eagerly or too reluctantly — mitigated by eval cases on escalation threshold.

## KPIs to instrument (events)
- `case.intent_classified`
- `case.resolved_by_agent`
- `case.escalated_to_human`
- `action.refund_issued` (amount redacted bucket)
- `action.hitl_rejected`
- `case.csat_collected`

## How to scaffold from this reference
1. Copy this README's section content into the relevant parts of `docs/discovery/solution-brief.md`.
2. Run `accel design`, preview `accel scaffold --scenario-id
   customer-service --dry-run`, then apply it.
3. `/add-worker-agent` for each of: KBResearcher (or adapt `account_planner`),
   OrderLookup, CaseActor, RefundActor, EscalationRouter.
4. `/add-tool` for each side-effect tool above.
5. Write 20–50 golden cases into `evals/quality/golden_cases.jsonl` derived from historical tier-1 tickets.
