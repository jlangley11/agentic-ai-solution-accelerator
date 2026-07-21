"""Shared validation and SSE protocol implementation."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from time import monotonic
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from src.accelerator_baseline.telemetry import Event, emit_event
from src.workflow.base import BaseWorkflow
from src.workflow.registry import ScenarioBundle

DisconnectCheck = Callable[[], Awaitable[bool]]
logger = logging.getLogger("accelerator")

SSE_HEADERS = {
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
}


def validate_payload(payload: object, schema: type[BaseModel]) -> BaseModel:
    """Validate a decoded request before any streaming response is created."""
    return schema.model_validate(payload)


async def stream_sse(
    workflow: BaseWorkflow,
    payload: BaseModel,
    is_disconnected: DisconnectCheck,
    client_error_message: str | None = None,
) -> AsyncIterator[bytes]:
    """Encode workflow events using the accelerator's stable SSE contract."""
    seq = 0
    stream_start = monotonic()
    events: AsyncIterator[dict[str, Any]] | None = None
    try:
        try:
            events = workflow.stream(payload.model_dump())
            async for event in events:
                if await is_disconnected():
                    break
                if isinstance(event, dict) and event.get("type") == "heartbeat":
                    yield b": ka\n\n"
                    continue
                seq += 1
                yield f"data: {json.dumps({**event, 'seq': seq})}\n\n".encode()
        finally:
            if events is not None:
                close = getattr(events, "aclose", None)
                if close is not None:
                    await close()
    except Exception as exc:
        if client_error_message is not None:
            logger.exception("SSE workflow failed")
        emit_event(
            Event(
                name="response.returned",
                ok=False,
                error=str(exc),
                value=round((monotonic() - stream_start) * 1000.0, 1),
                unit="ms",
            )
        )
        seq += 1
        error = {
            "type": "error",
            "message": client_error_message if client_error_message is not None else str(exc),
            "seq": seq,
        }
        yield f"data: {json.dumps(error)}\n\n".encode()
    seq += 1
    yield f"data: {json.dumps({'type': 'done', 'seq': seq})}\n\n".encode()


def sse_response(
    workflow: BaseWorkflow,
    payload: BaseModel,
    is_disconnected: DisconnectCheck,
    client_error_message: str | None = None,
) -> StreamingResponse:
    """Construct an SSE response for an already-validated payload."""
    return StreamingResponse(
        stream_sse(
            workflow,
            payload,
            is_disconnected,
            client_error_message=client_error_message,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def make_fastapi_stream_endpoint(
    bundle: ScenarioBundle,
) -> Callable[[Request], Awaitable[StreamingResponse]]:
    """Build the current FastAPI route while keeping validation pre-stream."""
    schema = bundle.request_schema
    workflow = bundle.workflow

    async def stream_endpoint(request: Request) -> StreamingResponse:
        try:
            raw_payload: Any = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            payload = validate_payload(raw_payload, schema)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        return sse_response(workflow, payload, request.is_disconnected)

    stream_endpoint.__name__ = f"{bundle.id.replace('-', '_')}_stream"
    return stream_endpoint
