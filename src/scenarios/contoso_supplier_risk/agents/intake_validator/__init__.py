"""intake_validator agent.

Validate the supplier review intake and list any missing required inputs.
The agent's system instructions live in
``docs/agent-specs/accel-contoso-supplier-risk-intake-validator.md`` and
are synced to Foundry by ``src/bootstrap.py``; this module only shapes
I/O (prompt / transform / validate).
"""
from .prompt import build_prompt
from .transform import transform_response
from .validate import validate_response

AGENT_NAME = "accel-contoso-supplier-risk-intake-validator"

__all__ = ["AGENT_NAME", "build_prompt", "transform_response", "validate_response"]
