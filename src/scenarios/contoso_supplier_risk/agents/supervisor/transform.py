"""Normalise supervisor output to a dict."""
from __future__ import annotations

import json
from typing import Any


def transform_response(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {"text": raw}
