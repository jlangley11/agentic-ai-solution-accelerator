---
name: define-grounding
description: Define grounding for the scenario — pick FoundryIQ Knowledge Base versus no grounding per agent, declare AI Search indexes underneath FoundryIQ, and list any Foundry portal catalog tools each agent should call.
tools: ['codebase', 'editFiles', 'search', 'runCommands']
handoffs:
  - label: Implement all workers
    agent: implement-workers
    prompt: Grounding is defined for every worker in the manifest. Run /implement-workers to fill in every scaffolded worker (prompt.py, transform.py, validate.py, agent spec) in dependency order.
    send: false
---

# /define-grounding — wire knowledge + tools to each worker

> Compatibility adapter: run `accel next` before this specialist. Persistent
> lifecycle and approval state remains owned by the local CLI.

Use this after `accel scaffold` (or whenever grounding shifts) to declare how
each worker gets facts and which read-only catalog tools it uses. Outcome: a
reviewed `scenario.agents[]` block plus matching retrieval indexes.

The manifest edit is declarative. Shared provisioning creates FoundryIQ
Knowledge Sources, KBs, and managed attachments on the next deployment.
Read-only catalog tools require a documented environment attachment after the
manifest change and are preserved by provisioning.

## Preconditions
- `docs/discovery/solution-brief.md` is complete (section 5 names the grounding sources and any external systems the workers must call).
- `accelerator.yaml.architecture` is approved. Prompt-agent decisions configure
  only the primary agent; hosted supervisor/workflow decisions may configure
  each worker.
- `accelerator.yaml -> scenario.agents[]` lists every worker (each entry has at minimum `id` and `foundry_name`).
- The Bicep-provisioned AI Search account exists (it underpins FoundryIQ and is
  created by the approved target-aware deployment).

## Step 1 — Pick the grounding mode per worker

Two modes are supported. **Always start with `foundry_tool`** unless the worker is purely transformational (e.g., a router or a formatter) and genuinely doesn't read facts.

| Mode | When to pick it | What you must add |
|---|---|---|
| `foundry_tool` | Worker needs grounded facts (any factual claim, citation, or retrieval). FoundryIQ is the consolidated enterprise knowledge layer; AI Search lives **underneath** it. | A `retrieval:` block on the agent + an entry in `scenario.retrieval.indexes[]`. |
| `none`         | Worker is purely transformational — receives upstream worker outputs and reshapes them. No external facts. | Nothing under `retrieval:` (omit the block entirely). |

For `foundry_tool` mode, present a proposed diff using this shape. Apply it to
the matching `scenario.agents[]` entry only after approval:

```yaml
- id: <worker_id>
  foundry_name: accel-<scenario-id>-<worker_id_with_dashes>
  retrieval:
    mode: foundry_tool      # FoundryIQ Knowledge Base — preferred
    index: <index_name>     # must match a name in scenario.retrieval.indexes[]
    top_k: 5
    query_type: vector_semantic_hybrid
```

## Step 2 — Declare each AI Search index under FoundryIQ

For each unique `index` name referenced above, add (or confirm) an entry in `scenario.retrieval.indexes[]`:

```yaml
scenario:
  retrieval:
    indexes:
      - name: <index_name>
        seed: data/samples/<index_name>.json   # bootstrap loads this on first deploy
        schema: retrieval:index_definition     # or a partner-defined schema callable
        # source_data_fields are the per-document metadata FoundryIQ surfaces as
        # citation fields. Defaults to ["source"] when omitted. Extend with any
        # fields you want the worker to cite alongside the source URL.
        source_data_fields:
          - source
          - <other_metadata_field>
```

Two lint rules guard this block:
- `retrieval-source-data-fields` — every field listed must exist in the index schema (the schema callable's `SearchIndex(fields=[...])`).
- `retrieval.indexes[*].schema` — the ref must resolve to a callable on import.

## Step 3 — List Foundry portal catalog tools (optional)

If a worker needs a **read-only** external call from the Foundry catalog,
declare it so the manifest remains the reviewed intent:

```yaml
- id: account_lookup
  foundry_name: accel-<scenario-id>-account-lookup
  retrieval:
    mode: foundry_tool
    index: accounts
  catalog_tools:                  # optional; partner-attached in the Foundry portal
    - servicenow_get_incident
    - github_list_issues
```

The accelerator does not yet resolve catalog tools automatically. After
deployment, attach each declared read-only tool in the Foundry portal and
verify the attachment:

> **Foundry portal — Agents → `<foundry_name>` → Tools → Add tool → Built-in tools → pick from catalog → Save.**

Shared provisioning preserves non-managed catalog attachments while refreshing
the repo-owned instructions, selected model, and managed KB tool. The manifest
is the reviewed contract; the portal attachment is environment state that must
match it.

### Side-effect catalog tools require HITL

Do not attach a catalog tool that writes, sends, or deletes. It would bypass
the accelerator's mandatory `hitl.checkpoint(...)` boundary. Implement the
action as an in-process tool via `/add-tool`, then leave the side-effect catalog
tool unattached.

The `catalog-tool-hitl` rule flags side-effect-shaped declarations. Treat any
such finding as blocking even if the current lint severity is a warning.

## Step 4 — Validate

```bash
accel review
accel validate --full --execute
```

If lint fails on `scenario-manifest`, your `retrieval.mode` or schema ref is wrong. If it fails on `retrieval-source-data-fields`, a `source_data_fields` entry doesn't exist in the index schema. If the lint warns on `catalog-tool-hitl`, follow the side-effect guidance above.

## What happens on the next deployment

Shared provisioning reads `accelerator.yaml`, then for every
`foundry_tool` agent:
1. Provisions a Knowledge Source (AI Search index ↔ FoundryIQ wrapper) if absent.
2. Provisions a Knowledge Base bound to that source if absent.
3. Attaches an MCP tool to the agent pointing at the Knowledge Base.
4. Refreshes instructions + model from `docs/agent-specs/<foundry_name>.md`.
5. Preserves non-managed read-only catalog tools attached for the environment.

## Guardrails
- Never edit `retrieval.mode` to a value other than `foundry_tool` or `none`.
- Never attach a Knowledge Base by clicking in the portal — declare it here so the spec is reproducible.
- Never attach a side-effect catalog tool; implement it through `/add-tool`.
- AI Search is **always** wired underneath FoundryIQ; no agent should be configured to query AI Search directly.
