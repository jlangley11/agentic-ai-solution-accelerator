# Single-Agent Pattern

Use this variant when you do **not** need supervisor orchestration — a single
Foundry agent with retrieval and one or two read-only tools is sufficient.

## When to pick this

- Short, bounded tasks (FAQ, summarisation, lookup, simple extraction).
- One persona, one set of sources.
- No multi-step planning.
- No tool chaining longer than ~2 calls.

## When NOT to pick this

- Multiple personas with different success criteria → use flagship supervisor.
- Side-effect tools (write/email/ticket) → use flagship (HITL gate lives in the
  aggregator).
- Multi-step reasoning across disjoint domains → use flagship.

## Swap in

```bash
# From the repo root
/switch-to-variant single-agent
```

That custom agent:

1. Copies `patterns/single-agent/src/agent.py` over `src/main.py`.
2. Strips flagship workers (`src/scenarios/sales_research/agents/{icp_fit_analyst,competitive_context,outreach_personalizer,supervisor}`)
   leaving only `account_researcher` (rename if needed).
3. Updates `accelerator.yaml.solution.pattern` to `single-agent`.
4. Re-runs `python scripts/accelerator-lint.py`.

## Structure

```
patterns/single-agent/src/
  agent.py     # FastAPI entrypoint + one agent + retrieval
```
