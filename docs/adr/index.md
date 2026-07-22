# Architecture decision records

This folder records the non-obvious decisions that shape the
accelerator. Each ADR captures **why** the decision exists — the
**how** lives in code, Bicep, or `.github/copilot-instructions.md`.

Use these when:

* A customer security or architecture review asks "why did you pick X?"
* A partner wants to deviate from a default and needs to know what
  that breaks.
* A new contributor reads `.github/copilot-instructions.md` and asks
  "where does this rule come from?"

Format: short [MADR](https://adr.github.io/madr/) — Title · Status ·
Context · Decision · Consequences. Decisions are *immutable*; if the
position changes we add a new ADR that supersedes the old one.

| ID | Title | Status |
|----|-------|--------|
| [0001](0001-microsoft-agent-framework.md) | Microsoft Agent Framework + Microsoft Foundry | Accepted |
| [0002](0002-repo-owned-foundry-instructions.md) | Repository owns Foundry agent instructions | Accepted |
| [0003](0003-supervisor-and-workers-flagship.md) | Supervisor + workers as the flagship shape | Accepted |
| [0004](0004-hitl-is-a-primitive.md) | HITL is a primitive on every side-effect tool | Accepted |
| [0005](0005-foundryiq-over-governed-search.md) | FoundryIQ over governed Azure AI Search | Accepted |
| [0006](0006-abac-constrained-rbac-admin.md) | ABAC-constrained RBAC-Admin for runtime per-agent grants | Accepted |
| [0007](0007-three-layer-agent-module.md) | Three-layer agent module (prompt / transform / validate) | Accepted |
| [0008](0008-unified-accelerator-cli.md) | Unified local accelerator CLI | Accepted |
| [0009](0009-private-evidence-ledger.md) | Local private evidence ledger | Accepted |
| [0010](0010-schema-driven-workbench.md) | Schema-driven customer workbench | Accepted |

## When to add an ADR

Add one when the decision:

1. Affects how a partner *should* extend the accelerator (i.e. it's
   load-bearing for `MUST` / `NEVER` rules in copilot-instructions).
2. Has plausible alternatives a reviewer would propose.
3. Is unlikely to flip again in the next 6 months.

Do **not** add an ADR for routine implementation choices, library pin
upgrades, or single-PR refactors. Use git history for those.
