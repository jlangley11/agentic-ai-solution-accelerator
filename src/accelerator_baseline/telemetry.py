"""Telemetry primitives.

Typed events emitted by every part of the accelerator. Partners add KPI-
specific events declared in ``accelerator.yaml.kpis``. Do NOT use ``print``
or ad-hoc logging for observability — route through this module so that:

1. Event schemas stay consistent and greppable across partners.
2. PII redaction happens in one place.
3. OpenTelemetry spans wrap Foundry + tool calls for App Insights correlation.
"""
from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from opentelemetry import trace

logger = logging.getLogger("accelerator.telemetry")
tracer = trace.get_tracer("accelerator")


# ---------------------------------------------------------------------------
# Event schema — extend per engagement (keep types; don't repurpose names)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Event:
    name: str
    args_redacted: Mapping[str, Any] = field(default_factory=dict)
    external_system: str | None = None
    ok: bool = True
    error: str | None = None
    # numeric payload (for duration/cost/ratio kpis)
    value: float | None = None
    unit: str | None = None


# KPI registry — supervisor/scaffold-from-brief appends entries here from
# accelerator.yaml.kpis[]. Each engagement pins its KPI events here so lint
# can verify parity between YAML and code.
KPI_EVENTS: set[str] = {
    "request.received",
    "supervisor.routed",
    "worker.completed",
    "worker.skipped",
    "tool.executed",
    "tool.hitl_approved",
    "tool.hitl_rejected",
    "aggregator.composed",
    "response.returned",
    # contoso-supplier-risk KPIs (accelerator.yaml -> kpis[]).
    # Wire emitters from src/scenarios/contoso_supplier_risk/workflow.py
    # and the case_drafter HITL aggregator.
    "supplier_review_cycle_time",
    "autonomous_triage_coverage",
    "hitl_approval_rate",
}


def emit_event(event: Event) -> None:
    """Emit a typed event to App Insights via the OTel-wired logger.

    **Canonical query surface: the App Insights ``traces`` table.** Each event
    becomes a log record with ``message == event.name`` and flattened attributes
    available as ``customDimensions.<attr>``. Booleans are normalised to the
    JSON-style strings ``"true"`` / ``"false"`` so KQL queries can use the
    obvious form; cast explicitly with ``tobool()`` for safety. Example::

        traces
        | where message == "response.returned"
        | where tobool(customDimensions.ok) == true
        | summarize count() by bin(timestamp, 1d)

    Correlation to the active distributed trace happens automatically: the
    Azure Monitor logging handler stamps the row with the active span's
    ``operation_Id`` / ``operation_ParentId``. We deliberately do **not** also
    call ``span.add_event(...)`` — the Azure Monitor exporter materialises
    span events as their own ``traces`` rows, which would double-count every
    business event. Use real child spans (around tool calls, retrieval,
    model calls) for waterfall timing; ``emit_event`` is for queryable KPIs.

    Why the unconditional log: ``configure_azure_monitor(logger_name="accelerator")``
    pipes ``accelerator.*`` loggers through the Azure Monitor exporter. Relying
    on ``span.add_event`` alone silently dropped events because async streaming
    paths often had no recording parent span.
    """
    payload = asdict(event)
    flat = _otel_flatten(payload)

    # `name` collides with stdlib ``logging.LogRecord.name``; reroute to
    # ``event_name`` so the log record fields don't blow up at emit time.
    # ``event_name`` is also the field consumers should filter on in KQL to
    # distinguish accelerator events from generic traces.
    flat.pop("name", None)
    flat["event_name"] = event.name

    # Single emission: log only. Span context is attached by the OTel logging
    # handler so ``operation_Id`` / ``operation_ParentId`` correlate the row
    # to the active request span without producing a duplicate.
    logger.info(event.name, extra=flat)


def _otel_flatten(payload: Mapping[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, Mapping):
            for kk, vv in v.items():
                flat[f"{k}.{kk}"] = _stringify(vv)
        else:
            flat[k] = _stringify(v)
    return flat


def _stringify(v: Any) -> Any:
    # Bool branch must come before the int branch -- ``bool`` is a subclass
    # of ``int`` in Python and would otherwise pass through as ``True``/``False``.
    # Azure Monitor's logging exporter serialises Python bools using their
    # ``repr`` (``"True"`` / ``"False"``), which trips KQL queries that
    # naturally reach for the JSON-style ``'true'`` / ``'false'``. Normalise
    # to the JSON form here so customDimensions stay query-friendly.
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (str, int, float)) or v is None:
        return v
    return str(v)


def _appinsights_configured() -> bool:
    # azure-monitor-opentelemetry honors this env var
    return bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))
