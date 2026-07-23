---
name: accelerator
description: Continue, review, diagnose, scaffold, deploy, evaluate, or hand over an Azure Agentic AI Solution Accelerator engagement. Use this skill whenever the user asks what to do next, starts a customer engagement, supplies requirements documents, changes the scenario, deploys an environment, runs UAT, or prepares operations—even if they do not mention the accelerator CLI.
---

# Accelerator engagement workflow

Use the repository's deterministic `accel` CLI as the source of lifecycle
state. Do not infer the engagement stage from conversation history.

## Start every engagement task

Ensure the project is installed (`python -m pip install -e ".[dev]"`), then
run:

```powershell
python -m accelerator_cli --json --pretty next
```

`accel --json --pretty next` is the preferred equivalent entry point.

Interpret the returned fields:

- `status=needs_input`: collect only `required_inputs` and unresolved issues.
- `status=approval_required`: present the proposed actions and request approval.
- `status=blocked`: explain each blocking issue and its remediation.
- `status=failed`: diagnose the command failure before continuing.
- `status=complete|ready`: use `next_command`.

## Interaction pattern

For every stage, follow this order:

1. Explain the current stage and why it matters.
2. Collect only the missing information.
3. Run a dry-run or read-only command.
4. Present the proposed files, cloud actions, or disclosure decision.
5. Obtain explicit approval for `apply`, `execute`, or `destructive` actions.
6. Run the approved command.
7. Run `python -m accelerator_cli --json next` again.

Do not skip from a planning result directly to execution.

## Permission boundaries

- `inspect`: read-only; may run automatically.
- `apply`: changes repository or local engagement artifacts; preview first.
- `execute`: calls Azure, GitHub, evaluations, or another external system;
  request separate approval.
- `destructive`: surface the command and let the human run it.

The coding-agent CLI's own permission system remains authoritative.

## Customer document intake

Add multiple local documents with:

```powershell
accel intake add <path> [<path> ...]
accel intake list
accel intake review <source-id>
```

Documents enter the gitignored evidence ledger as `local_only`. Before any
model-assisted extraction can use source text, show the user the source
metadata and record an explicit disclosure decision:

```powershell
accel intake disclose <source-id> approved_for_model --apply
```

Approval changes local metadata only; it does not transmit content by itself.
Never include secrets or unapproved source excerpts in prompts.

Record reviewed requirement candidates with stable IDs and evidence links:

```powershell
accel intake requirement add --category <category> --statement <text> `
  --evidence <source-id>:<chunk-id> --apply
accel intake requirement list
accel intake requirement decide <requirement-id> approved --by <reviewer> --apply
accel intake requirement link <requirement-id> --type quality_eval `
  --target evals/quality/golden_cases.jsonl#<case-id> --apply
accel intake requirement export --apply
```

Supported local intake formats include Markdown, text, CSV, DOCX, PDF, PPTX,
XLSX, and XLSM. Scanned PDFs fail closed with an OCR/export remediation rather
than silently producing an empty requirement set. Sources default to a 50 MiB
limit; macros are never executed.

## Architecture Advisor

After discovery is complete, run `accel design`. Present the recommendation,
matched signals, confidence, alternatives, and official Foundry references.
Foundry agent types are `prompt-agent` and `hosted-agent`. Implementation
patterns are `managed-prompt`, `harness`, and `custom-workflow`; workflow is a
separate orchestration pattern.

Do not scaffold until the partner approves:

```powershell
accel design --approved-by "<partner architect>" --apply
```

If any selected dimension differs from the recommendation, require
`--override-reason`. Requirement changes invalidate the stored fingerprint and
return the lifecycle to design.

Use Harness only for a Hosted `single-agent` recommendation. Scaffold it with
`--no-retrieval`; the generated workflow uses `src.workflow.harness` and one
primary agent spec. Do not add workers. File access, background agents, looping,
shell, built-in web search, file memory, and framework auto-approval remain
disabled until separately governed. Side-effect tools still require
`hitl.checkpoint(...)`.

## Architecture diagram deliverable

After scaffold apply, generate the scenario's Azure resource diagram with
**Azure Architecture Diagram Builder MCP v1.0.0**. Use the deterministic tool
sequence `list_services` → `validate_architecture` → `render_diagram`, then
commit both:

- `docs/assets/diagrams/<scenario>-architecture.svg`
- `docs/assets/diagrams/<scenario>-architecture.mcp.json`

The provenance JSON must record the service graph, connections, groups, render
options, MCP release and tools, WAF result, and SHA-256 of the generated SVG.
Never hand-edit the SVG. Regenerate from the provenance input, and return to
`accel design` if WAF remediation changes the approved topology.

## Common lifecycle commands

```text
accel discover
accel design
accel design --approved-by <name> --apply
accel scaffold --scenario-id <id> --dry-run
accel environment list
accel deploy --env <env> --region <region> --dry-run
accel validate --full --execute
accel evaluate --api-url <url> --execute
accel uat report
accel handover generate --env <env> --dry-run
accel handover approve --approver <name> --apply
accel operate status
```

Use the exact `next_command` returned by the CLI when it differs from these
examples.

Prefer the `accel` command over a legacy task-specific custom agent whenever
both exist. Legacy agents are compatibility entry points, not the authoritative
workflow.

## Repository guardrails

Read and follow `AGENTS.md`. In particular:

- Keep `accelerator.yaml` as the executable engagement contract.
- Keep `accelerator.yaml.architecture` approved and current before
  scaffold/deploy.
- Treat `docs/discovery/solution-brief.md` as approved intent and
  `.accelerator/private/evidence.db` as local provenance—not parallel config.
- Keep Foundry agent instructions in `docs/agent-specs/*.md`.
- Declare request/response schemas and `scenario.experience` so
  `/scenario/metadata` can drive the generic workbench.
- Use Microsoft Agent Framework and managed identity.
- Preserve HITL, telemetry, evaluation, content-filter, and landing-zone rules.
- Never commit `.accelerator/`; it contains local engagement state.

## Failure handling

When a command fails:

1. Read `blocking_issues` and command diagnostics.
2. Fix the root cause or ask for the missing decision.
3. Re-run the same command.
4. Do not shape a failed operation as success.

Use `accel review` and `accel validate --full --execute` before a PR.
