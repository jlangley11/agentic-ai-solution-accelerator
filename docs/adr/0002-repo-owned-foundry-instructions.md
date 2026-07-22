# ADR-0002 · Repository owns Foundry agent instructions

**Status:** Accepted

## Context

Prototype prompts often live either as Python string literals or as mutable
portal configuration. Neither is sufficient for a partner-delivered,
customer-owned production solution:

1. Inline strings mix system policy with per-request prompt construction.
2. Portal edits bypass review, are difficult to reproduce across environments,
   and drift from the customer fork.
3. Self-hosted and Hosted preview targets need the same instruction artifact.

## Decision

Each Foundry agent's durable system instructions live in
`docs/agent-specs/<foundry_name>.md`.

Shared provisioning reads the spec and creates/updates the matching Foundry
agent version:

- self-host: FastAPI startup through `src/bootstrap.py`
- Hosted preview: the postdeploy hook

Runtime inference uses Microsoft Agent Framework's version-resolved
`FoundryAgent` path. `prompt.py` builds only the per-request user envelope.
Portal inspection is supported; portal-authored instruction changes are not
and are overwritten on the next provisioning sync.

`accelerator-lint.py` blocks inline system instructions and other parallel
authoring paths.

## Consequences

**Positive**

* Prompt changes are reviewable, diffable, and portable across clients and
  environments.
* Rollback is deterministic: revert the spec, deploy, and re-run acceptance.
* Self-hosted and Hosted preview targets converge on one provisioning path.
* The portal still exposes the materialized version for customer inspection.

**Negative**

* A durable prompt change requires the normal review/deployment path.
* Operators must not treat a successful portal edit as a completed rollback.
* End-to-end validation still requires a deployed Foundry project.

**How to deviate**

Not supported. Do not move instructions into Python or make the Foundry portal
the authoring surface.

## References

* `src/provisioning.py` — spec synchronization and version creation
* `src/bootstrap.py` — self-host compatibility shim
* `docs/agent-specs/README.md` — authoring and synchronization guide
* [`docs/customer-runbook.md` §7 — Prompt / agent-instruction rollback](../customer-runbook.md#7-prompt--agent-instruction-rollback)
* `AGENTS.md` — SDK and platform rules
