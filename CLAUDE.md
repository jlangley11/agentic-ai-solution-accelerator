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
- After editing the canonical skill, run
  `python scripts/sync-agent-skill.py` and never hand-edit the generated
  `.claude/skills/accelerator/` copy.
- Customer evidence stays local-only until the CLI records
  `approved_for_model`. Do not place unapproved excerpts in Claude context.
