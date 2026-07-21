"""Opt-in Foundry Hosted Agents preview entrypoint."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any, get_origin

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponseEventStream,
    ResponsesAgentServerHost,
)
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .serving.sse import sse_response, validate_payload
from .workflow.registry import ScenarioBundle, load_scenario

logger = logging.getLogger("accelerator")
_azure_monitor_configured = False


class DualHost(InvocationAgentServerHost, ResponsesAgentServerHost):
    """Public cooperative host exposing both preview protocols."""


def _configure_azure_monitor() -> None:
    global _azure_monitor_configured
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if _azure_monitor_configured or not connection_string:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor  # type: ignore
    except ImportError:
        logger.warning("azure-monitor-opentelemetry not installed; OTel disabled.")
        return
    configure_azure_monitor(
        connection_string=connection_string,
        logger_name="accelerator",
    )
    _azure_monitor_configured = True
    logger.info("App Insights wired up for hosted-agent serving.")


def _free_text_payload(text: str, schema: type[BaseModel]) -> dict[str, Any]:
    fields = schema.model_fields
    payload: dict[str, Any] = {}
    text_field = "company_name" if "company_name" in fields else None
    if text_field is None:
        text_field = next(
            (
                name
                for name, field in fields.items()
                if field.is_required() and field.annotation is str
            ),
            None,
        )
    if text_field is not None:
        payload[text_field] = text

    for name, field in fields.items():
        if name in payload or not field.is_required():
            continue
        if field.annotation is str:
            payload[name] = ""
        elif get_origin(field.annotation) is list:
            payload[name] = []
    return payload


def _response_payload(text: str, schema: type[BaseModel]) -> BaseModel:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Responses input text must not be empty.")
    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError:
        decoded = None
    raw_payload = decoded if isinstance(decoded, dict) else _free_text_payload(stripped, schema)
    return validate_payload(raw_payload, schema)


def _progress_text(
    bundle: ScenarioBundle,
    payload: BaseModel,
    cancellation_signal: asyncio.Event,
    final_briefing: dict[str, Any],
) -> AsyncIterable[str]:
    async def iterate() -> AsyncIterator[str]:
        workflow_events = bundle.workflow.stream(payload.model_dump())
        cancellation_task = asyncio.create_task(cancellation_signal.wait())
        next_task: asyncio.Future[dict[str, Any]] | None = None
        try:
            while True:
                next_task = asyncio.ensure_future(anext(workflow_events))
                done, _ = await asyncio.wait(
                    {next_task, cancellation_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if cancellation_task in done:
                    if not next_task.done():
                        next_task.cancel()
                    await asyncio.gather(next_task, return_exceptions=True)
                    raise asyncio.CancelledError("Response cancelled.")
                try:
                    event = next_task.result()
                except StopAsyncIteration:
                    break
                finally:
                    next_task = None
                if event.get("type") == "final":
                    briefing = event.get("briefing")
                    if not isinstance(briefing, dict):
                        raise RuntimeError(
                            "Workflow final event did not contain a briefing object."
                        )
                    final_briefing.update(briefing)
                    continue
                if event.get("type") not in {"heartbeat", "briefing_ready"}:
                    yield json.dumps(event) + "\n"
        finally:
            if next_task is not None:
                if not next_task.done():
                    next_task.cancel()
                await asyncio.gather(next_task, return_exceptions=True)
            if not cancellation_task.done():
                cancellation_task.cancel()
            await asyncio.gather(cancellation_task, return_exceptions=True)
            close = getattr(workflow_events, "aclose", None)
            if close is not None:
                await close()

    return iterate()


def create_app(bundle: ScenarioBundle | None = None) -> DualHost:
    """Create the preview dual-protocol host without runtime provisioning."""
    _configure_azure_monitor()
    scenario = bundle or load_scenario()
    app = DualHost(configure_observability=None)

    @app.invoke_handler
    async def invoke(request: Request) -> Response:
        try:
            raw_payload: Any = await request.json()
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        try:
            payload = validate_payload(raw_payload, scenario.request_schema)
        except ValidationError as exc:
            return JSONResponse(
                {"detail": jsonable_encoder(exc.errors())},
                status_code=422,
            )
        return sse_response(
            scenario.workflow,
            payload,
            request.is_disconnected,
            client_error_message="The workflow could not complete the invocation.",
        )

    @app.response_handler
    async def respond(
        request: CreateResponse,
        context: ResponseContext,
        cancellation_signal: asyncio.Event,
    ) -> AsyncIterator[Any]:
        events = ResponseEventStream(
            response_id=context.response_id,
            model=request.model,
        )
        yield events.emit_created()
        yield events.emit_in_progress()
        try:
            payload = _response_payload(
                await context.get_input_text(),
                scenario.request_schema,
            )
        except ValueError as exc:
            yield events.emit_failed(message=str(exc))
            return
        try:
            final_briefing: dict[str, Any] = {}
            async for event in events.aoutput_item_reasoning_item(
                _progress_text(scenario, payload, cancellation_signal, final_briefing)
            ):
                yield event
            if not final_briefing:
                raise RuntimeError("Workflow completed without a final briefing.")
            async for event in events.aoutput_item_message(json.dumps(final_briefing)):
                yield event
            yield events.emit_completed()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - convert handler failures to protocol events
            logger.exception("Responses workflow failed")
            yield events.emit_failed(message="The workflow could not complete the response.")

    return app


app = create_app()


def main() -> None:
    """Run the hosted-preview protocol server."""
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
