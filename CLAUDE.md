@AGENTS.md

# Claude Code adapter

`AGENTS.md` above is the complete engineering contract. This file contains only
Claude-specific adapter guidance:

- Use `.claude/skills/accelerator/SKILL.md` for engagement lifecycle work.
- Begin lifecycle tasks with `accel --json --pretty next`; never infer stage
  from conversation memory or auto memory.
- Treat `inspect`, `apply`, `execute`, and `destructive` as separate permission
  boundaries. Plan mode is read-only; never auto-run destructive commands.
- Use subagents only for bounded research or validation. They do not own
  lifecycle state and must return to the main session before writes.
- Project MCP configuration may call `accel-mcp`; prefer its preview/read tools
  before write or cloud-execution tools.
- After discovery, run `accel design`; present the recommendation and require
  approval or an override reason before scaffold/deploy. Do not infer prompt
  versus Hosted agent or managed-prompt versus Harness versus custom-workflow
  from conversation memory. Harness is an implementation pattern; workflow is
  orchestration, not a third Foundry Agent Service runtime type.
- Treat `foundry-prompt`, `hosted-preview`, and `selfhost` as distinct targets;
  use only the target recorded in the approved architecture decision.
- Keep Harness experimental capabilities disabled by default and never use its
  approval layer to bypass accelerator `hitl.checkpoint(...)`.
- Generate scaffold-phase Azure architecture diagrams through Azure
  Architecture Diagram Builder MCP, commit the SVG plus checksum-bound
  `.mcp.json` provenance, and never hand-edit the generated SVG.
- After editing the canonical skill, run
  `python scripts/sync-agent-skill.py` and never hand-edit the generated
  `.claude/skills/accelerator/` copy.
- Customer evidence stays local-only until the CLI records
  `approved_for_model`. Do not place unapproved excerpts in Claude context.
- For workbench changes, never retain/render raw model chunks. Browser history
  is opt-in local storage, must expose clear privacy and deletion controls, and
  must not display saved request values in navigation.
