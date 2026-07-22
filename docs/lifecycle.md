# Unified accelerator lifecycle

Install the local package once, then use the vendor-neutral delivery interface:

```powershell
python -m pip install -e ".[dev]"
accel next
```

After installation, `python -m accelerator_cli next` is equivalent.

The CLI derives the current stage from repository and Azure artifacts. It does
not rely on a particular coding-agent session, so an engagement can move
between GitHub Copilot CLI, Codex, Claude Code, or direct terminal use.

## Lifecycle

| Stage | Completion evidence |
|---|---|
| Qualify | Sponsor, wedge process, measurable baseline, and workshop readiness |
| Discover | Governed evidence, approved requirements/traceability, and solution brief with no unresolved markers |
| Scaffold | Scenario package, request/response schemas, experience metadata, agents, grounding, and eval datasets |
| Provision | Declared environment, green preflight, and deployed endpoint metadata |
| Iterate | Quality and red-team datasets plus repository validation |
| UAT | Passing acceptance report and customer sign-off |
| Handover | Engagement-specific handover package |
| Operate | Handover complete; monitoring and value review active |

Every command follows the same interaction:

> Explain → collect missing input → preview → approve → apply or execute →
> verify → calculate the next action

## Commands people need to remember

```text
accel start
accel status
accel next
accel review
accel validate
accel help
```

The CLI selects advanced commands such as `intake`, `scaffold`, `deploy`,
`evaluate`, `uat`, and `handover` when they become relevant.

Use `accel evaluate --api-url <url> --foundry --execute` to supplement deterministic
business assertions with Foundry-native relevance and groundedness evaluators.

## Approval boundaries

| Level | Meaning |
|---|---|
| `inspect` | Read-only repository or environment inspection |
| `apply` | Changes local repository or engagement artifacts |
| `execute` | Calls Azure, GitHub, evaluations, or another external system |
| `destructive` | Command is surfaced for the human operator to run |

The coding-agent CLI's own filesystem, shell, and network permissions remain
authoritative.

Generating a handover packet creates a draft. Day-2 operation does not become
active until `accel handover approve --approver <name> --apply` records the
customer-ops approval.

## Coding-agent usage

### GitHub Copilot CLI

```text
/agent accelerator
```

Or ask: `Use the accelerator skill and continue this engagement.`

### Codex

Ask: `Use the accelerator skill and continue this engagement.`

Codex discovers `.agents/skills/accelerator/SKILL.md`.

### Claude Code

```text
/accelerator
```

Claude loads `CLAUDE.md` and the synchronized skill under
`.claude/skills/accelerator/`.

### MCP clients

Install `.[mcp]` and configure a stdio server with command `accel-mcp`.
Read/preview and write/execute tools are separate so the client can apply its
own approval policy.

## Related

- [CLI reference](reference/accelerator-cli.md)
- [Artifact authority](reference/artifact-model.md)
- [Coding-agent portability](reference/agent-portability.md)
- [Partner playbook](partner-playbook.md)
