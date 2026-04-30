# Chat-with-Actioning Pattern

Use this variant when the user interaction is **conversational**, multi-turn,
and the agent occasionally performs side-effects (schedule meeting, open
ticket, write CRM record) mid-conversation.

## When to pick this

- The user is the human in the loop — they direct the conversation and
  approve actions inline.
- Short-horizon tasks, not batch research.
- Thread state must persist across turns.

## When NOT to pick this

- Long-running research (flagship fits better).
- Users don't want a chat UX (single-agent or flagship fit better).

## Swap in

```bash
/switch-to-variant chat-with-actioning
```

That custom agent:
1. Replaces `src/main.py` with this pattern's `chat.py`.
2. Adds `src/scenarios/<scenario>/agents/chat_assistant/` (3-layer shape).
3. Keeps the `hitl.checkpoint` gate on every side-effect tool.
4. Updates `accelerator.yaml.solution.pattern`.

## Thread state

Chat threads are persisted in Foundry's thread store (the Agent Framework
``Thread`` abstraction). Partners must NOT roll their own thread store — reuse
Foundry's so thread IDs line up with observability.
