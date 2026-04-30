# ADR-0005 · Azure AI Search is the only retrieval surface

**Status:** Accepted

## Context

Retrieval-augmented generation is the most common extension point
partners ask about: customers want grounding on documents, knowledge
bases, structured data, or external HTTP sources. A flagship
accelerator could expose retrieval as an abstraction (a `Retriever`
interface) and let partners plug in any vector store, search engine,
or HTTP client.

That breadth has a cost: groundedness is a security boundary. Without
a single retrieval surface, the eval gates can't reliably check that
retrieved content was sanitized, that citations resolve, that the
content-filter pipeline actually saw the retrieved bytes, or that
private-endpoint policies cover the data plane.

## Decision

The accelerator uses **Azure AI Search** as the only first-class
retrieval surface. All retrieval flows through
`src/retrieval/ai_search.py`. Tools that need fresh data from
external systems do *not* live in retrieval; they are normal tools
that call those systems via SDK and emit their own grounding events.

Direct HTTP to content sources (e.g. `requests.get(...)` against a
SharePoint site, GitHub raw URL, or web crawler endpoint) inside a
retrieval module is rejected by `accelerator-lint.py` rule
`retrieval_must_use_ai_search`.

## Consequences

**Positive**

* Single integration point for AAD auth, private endpoints, content
  filters, citation tracking, and groundedness eval.
* Knowledge base management, indexer schedules, vector embedding
  policies, and PII redaction live in one place.
* The Foundry MCP RemoteTool connection (`infra/main.bicep:339`)
  consumes Search directly — no broker layer.

**Negative**

* Sources that don't have a Search indexer adapter must be ETL'd
  into Search (or wrapped as a tool, not a retriever). That is real
  upfront work for some customer estates.
* "Just paste the URL" demos that bypass Search are not part of the
  flagship — partners run them in `/switch-to-variant` walkthroughs
  but they don't compose with the eval / RAI gates.

**How to deviate**

A partner with a hard requirement for a non-Search retrieval surface
(e.g. an internal vector DB the customer mandates) can fork the
retrieval module — but they own re-implementing groundedness
validation, citation resolution, and the corresponding redteam cases.
That is out of scope for the flagship.

## References

* `src/retrieval/ai_search.py`
* `infra/main.bicep` lines 270–355 (Search service, project
  connection, MCP RemoteTool connection)
* `evals/quality/` — groundedness scorer
* `.github/copilot-instructions.md` — "Grounding / RAG" rules
