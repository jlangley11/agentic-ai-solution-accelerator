"""risk_scorer agent.

Score supplier risk factors with rationale and policy references. The
agent's system instructions live in
``docs/agent-specs/accel-contoso-supplier-risk-risk-scorer.md`` and are
synced to Foundry by ``src/bootstrap.py``; this module only shapes I/O
(prompt / transform / validate).
"""
from .prompt import build_prompt
from .transform import transform_response
from .validate import validate_response

AGENT_NAME = "accel-contoso-supplier-risk-risk-scorer"

__all__ = ["AGENT_NAME", "build_prompt", "transform_response", "validate_response"]
