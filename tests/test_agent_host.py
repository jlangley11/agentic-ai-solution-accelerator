from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.agent_host import _progress_text, create_app
from src.workflow.registry import ScenarioBundle


class HostedRequest(BaseModel):
    company_name: str
    seller_intent: str
    tags: list[str]
    persona: str = "Decision maker"


class HostedWorkflow:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        self.requests.append(request)
        briefing = {"request": request, "ok": True}
        yield {"type": "status", "stage": "working"}
        yield {"type": "heartbeat"}
        yield {"type": "briefing_ready", "briefing": briefing}
        yield {"type": "final", "briefing": briefing}


class BlockingWorkflow:
    def __init__(self) -> None:
        self.blocked = asyncio.Event()
        self.closed = asyncio.Event()

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        try:
            yield {"type": "status", "stage": "started"}
            self.blocked.set()
            await asyncio.Event().wait()
        finally:
            self.closed.set()


class FailingWorkflow:
    async def stream(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        raise RuntimeError("internal database detail")
        yield  # pragma: no cover


def _bundle(
    workflow: HostedWorkflow | BlockingWorkflow | FailingWorkflow,
) -> ScenarioBundle:
    return ScenarioBundle(
        id="hosted-test",
        package="tests",
        request_schema=HostedRequest,
        workflow=workflow,  # type: ignore[arg-type]
        endpoint_path="/research/stream",
        agents=(),
        retrieval_indexes=(),
        evals_quality="",
        evals_redteam="",
    )


def _response_events(response_text: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in response_text.splitlines()
        if line.startswith("data: ")
    ]


def test_dual_host_exposes_public_protocol_routes() -> None:
    app = create_app(_bundle(HostedWorkflow()))
    routes = {route.path for route in app.routes}

    assert {"/invocations", "/responses", "/readiness"} <= routes


def test_invocations_validation_and_sse_streaming() -> None:
    workflow = HostedWorkflow()
    app = create_app(_bundle(workflow))

    with TestClient(app) as client:
        invalid_json = client.post(
            "/invocations",
            content="{",
            headers={"Content-Type": "application/json"},
        )
        invalid_schema = client.post("/invocations", json={})
        response = client.post(
            "/invocations",
            json={
                "company_name": "Contoso",
                "seller_intent": "Prepare",
                "tags": [],
            },
        )

    assert invalid_json.status_code == 400
    assert invalid_schema.status_code == 422
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert b": ka\n\n" in response.content
    data = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["seq"] for event in data] == [1, 2, 3, 4]
    assert [event["type"] for event in data] == [
        "status",
        "briefing_ready",
        "final",
        "done",
    ]


def test_invocations_hide_unexpected_workflow_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(_bundle(FailingWorkflow()))

    with TestClient(app) as client:
        response = client.post(
            "/invocations",
            json={
                "company_name": "Contoso",
                "seller_intent": "Prepare",
                "tags": [],
            },
        )

    assert response.status_code == 200
    assert "The workflow could not complete the invocation." in response.text
    assert "internal database detail" not in response.text
    assert any(record.message == "SSE workflow failed" for record in caplog.records)


def test_responses_structured_json_streams_progress_and_final_output() -> None:
    workflow = HostedWorkflow()
    app = create_app(_bundle(workflow))
    structured = {
        "company_name": "Contoso",
        "seller_intent": "Prepare",
        "tags": ["priority"],
    }

    with TestClient(app) as client:
        response = client.post(
            "/responses",
            json={"model": "test-model", "input": json.dumps(structured), "stream": True},
        )

    assert response.status_code == 200
    assert "response.reasoning_summary_text.delta" in response.text
    assert "response.output_text.delta" in response.text
    assert "response.completed" in response.text
    events = _response_events(response.text)
    reasoning = "".join(
        event.get("delta", "")
        for event in events
        if event["type"] == "response.reasoning_summary_text.delta"
    )
    output = "".join(
        event.get("delta", "")
        for event in events
        if event["type"] == "response.output_text.delta"
    )
    assert '"stage": "working"' in reasoning
    assert "briefing_ready" not in reasoning
    assert '"company_name": "Contoso"' not in reasoning
    assert json.loads(output)["request"]["company_name"] == "Contoso"
    assert workflow.requests == [{**structured, "persona": "Decision maker"}]


def test_responses_free_text_adapts_required_strings_and_lists() -> None:
    workflow = HostedWorkflow()
    app = create_app(_bundle(workflow))

    with TestClient(app) as client:
        response = client.post(
            "/responses",
            json={"model": "test-model", "input": "Fabrikam", "stream": True},
        )

    assert response.status_code == 200
    assert "response.completed" in response.text
    events = _response_events(response.text)
    output = "".join(
        event.get("delta", "")
        for event in events
        if event["type"] == "response.output_text.delta"
    )
    assert json.loads(output)["request"]["company_name"] == "Fabrikam"
    assert workflow.requests == [
        {
            "company_name": "Fabrikam",
            "seller_intent": "",
            "tags": [],
            "persona": "Decision maker",
        }
    ]


def test_responses_reject_empty_input_with_failed_event() -> None:
    app = create_app(_bundle(HostedWorkflow()))

    with TestClient(app) as client:
        response = client.post(
            "/responses",
            json={"model": "test-model", "input": "   ", "stream": True},
        )

    assert response.status_code == 200
    assert "response.failed" in response.text
    assert "Responses input text must not be empty." in response.text


def test_responses_hide_unexpected_workflow_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(_bundle(FailingWorkflow()))

    with TestClient(app) as client:
        response = client.post(
            "/responses",
            json={"model": "test-model", "input": "Fabrikam", "stream": True},
        )

    assert response.status_code == 200
    assert "response.failed" in response.text
    assert "The workflow could not complete the response." in response.text
    assert "internal database detail" not in response.text
    assert any(record.message == "Responses workflow failed" for record in caplog.records)


@pytest.mark.asyncio
async def test_responses_cancellation_interrupts_and_closes_blocked_workflow() -> None:
    workflow = BlockingWorkflow()
    bundle = _bundle(workflow)
    payload = HostedRequest(company_name="Contoso", seller_intent="", tags=[])
    cancellation_signal = asyncio.Event()
    progress = _progress_text(bundle, payload, cancellation_signal, {})

    assert json.loads(await anext(progress))["stage"] == "started"
    blocked_next = asyncio.create_task(anext(progress))
    await asyncio.wait_for(workflow.blocked.wait(), timeout=1)
    cancellation_signal.set()

    with pytest.raises(asyncio.CancelledError, match="Response cancelled"):
        await asyncio.wait_for(blocked_next, timeout=1)
    assert workflow.closed.is_set()
