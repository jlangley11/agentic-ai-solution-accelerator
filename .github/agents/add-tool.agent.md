---
name: add-tool
description: Add a side-effect tool (CRM write, ticket create, email send, etc.) with HITL scaffolding, telemetry, and a redteam case.
tools: ['codebase', 'editFiles', 'search']
---

# /add-tool — scaffold a side-effect tool with HITL baked in

> Compatibility adapter: use `accel next` before adding the tool and
> `accel validate` after HITL, telemetry, tests, and red-team wiring are complete.

Use this for any tool that writes, sends, mutates external state, or triggers destructive actions. If the tool is read-only, you probably don't need this — just add a retriever under `src/retrieval/`.

## Inputs to gather
1. **Tool name** (lowercase_with_underscores, e.g., `crm_create_contact`)
2. **External system** (e.g., Salesforce, ServiceNow, Dynamics, SMTP)
3. **Operation** (verb + object, e.g., "create Contact in Salesforce")
4. **Reversibility** (reversible / irreversible — affects HITL default)
5. **HITL policy**: `always` / `threshold:<expr>` (for example,
   `threshold:amount > 1000`) / `never` (only if reversible AND
   `accelerator.yaml.solution.hitl = none`)
6. **Which worker agent uses it** (must already exist)
7. **Auth approach** (Managed Identity / OAuth-via-KeyVault)

## Create `src/tools/<tool_name>.py`
```python
"""<Tool display name> — side-effect tool.

Operation: <verb + object>
External system: <system>
HITL: <policy>
Auth: <approach>
"""
from __future__ import annotations
from typing import Any
from azure.identity import DefaultAzureCredential
from ..accelerator_baseline.hitl import checkpoint, HITLDenied
from ..accelerator_baseline.telemetry import emit_event, Event


TOOL_NAME = "<tool_name>"

# Module-level constant. The accelerator-lint `hitl-required` rule
# scans every `src/tools/*.py` file for `HITL_POLICY` to identify
# side-effect tools — without it, the file is treated as read-only and
# the HITL gate is not enforced. Set to "always" / "never" /
# "threshold:<expr>" per the custom agent prompt above.
HITL_POLICY = "<always | never | threshold:amount > 1000>"


INPUT_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}


async def run(args: dict[str, Any]) -> dict[str, Any]:
    await checkpoint(tool=TOOL_NAME, args=args, policy=HITL_POLICY)

    credential = DefaultAzureCredential()
    # call external system
    result: dict[str, Any] = {}

    emit_event(Event(
        name=f"tool.{TOOL_NAME}.executed",
        args_redacted={k: _redact(v) for k, v in args.items()},
        external_system="<system>",
        ok=True,
    ))
    return result


def _redact(v: Any) -> Any:
    return v
```

> **Why `HITL_POLICY` is a module-level constant.** The `accelerator-lint`
> rule `hitl-required` scans `src/tools/*.py` for that exact identifier to
> identify side-effect tools. If you bury the policy as an inline argument to
> `checkpoint(...)`, lint treats the file as read-only and never checks for the
> HITL gate. Threshold policies use `threshold:<expr>` with normal Python
> comparison operators.

## Register on the worker
Expose the tool in the worker's tool registry so Foundry advertises it.

## Tests
`tests/tools/test_<tool_name>.py`:
- HITL approve → tool executes
- HITL deny → raises `HITLDenied`, no external call
- Redaction → no raw PII in events

## Author + run the redteam case
Every side-effect tool ships with at least one redteam case. Author it now, then run it — both halves are required, not just authoring.

1. Add a case to `evals/redteam/cases.jsonl` exercising prompt-injection or jailbreak attempts to misuse the tool.
2. Run it:

   ```bash
   python evals/redteam/run.py --api-url <your-api-url>
   ```

   Confirm the new case appears in the output and the safety bar in `accelerator.yaml.acceptance.safety_pass` still holds.

## Verify against acceptance
Re-run the full acceptance chain to prove the new tool didn't regress the scenario:

```bash
accel evaluate --api-url <your-api-url> --execute
```

The unified evaluator reports every threshold in
`accelerator.yaml.acceptance`. If any threshold drops, fix the tool before the
PR.

## Guardrails
- NEVER skip `checkpoint(...)`.
- NEVER inline secrets; use `DefaultAzureCredential` or KeyVault references.
- NEVER use `requests` when an official SDK exists.
- Emit telemetry even on failure (`ok=False`).
- Run `scripts/accelerator-lint.py` after.
