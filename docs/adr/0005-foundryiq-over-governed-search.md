# ADR-0005 · FoundryIQ over governed Azure AI Search

**Status:** Accepted

## Context

Retrieval-augmented generation is the most common extension point partners ask
about. Customers want grounding on documents, knowledge bases, structured data,
or external systems, while the accelerator must preserve identity, private
networking, citation provenance, and evaluation.

That breadth has a cost: groundedness is a security boundary. Without
a single retrieval surface, the eval gates can't reliably check that
retrieved content was sanitized, that citations resolve, that the
content-filter pipeline actually saw the retrieved bytes, or that
private-endpoint policies cover the data plane.

## Decision

New manifests declare either:

- `foundry_tool` — a FoundryIQ Knowledge Base exposed to the Foundry agent
  through an MCP tool, with governed Azure AI Search indexes underneath
- `none` — for purely transformational workers

Shared provisioning creates Search schemas/seeds first, then FoundryIQ
Knowledge Sources/KBs, then agent attachments and RBAC. The
`python_injected` path through `src/retrieval/ai_search.py` remains legacy
runtime compatibility and is not accepted for new manifests.

Tools that need transactional or fresh external-system data remain normal
tools, not retrievers.

Direct HTTP to content sources (e.g. `requests.get(...)` against a
SharePoint site, GitHub raw URL, or web crawler endpoint) inside a
retrieval module is rejected by `accelerator-lint.py` rule
`retrieval_must_use_ai_search`.

## Consequences

**Positive**

* Foundry-native knowledge tooling is used without giving up governed Search
  schemas, private endpoints, Entra identity, or citation validation.
* Full retrieved-URI provenance can be propagated to dependent workers.
* Provisioning and evaluation can reason about a finite set of manifest modes.

**Negative**

* Sources without a supported Search ingestion path require ETL or a governed
  external tool.
* Existing `python_injected` scenarios require migration rather than being
  copied into new manifests.
* "Just paste the URL" demos do not compose with the citation/RAI gates.

**How to deviate**

A hard requirement for another retrieval substrate is outside the supported
manifest contract. The partner would own identity, provenance, citation,
groundedness, private-network, and red-team equivalents.

## References

* `src/provisioning.py`
* `src/retrieval/ai_search.py` (legacy compatibility path)
* `accelerator.yaml` — per-agent retrieval modes and index declarations
* `evals/quality/` — groundedness scorer
* `AGENTS.md` — Grounding / RAG rules
