# ADR-0001 · Microsoft Agent Framework + Microsoft Foundry

**Status:** Accepted

## Context

The agentic-AI ecosystem has multiple viable orchestration SDKs:
Microsoft Agent Framework (MAF), Semantic Kernel, LangChain /
LangGraph, LlamaIndex, Haystack, AutoGen, and several hosted-only
frameworks. Each ships its own primitives for prompts, tools,
multi-agent coordination, and tracing.

For a Microsoft-shipped accelerator that lands in customer Azure
tenants, the choice is load-bearing: it determines which model
provider works first-class, which observability stack wires
seamlessly, and which support contract the customer can rely on when
something breaks at 2am.

## Decision

The accelerator uses **Microsoft Agent Framework (`agent_framework`)**
with **Microsoft Foundry** as the model backend. Agent identities,
versioning, and content-safety policies live in Foundry; orchestration
(supervisor, workers, executors, HITL gates) is authored in MAF.

`accelerator-lint.py` enforces the negative space:

* `no_direct_openai_client` — OpenAI clients are blocked for agent inference;
  the Entra-authenticated provisioning-time seed-embedding path is the only
  narrow exception.
* `no_other_orchestrators` — imports from LangChain, LlamaIndex,
  Haystack, etc. fail lint.

## Consequences

**Positive**

* Customer's Azure support contract covers the model + identity +
  filter plane end-to-end. No "go ask the LangChain community" path.
* Foundry agent versioning provides explicit runtime versions while repo-owned
  specs make rollback reviewable and reproducible
  (see [ADR-0002](0002-repo-owned-foundry-instructions.md)).
* Telemetry plumbs through `azure-monitor-opentelemetry` with no
  glue code.

**Negative**

* Partners arriving with a working LangChain prototype must port to
  MAF before scaffolding a customer fork. The
  `accel scaffold` and the worker specialists assume MAF idioms.
* Some bleeding-edge LangChain integrations (specific community
  vector stores, niche tool schemas) have no first-class MAF
  equivalent and must be re-implemented.

**How to deviate**

There is no supported deviation. A partner who needs a different
orchestrator should not use this accelerator — the supervisor,
worker, HITL, and telemetry primitives are MAF-shaped and not
portable.

## References

* `pyproject.toml` — `agent_framework` pin
* `.github/copilot-instructions.md` — "SDK & platform" rules
* `docs/version-matrix.md` — compatibility window
