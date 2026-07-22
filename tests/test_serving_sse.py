from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from src.serving.sse import make_fastapi_stream_endpoint, stream_sse, validate_payload
from src.workflow.registry import ScenarioBundle


class RequestModel(BaseModel):
    company_name: str


class ResponseModel(BaseModel):
    ok: bool


class StubWorkflow:
    def __init__(self, events: list[dict[str, Any]], error: Exception | None = None) -> None:
        self.events = events
        self.error = error
        self.closed = False

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        try:
            for event in self.events:
                yield event
            if self.error:
                raise self.error
        finally:
            self.closed = True


class ConstructionErrorWorkflow:
    def stream(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        raise RuntimeError("iterator construction failed")


def _bundle(
    workflow: StubWorkflow,
    response_schema: type[BaseModel] | None = None,
) -> ScenarioBundle:
    return ScenarioBundle(
        id="test-scenario",
        package="tests",
        request_schema=RequestModel,
        workflow=workflow,  # type: ignore[arg-type]
        endpoint_path="/research/stream",
        agents=(),
        retrieval_indexes=(),
        evals_quality="",
        evals_redteam="",
        response_schema=response_schema,
    )


async def _connected() -> bool:
    return False


@pytest.mark.asyncio
async def test_sse_preserves_heartbeat_and_monotonic_sequence() -> None:
    workflow = StubWorkflow(
        [
            {"type": "status", "stage": "starting"},
            {"type": "heartbeat"},
            {"type": "final", "briefing": {"ok": True}},
        ]
    )
    payload = validate_payload({"company_name": "Contoso"}, RequestModel)

    chunks = [chunk async for chunk in stream_sse(workflow, payload, _connected)]

    assert chunks[1] == b": ka\n\n"
    data = [
        json.loads(chunk.removeprefix(b"data: ").removesuffix(b"\n\n"))
        for chunk in chunks
        if chunk.startswith(b"data: ")
    ]
    assert [event["seq"] for event in data] == [1, 2, 3]
    assert [event["type"] for event in data] == ["status", "final", "done"]


@pytest.mark.asyncio
async def test_sse_emits_error_then_terminal_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted = []
    monkeypatch.setattr("src.serving.sse.emit_event", emitted.append)
    workflow = StubWorkflow([], RuntimeError("workflow failed"))
    payload = validate_payload({"company_name": "Contoso"}, RequestModel)

    chunks = [chunk async for chunk in stream_sse(workflow, payload, _connected)]
    data = [
        json.loads(chunk.removeprefix(b"data: ").removesuffix(b"\n\n"))
        for chunk in chunks
    ]

    assert data == [
        {"type": "error", "message": "workflow failed", "seq": 1},
        {"type": "done", "seq": 2},
    ]
    assert len(emitted) == 1
    assert emitted[0].name == "response.returned"
    assert emitted[0].ok is False


@pytest.mark.asyncio
async def test_sse_handles_synchronous_iterator_construction_error() -> None:
    payload = validate_payload({"company_name": "Contoso"}, RequestModel)

    chunks = [
        chunk
        async for chunk in stream_sse(
            ConstructionErrorWorkflow(),  # type: ignore[arg-type]
            payload,
            _connected,
        )
    ]
    data = [
        json.loads(chunk.removeprefix(b"data: ").removesuffix(b"\n\n"))
        for chunk in chunks
    ]

    assert data == [
        {"type": "error", "message": "iterator construction failed", "seq": 1},
        {"type": "done", "seq": 2},
    ]


@pytest.mark.asyncio
async def test_sse_validates_and_normalizes_final_response() -> None:
    workflow = StubWorkflow(
        [{"type": "final", "briefing": {"ok": True, "ignored": "extra"}}]
    )
    payload = validate_payload({"company_name": "Contoso"}, RequestModel)

    chunks = [
        chunk
        async for chunk in stream_sse(
            workflow,
            payload,
            _connected,
            response_schema=ResponseModel,
        )
    ]
    data = [
        json.loads(chunk.removeprefix(b"data: ").removesuffix(b"\n\n"))
        for chunk in chunks
    ]

    assert data[0] == {
        "type": "final",
        "briefing": {"ok": True},
        "seq": 1,
    }


@pytest.mark.asyncio
async def test_sse_rejects_invalid_final_response_before_emitting_it() -> None:
    workflow = StubWorkflow([{"type": "final", "briefing": {"wrong": True}}])
    payload = validate_payload({"company_name": "Contoso"}, RequestModel)

    chunks = [
        chunk
        async for chunk in stream_sse(
            workflow,
            payload,
            _connected,
            response_schema=ResponseModel,
        )
    ]
    data = [
        json.loads(chunk.removeprefix(b"data: ").removesuffix(b"\n\n"))
        for chunk in chunks
    ]

    assert [event["type"] for event in data] == ["error", "done"]
    assert "final" not in {event["type"] for event in data}


@pytest.mark.asyncio
async def test_sse_rejects_invalid_briefing_ready_before_later_actions() -> None:
    workflow = StubWorkflow(
        [
            {"type": "briefing_ready", "briefing": {"wrong": True}},
            {"type": "tool_result", "tool": "send_email", "result": "sent"},
            {"type": "final", "briefing": {"ok": True}},
        ]
    )
    payload = validate_payload({"company_name": "Contoso"}, RequestModel)

    chunks = [
        chunk
        async for chunk in stream_sse(
            workflow,
            payload,
            _connected,
            response_schema=ResponseModel,
        )
    ]
    data = [
        json.loads(chunk.removeprefix(b"data: ").removesuffix(b"\n\n"))
        for chunk in chunks
    ]

    assert [event["type"] for event in data] == ["error", "done"]
    assert workflow.closed


@pytest.mark.asyncio
async def test_sse_disconnect_closes_workflow_and_still_terminates() -> None:
    workflow = StubWorkflow([{"type": "status"}, {"type": "final"}])
    payload = validate_payload({"company_name": "Contoso"}, RequestModel)

    async def disconnected() -> bool:
        return True

    chunks = [chunk async for chunk in stream_sse(workflow, payload, disconnected)]

    assert chunks == [b'data: {"type": "done", "seq": 1}\n\n']
    assert workflow.closed


def test_validation_is_synchronous() -> None:
    with pytest.raises(ValidationError):
        validate_payload({}, RequestModel)


def test_fastapi_route_preserves_validation_status_headers_and_body() -> None:
    workflow = StubWorkflow([{"type": "final", "briefing": {"ok": True}}])
    bundle = _bundle(workflow, ResponseModel)
    app = FastAPI()
    app.add_api_route(
        bundle.endpoint_path,
        make_fastapi_stream_endpoint(bundle),
        methods=["POST"],
        name=f"scenario-{bundle.id}",
    )

    with TestClient(app) as client:
        invalid_json = client.post(
            bundle.endpoint_path,
            content="{",
            headers={"Content-Type": "application/json"},
        )
        invalid_schema = client.post(bundle.endpoint_path, json={})
        response = client.post(bundle.endpoint_path, json={"company_name": "Contoso"})

    assert invalid_json.status_code == 400
    assert invalid_schema.status_code == 422
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["connection"] == "keep-alive"
    assert response.content == (
        b'data: {"type": "final", "briefing": {"ok": true}, "seq": 1}\n\n'
        b'data: {"type": "done", "seq": 2}\n\n'
    )


def test_fastapi_route_hides_invalid_response_schema_details() -> None:
    workflow = StubWorkflow([{"type": "final", "briefing": {"wrong": True}}])
    bundle = _bundle(workflow, ResponseModel)
    app = FastAPI()
    app.add_api_route(
        bundle.endpoint_path,
        make_fastapi_stream_endpoint(bundle),
        methods=["POST"],
    )

    with TestClient(app) as client:
        response = client.post(
            bundle.endpoint_path,
            json={"company_name": "Contoso"},
        )

    assert "The workflow could not complete the response." in response.text
    assert "validation error" not in response.text.lower()
    assert '"type": "final"' not in response.text
