"""FastAPI entrypoint - loads the scenario declared in ``accelerator.yaml``.

Key properties (enforced by scripts/accelerator-lint.py):
- DefaultAzureCredential only; no secrets in env.
- OpenTelemetry configured at startup for App Insights correlation.
- SSE streaming for agent progress; no WebSockets / long polling.
- Foundry agent system instructions live in `docs/agent-specs/*.md`;
  the provisioner syncs them before serving.
- No scenario-specific imports here - all scenario wiring comes from the
  manifest via :mod:`src.workflow.registry`.
- CORS allow-list driven by the ``ALLOWED_ORIGINS`` env var (comma-separated
  list of exact origins, or ``*`` for sandbox-only allow-all). Empty default
  is production-safe: no cross-origin browser calls until the deployer opts in.
- The default self-host invokes :mod:`src.bootstrap` synchronously inside the
  ``lifespan`` startup phase. The same implementation is also callable through
  :mod:`src.provisioning` before an opt-in hosted runtime starts.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .bootstrap import bootstrap as run_bootstrap
from .config.settings import load_settings
from .serving.sse import make_fastapi_stream_endpoint as _make_stream_endpoint
from .workflow.registry import load_scenario

logger = logging.getLogger("accelerator")
logging.basicConfig(level=logging.INFO)


def _configure_otel(app: FastAPI) -> None:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor  # type: ignore
    except Exception:
        logger.warning("azure-monitor-opentelemetry not installed; OTel disabled.")
        return
    s = load_settings()
    if not s.appinsights_connection:
        return
    configure_azure_monitor(
        connection_string=s.appinsights_connection,
        logger_name="accelerator",
    )
    # FastAPI auto-instrumentation creates a parent ``requests`` span per HTTP
    # request, so every ``emit_event(...)`` inside the workflow gets correlated
    # to a single distributed-trace operation_Id in App Insights.
    try:
        from opentelemetry.instrumentation.fastapi import (  # type: ignore
            FastAPIInstrumentor,
        )

        FastAPIInstrumentor.instrument_app(app)
        logger.info("App Insights wired up (FastAPI auto-instrumentation enabled).")
    except Exception as exc:  # noqa: BLE001 — instrumentation is best-effort
        logger.warning("FastAPI auto-instrumentation skipped: %s", exc)
        logger.info("App Insights wired up.")


def _configure_cors(app: FastAPI) -> None:
    """Install CORS middleware from ``ALLOWED_ORIGINS``.

    The env var is a comma-separated list of exact origins
    (e.g. ``http://localhost:5173,https://contoso.example.com``). The literal
    value ``*`` enables allow-all without credentials — sandbox-only.
    Empty / unset means no cross-origin allowed: the API is server-to-server
    until the deployer explicitly opts in. This is the production-safe default.

    Read directly from ``os.environ`` (not via :func:`load_settings`) so this
    can run before Foundry / Search env vars are present — e.g. in unit-test
    smoke checks of the FastAPI app object.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        return
    if origins == ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        logger.info("CORS: allow-all (sandbox mode).")
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info("CORS: allow-listed %d origin(s).", len(origins))


app = FastAPI(
    title="Agentic AI Solution Accelerator",
    version="0.1.0",
    lifespan=None,  # set below once _bundle is loaded
)
_configure_otel(app)
_configure_cors(app)
_bundle = load_scenario()
logger.info("loaded scenario %r at %s", _bundle.id, _bundle.endpoint_path)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run deploy-time bootstrap before accepting traffic.

    See :mod:`src.bootstrap` for the contract. Failure here propagates and
    aborts uvicorn startup — that is the intended fail-closed signal for
    ``azd up`` (ACA marks the revision unhealthy).
    """
    await run_bootstrap(_bundle)
    # Pre-warm credential and agent version cache so the first user
    # request does not pay a cold-start penalty.
    if hasattr(_bundle.workflow, "warmup"):
        try:
            await _bundle.workflow.warmup()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 — warmup is best-effort
            logger.debug("workflow.warmup skipped: %s", exc)
    yield


app.router.lifespan_context = _lifespan
app.add_api_route(
    _bundle.endpoint_path,
    _make_stream_endpoint(_bundle),
    methods=["POST"],
    name=f"scenario-{_bundle.id}",
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "scenario": _bundle.id}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)  # noqa: S104  # bind-all expected for containerized app
