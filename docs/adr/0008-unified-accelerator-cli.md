# ADR 0008 — Unified local accelerator CLI

**Status:** Accepted
**Date:** 2026-07-21

## Context

The accelerator originally expressed its delivery workflow across walkthroughs,
custom-agent prompts, scripts, and chat history. That made the experience
Copilot-centric and allowed procedural guidance to drift from executable
behavior.

## Decision

The Python `accel` CLI is the authoritative lifecycle engine. It derives state
from repository and Azure artifacts, emits a versioned JSON result contract,
and separates `inspect`, `apply`, `execute`, and `destructive` operations.

Agent Skills, custom agents, MCP clients, and humans invoke the same command
functions. Vendor session state and subagents may improve UX but cannot be
required for correctness.

## Consequences

- Engagements can move between Copilot CLI, Codex, Claude Code, and direct
  terminal use.
- Procedural documentation is generated from executable command metadata.
- Existing custom agents remain compatibility adapters during migration.
- New lifecycle operations must support preview and typed failure results.
