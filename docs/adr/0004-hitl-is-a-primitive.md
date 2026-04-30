# ADR-0004 · HITL is a primitive on every side-effect tool

**Status:** Accepted

## Context

Most agent frameworks treat human-in-the-loop as an opt-in feature
applied per-deployment ("turn on approvals if you need them"). For
internal pilots that is fine; for production agents that touch CRMs,
ticketing systems, email gateways, or destructive APIs in regulated
customers, "opt-in" means "off by default" means "on incident day,
off in production".

The accelerator targets customer environments where reversibility and
auditability matter more than the convenience of skipping approvals.

## Decision

HITL is a **primitive**, not a feature. Every side-effect tool MUST
gate through `src/accelerator_baseline/hitl.py.checkpoint(...)` —
**no exceptions in code**. `accelerator-lint.py` rule
`tools_must_use_hitl` blocks merge of any tool module that performs
a write/send/destructive call without the checkpoint.

The *policy* (`mode: required` / `optional` / `none`) is configured
per accelerator in `accelerator.yaml -> solution.hitl` and per tool in
the tool module. `mode: none` is permitted only when the action is
**reversible** AND **logged** — both verifiable from the tool's
metadata.

## Consequences

**Positive**

* Partner cannot accidentally ship a side-effect tool without
  approvals — lint catches it pre-merge.
* `/add-tool` scaffolds the checkpoint by default, so the easy path
  is also the safe path.
* Killswitch (`customer-runbook.md` §3) flipping to `none-allowed`
  halts every side-effect agent in one Bicep parameter.

**Negative**

* "Read-only" agents that the partner *thinks* are read-only may have
  to cross the lint barrier. The mitigation is correct: the tool is
  read-only and lint passes; or it isn't and HITL was the right ask.
* Approver endpoint becomes a deployment dependency — if the approver
  Logic App / webhook is misconfigured, side-effect tools fail closed
  (correct behavior, but surprising on first deploy).

**How to deviate**

Not supported. A partner who wants no-HITL deploys can set every
tool to `mode: none`, but only for tools that meet the reversible +
logged bar. Removing the lint rule is out of scope.

## References

* `src/accelerator_baseline/hitl.py` — `checkpoint(...)` primitive
* `accelerator.yaml.solution.hitl` — declared policy
* `scripts/accelerator-lint.py` — `tools_must_use_hitl` rule
* [`docs/customer-runbook.md` §3 (Killswitch)](../customer-runbook.md#3-operational-dials-at-runtime) and [§9 (incident playbook)](../customer-runbook.md#9-incident-playbook)
* `.github/agents/add-tool.agent.md`
