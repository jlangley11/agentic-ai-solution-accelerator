from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

import src.provisioning as provisioning
import src.workflow.harness as harness_module
from src.agent_specs import parse_agent_instructions
from src.workflow.harness import HarnessWorkflow, harness_model_deployment


class FakeCredential:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeAgent:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.session = object()
        self.prompt = ""

    def create_session(self) -> object:
        return self.session

    async def run(self, prompt: str, *, session: object) -> Any:
        assert session is self.session
        self.prompt = prompt
        return SimpleNamespace(text=self.raw)


class BlockingAgent:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    def create_session(self) -> object:
        return object()

    async def run(self, _prompt: str, *, session: object) -> Any:
        assert session is not None
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()


def _context(*, retrieval: str = "none") -> SimpleNamespace:
    return SimpleNamespace(
        agents=(
            SimpleNamespace(
                id="primary",
                foundry_name="accel-demo-primary",
                retrieval=(
                    None
                    if retrieval == "none"
                    else SimpleNamespace(mode=retrieval)
                ),
            ),
        ),
        implementation=SimpleNamespace(implementation_pattern="harness"),
    )


def _spec(tmp_path) -> None:
    path = tmp_path / "accel-demo-primary.md"
    path.write_text(
        "# Demo\n\n## Instructions\n\nReturn the required JSON object.\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_harness_runs_with_safe_released_features(
    tmp_path,
    monkeypatch,
) -> None:
    _spec(tmp_path)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "platform-model")
    monkeypatch.setenv("AZURE_AI_FOUNDRY_MODEL", "manifest-model")
    credential = FakeCredential()
    client_args: dict[str, Any] = {}
    agent_args: dict[str, Any] = {}
    fake_agent = FakeAgent('{"result":{"answer":"done"}}')

    def client_factory(**kwargs):
        client_args.update(kwargs)
        return object()

    def agent_factory(**kwargs):
        agent_args.update(kwargs)
        return fake_agent

    workflow = HarnessWorkflow(
        context=_context(),
        build_prompt=lambda request: json.dumps(request, sort_keys=True),
        transform_response=json.loads,
        validate_response=lambda value: ("result" in value, "missing result"),
        specs_dir=tmp_path,
        credential_factory=lambda: credential,
        client_factory=client_factory,
        agent_factory=agent_factory,
    )

    events = [event async for event in workflow.stream({"query": "demo"})]

    assert [event["type"] for event in events] == [
        "status",
        "briefing_ready",
        "final",
    ]
    assert events[-1]["briefing"]["result"]["answer"] == "done"
    assert client_args["model"] == "platform-model"
    assert agent_args["disable_file_memory"] is True
    assert agent_args["file_access_store"] is None
    assert agent_args["background_agents"] is None
    assert agent_args["shell_executor"] is None
    assert agent_args["disable_web_search"] is True
    assert agent_args["disable_tool_auto_approval"] is True
    assert agent_args["loop_should_continue"] is None
    assert agent_args["tools"] is None
    assert agent_args["otel_provider_name"] == "accelerator.harness"
    assert fake_agent.prompt == '{"query": "demo"}'
    assert credential.closed is True


def test_harness_model_requires_a_deployment(monkeypatch) -> None:
    for name in (
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "AZURE_AI_FOUNDRY_MODEL",
        "FOUNDRY_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="Required model env var"):
        harness_model_deployment()


def test_harness_rejects_retrieval_until_tool_bridge_exists(tmp_path) -> None:
    _spec(tmp_path)

    with pytest.raises(ValueError, match="retrieval mode 'none'"):
        HarnessWorkflow(
            context=_context(retrieval="foundry_tool"),
            build_prompt=lambda request: str(request),
            transform_response=lambda raw: {"result": raw},
            validate_response=lambda value: (True, ""),
            specs_dir=tmp_path,
        )


def test_agent_spec_parser_rejects_inline_model(tmp_path) -> None:
    path = tmp_path / "agent.md"
    path.write_text(
        "# Agent\n\n**Model:** forbidden\n\n## Instructions\n\nDo work.\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Model"):
        parse_agent_instructions(path)


@pytest.mark.asyncio
async def test_harness_skips_prompt_agent_version_provisioning(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    _spec(tmp_path)
    caplog.set_level("INFO", logger="accelerator.bootstrap")
    monkeypatch.setattr(provisioning, "SPECS_DIR", tmp_path)
    monkeypatch.setattr(
        provisioning,
        "foundry_project_endpoint",
        lambda: "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setattr(
        provisioning,
        "_parse_model_map",
        lambda: {"default": "gpt-5-mini"},
    )
    bundle = SimpleNamespace(
        implementation=SimpleNamespace(implementation_pattern="harness"),
        agents=(
            SimpleNamespace(
                foundry_name="accel-demo-primary",
                retrieval=None,
            ),
        ),
    )

    await provisioning._bootstrap_foundry(bundle)

    assert "skipping prompt-agent version provisioning" in caplog.text


@pytest.mark.asyncio
async def test_harness_heartbeat_allows_disconnect_cancellation(
    tmp_path,
    monkeypatch,
) -> None:
    _spec(tmp_path)
    monkeypatch.setenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "platform-model")
    monkeypatch.setattr(harness_module, "HARNESS_HEARTBEAT_SECONDS", 0.01)
    credential = FakeCredential()
    blocking_agent = BlockingAgent()
    workflow = HarnessWorkflow(
        context=_context(),
        build_prompt=lambda request: json.dumps(request),
        transform_response=json.loads,
        validate_response=lambda value: (True, ""),
        specs_dir=tmp_path,
        credential_factory=lambda: credential,
        client_factory=lambda **_kwargs: object(),
        agent_factory=lambda **_kwargs: blocking_agent,
    )
    stream = workflow.stream({"query": "demo"})

    assert (await anext(stream))["type"] == "status"
    heartbeat = await asyncio.wait_for(anext(stream), timeout=1)
    assert heartbeat == {"type": "heartbeat"}
    await stream.aclose()

    await asyncio.wait_for(blocking_agent.cancelled.wait(), timeout=1)
    assert credential.closed is True
