# ADR-0011 · Architecture advice is an approved lifecycle gate

**Status:** Accepted

## Context

Discovery previously selected only a scenario topology such as
`supervisor-routing`. Scaffolding still assumed the self-hosted application
shape before asking whether the requirements fit a Foundry prompt agent,
Hosted agent, existing application, or custom UX.

This forced partners to understand many platform and slash-command details and
made the deployment target an environment concern rather than an architectural
decision.

## Decision

Add an explicit `design` lifecycle stage between discovery and scaffolding.

`accel design` deterministically recommends:

1. Foundry agent type: prompt or Hosted
2. orchestration pattern: single agent, deterministic workflow, or supervisor
3. application shell: none, existing app, workbench, or custom
4. accelerator target: `foundry-prompt`, `hosted-preview`, or `selfhost`

The recommendation includes signals, confidence, alternatives, and official
Foundry references. A partner must approve or override it; overrides require a
reason. The approved record and requirements fingerprint live in
`accelerator.yaml -> architecture`.

Workflow is modeled as orchestration—not as a third Agent Service runtime type.

## Consequences

**Positive**

- Partners need only `accel next`; architecture guidance appears automatically.
- Prompt-agent scenarios can avoid the application runtime entirely.
- Existing frameworks and complex orchestration receive evidence-backed Hosted
  recommendations.
- Requirement changes invalidate stale decisions before scaffold/deploy.
- Architecture rationale is reviewable and available during handover.

**Negative**

- The CLI wire contract adds a `design` stage and moves to schema version 1.1.
- Scaffold and deployment are blocked until the decision is approved.
- The prompt-agent target needs a separate GitHub Environment and currently has
  a provisioning canary rather than the self-host SSE acceptance chain.

## References

- `src/accelerator_cli/architecture_advisor.py`
- `src/accelerator_cli/lifecycle_commands.py`
- `deploy/foundry-prompt/`
- [`Architecture Advisor`](../reference/architecture-advisor.md)
- [Foundry Agent Service overview](https://learn.microsoft.com/azure/foundry/agents/overview)
