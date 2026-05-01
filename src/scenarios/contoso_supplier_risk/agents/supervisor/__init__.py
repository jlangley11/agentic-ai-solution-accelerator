"""Supervisor agent for contoso-supplier-risk."""
from .prompt import build_prompt
from .transform import transform_response
from .validate import validate_response

AGENT_NAME = "accel-contoso-supplier-risk-supervisor"
__all__ = ["AGENT_NAME", "build_prompt", "transform_response", "validate_response"]
