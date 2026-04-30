# ADR-0002 · Foundry portal owns agent instructions

**Status:** Accepted

## Context

Most agent SDKs let you author the system prompt as a string literal
in code (`prompt = """You are a helpful…"""`). It is the most
discoverable approach and matches how prototypes start.

For a production accelerator deployed into a customer tenant, that
shape conflicts with two realities:

1. **Prompt rollback during an incident.** When a regression slips
   through eval gates, the customer's incident commander needs to roll
   back the prompt without waiting for a code-review-build-deploy
   cycle. Code-string prompts force a deploy.
2. **Customer-side prompt review.** Some regulated customers require
   security or domain reviewers to *see* and *sign off on* the live
   instruction set without pulling the partner's git fork.

## Decision

Agent instructions live in the **Foundry portal**, attached to a
named agent and version. The runtime retrieves them with:

```python
client = AzureAIClient(agent_name="...", use_latest_version=True)
```

`accelerator-lint.py` rule `no_inline_agent_instructions` blocks any
attempt to construct or override agent instructions in code.

The repo *does* keep a `docs/agent-specs/<foundry_name>.md` file per
agent — that file is the **source-of-truth** that the partner pastes
into Foundry on first deploy and re-pastes if the portal record is
ever lost. It is **not** the runtime source.

## Consequences

**Positive**

* Prompt rollback during an incident is a portal action, no deploy
  needed. See `customer-runbook.md` §9 P1 and §7.
* Reviewers can see the live instruction set in the portal without
  cloning the fork.
* Foundry's built-in versioning lets the customer pin to a specific
  version while a new one is being soak-tested.

**Negative**

* Two writable surfaces (portal + spec file) means drift is possible.
  The spec file is the documented source-of-truth; portal-side edits
  must be back-ported.
* Local development requires a Foundry account and a deployed agent —
  no fully-offline iteration loop.

**How to deviate**

Not supported. Partners who want code-owned prompts should fork the
accelerator and remove the lint rule, but they lose the rollback and
review workflows the runbook depends on.

## References

* `src/bootstrap.py` — `AzureAIClient(use_latest_version=True)` calls
* `docs/agent-specs/README.md` — spec-file authoring guide
* [`docs/customer-runbook.md` §7 — Prompt / agent-instruction rollback](../customer-runbook.md#7-prompt--agent-instruction-rollback)
* `.github/copilot-instructions.md` — "SDK & platform" rules
