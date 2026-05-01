"""Validate supervisor output shape."""
from __future__ import annotations

from typing import Any


def validate_response(data: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "supervisor output must be a JSON object"
    return True, ""
