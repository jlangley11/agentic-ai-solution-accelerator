"""Normalise evidence_retriever output to the canonical dict shape.

Coerces ``evidence_pack`` items into the tight schema the downstream
risk_scorer + case_drafter assume, and rebuilds ``sources`` from the
items themselves so a missing/inconsistent ``sources`` block from the
model never becomes a downstream KeyError.
"""
from __future__ import annotations

import json
from typing import Any

_VALID_SOURCE_SYSTEMS: frozenset[str] = frozenset({
    "sharepoint",
    "azure_sql",
    "dynamics_365_finance",
    "servicenow",
    "blob_storage",
})

_OPTIONAL_ITEM_FIELDS: tuple[str, ...] = (
    "supplier_id",
    "category",
    "country",
    "retrieved_at",
)


def _parse(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}


def _coerce_evidence_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    summary = item.get("summary")
    source = item.get("source")
    source_system = item.get("source_system")
    if not (isinstance(summary, str) and summary.strip()):
        return None
    if not (isinstance(source, str) and source.strip()):
        return None
    if source_system not in _VALID_SOURCE_SYSTEMS:
        return None
    out: dict[str, Any] = {
        "summary": summary.strip(),
        "source": source.strip(),
        "source_system": source_system,
    }
    for f in _OPTIONAL_ITEM_FIELDS:
        v = item.get(f)
        if isinstance(v, str) and v.strip():
            out[f] = v.strip()
    return out


def _dedupe_sources(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for it in items:
        key = (it["source_system"], it["source"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"source_system": it["source_system"], "source": it["source"]})
    return out


def transform_response(response: str | dict[str, Any]) -> dict[str, Any]:
    data = _parse(response)
    raw_pack = data.get("evidence_pack") or []
    pack: list[dict[str, Any]] = []
    if isinstance(raw_pack, list):
        for item in raw_pack:
            coerced = _coerce_evidence_item(item)
            if coerced is not None:
                pack.append(coerced)
    raw_gaps = data.get("coverage_gaps") or []
    gaps = [
        s.strip() for s in raw_gaps
        if isinstance(s, str) and s.strip()
    ][:5]
    return {
        "evidence_pack": pack,
        "coverage_gaps": gaps,
        "sources": _dedupe_sources(pack),
    }
