# Coding-agent portability

The accelerator's workflow is implemented by the local `accel` CLI. Coding
agents provide conversational UX but do not own lifecycle logic.

## Shared surfaces

| Surface | Location | Consumers |
|---|---|---|
| Repository rules | `AGENTS.md` | Copilot CLI, Codex, Claude through import |
| Canonical Agent Skill | `.agents/skills/accelerator/` | Copilot CLI, Codex |
| Claude skill adapter | `.claude/skills/accelerator/` | Claude Code |
| Copilot custom agent | `.github/agents/accelerator.agent.md` | VS Code and Copilot CLI |
| Deterministic workflow | `src/accelerator_cli/` | Every client and direct terminal use |
| Optional MCP adapter | `src/accelerator_mcp/` | Copilot CLI, Codex, Claude Code, other MCP clients |

`scripts/sync-agent-skill.py` synchronizes the Claude adapter. CI checks that
the committed copy matches the canonical skill.

## MCP setup

Install the optional adapter:

```powershell
python -m pip install -e ".[mcp]"
```

Configure a local stdio server whose command is `accel-mcp`. The server exposes
read-only status and preview tools separately from repository-write and Azure
execution tools so each coding-agent client's approval policy remains effective.

## Portability rules

- Never depend on a vendor's conversation history to determine engagement
  state.
- Never put lifecycle business logic in an agent prompt.
- Never require subagents, fleet mode, plugins, or remote control for
  correctness.
- Vendor-specific capabilities may improve presentation, parallelism, or
  review, but they must call the same CLI operations.
- Compare cross-agent behavior by commands, state transitions, artifacts, and
  approvals—not identical prose.

## Updating the shared skill

1. Edit `.agents/skills/accelerator/SKILL.md`.
2. Run `python scripts/sync-agent-skill.py`.
3. Run `python scripts/sync-agent-skill.py --check`.
4. Run `python -m pytest tests/test_agent_skill_portability.py -q`.
