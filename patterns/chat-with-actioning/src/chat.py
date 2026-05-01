"""Chat-with-actioning variant — persistent Foundry thread + HITL tool calls."""
from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from agent_framework.azure import AzureAIClient  # type: ignore
except Exception:  # pragma: no cover
    AzureAIClient = None  # type: ignore

from src.accelerator_baseline.hitl import HITLDenied, checkpoint
from src.accelerator_baseline.killswitch import assert_enabled
from src.accelerator_baseline.telemetry import Event, emit_event
from src.tools import SIDE_EFFECT_TOOLS

AGENT_NAME = "accel-chat-assistant"

app = FastAPI(title="Chat-with-Actioning Accelerator", version="0.1.0")


class ChatTurnRequest(BaseModel):
    thread_id: str | None = None
    message: str


@app.post("/chat/stream")
async def chat_stream(req: ChatTurnRequest, request: Request) -> StreamingResponse:
    async def gen() -> AsyncIterator[bytes]:
        assert_enabled("workflow")
        emit_event(Event(name="request.received",
                         args_redacted={"has_thread": bool(req.thread_id)}))
        if AzureAIClient is None:
            yield b"data: {\"type\":\"error\",\"message\":\"SDK not installed\"}\n\n"
            return

        client = AzureAIClient(agent_name=AGENT_NAME, use_latest_version=True)
        agent = client.as_agent()
        thread = await agent.get_or_create_thread(req.thread_id)  # pyright: ignore[reportAttributeAccessIssue]  # SDK runtime surface; type stubs lag GA shape

        async for chunk in agent.run_stream(req.message, thread=thread):
            if await request.is_disconnected():
                break
            if getattr(chunk, "tool_call", None):
                tc = chunk.tool_call  # pyright: ignore[reportAttributeAccessIssue]  # checked via getattr above; type stubs lag GA shape
                if tc.name in SIDE_EFFECT_TOOLS:
                    fn, _schema = SIDE_EFFECT_TOOLS[tc.name]
                    try:
                        await checkpoint(tool=tc.name, args=tc.arguments, policy="always")
                    except HITLDenied:
                        yield f"data: {json.dumps({'type':'tool_denied','tool':tc.name})}\n\n".encode()
                        continue
                    result = await fn(**tc.arguments)
                    yield f"data: {json.dumps({'type':'tool_result','tool':tc.name,'result':result})}\n\n".encode()
                    continue
            text = getattr(chunk, "text", None)
            if text:
                yield f"data: {json.dumps({'type':'chunk','content':text})}\n\n".encode()

        emit_event(Event(name="response.returned", ok=True))
        yield f"data: {json.dumps({'type':'final','thread_id': thread.id})}\n\n".encode()

    return StreamingResponse(gen(), media_type="text/event-stream")
