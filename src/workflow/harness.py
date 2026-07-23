"""Production-safe Microsoft Agent Framework Harness workflow."""
from __future__ import annotations

import asyncio
import os
import pathlib
import warnings
from collections.abc import Callable
from time import monotonic
from typing import Any, AsyncIterator

with warnings.catch_warnings():
    # Importing the stable Harness currently imports its opt-in experimental
    # file-store type and emits a warning even though this runtime disables it.
    warnings.filterwarnings(
        "ignore",
        message=r"\[HARNESS\] AgentFileStore is experimental.*",
    )
    from agent_framework import create_harness_agent
    from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from src.accelerator_baseline.killswitch import assert_enabled
from src.accelerator_baseline.telemetry import Event, emit_event
from src.agent_specs import SPECS_DIR, parse_agent_instructions
from src.config.settings import foundry_project_endpoint

PromptBuilder = Callable[[dict[str, Any]], str]
ResponseTransformer = Callable[[str], dict[str, Any]]
ResponseValidator = Callable[[dict[str, Any]], tuple[bool, str]]
HARNESS_HEARTBEAT_SECONDS = 15.0


def harness_model_deployment() -> str:
    """Resolve the platform-injected model first, then accelerator fallbacks."""
    for name in (
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "AZURE_AI_FOUNDRY_MODEL",
        "FOUNDRY_MODEL",
    ):
        value = os.environ.get(name)
        if value:
            return value
    raise RuntimeError(
        "Required model env var 'AZURE_AI_MODEL_DEPLOYMENT_NAME', "
        "'AZURE_AI_FOUNDRY_MODEL', or 'FOUNDRY_MODEL' is not set."
    )


class HarnessWorkflow:
    """Run one request through a fresh, safe Harness agent session."""

    validated_partials = False

    def __init__(
        self,
        *,
        context: Any,
        build_prompt: PromptBuilder,
        transform_response: ResponseTransformer,
        validate_response: ResponseValidator,
        specs_dir: pathlib.Path = SPECS_DIR,
        credential_factory: Callable[[], Any] | None = None,
        client_factory: Callable[..., Any] | None = None,
        agent_factory: Callable[..., Any] | None = None,
    ) -> None:
        agents = tuple(getattr(context, "agents", ()) or ())
        if len(agents) != 1:
            raise ValueError("Harness scenarios must declare exactly one primary agent.")
        if getattr(agents[0], "id", None) != "primary":
            raise ValueError("Harness scenario agent id must be 'primary'.")
        implementation = getattr(context, "implementation", None)
        if getattr(implementation, "implementation_pattern", None) != "harness":
            raise ValueError("HarnessWorkflow requires implementation_pattern='harness'.")
        retrieval = getattr(agents[0], "retrieval", None)
        if retrieval is not None and getattr(retrieval, "mode", "none") != "none":
            raise ValueError(
                "Harness scenarios currently support retrieval mode 'none' only."
            )
        spec_path = specs_dir / f"{agents[0].foundry_name}.md"
        if not spec_path.exists():
            raise RuntimeError(f"Missing Harness agent spec: {spec_path}")
        self._agent_id = agents[0].id
        self._agent_name = agents[0].foundry_name
        self._instructions = parse_agent_instructions(spec_path)
        self._build_prompt = build_prompt
        self._transform_response = transform_response
        self._validate_response = validate_response
        self._credential_factory = credential_factory or DefaultAzureCredential
        self._client_factory = client_factory or FoundryChatClient
        self._agent_factory = agent_factory or create_harness_agent

    async def stream(
        self,
        request: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        assert_enabled("workflow")
        started = monotonic()
        emit_event(
            Event(
                name="request.received",
                args_redacted={
                    "implementation_pattern": "harness",
                    "agent": self._agent_id,
                },
            )
        )
        yield {"type": "status", "stage": "harness.planning"}
        prompt = self._build_prompt(request)
        credential = self._credential_factory()
        run_task: asyncio.Future[Any] | None = None
        try:
            client = self._client_factory(
                project_endpoint=foundry_project_endpoint(),
                model=harness_model_deployment(),
                credential=credential,
            )
            agent = self._agent_factory(
                client=client,
                id=self._agent_name,
                name=self._agent_name,
                agent_instructions=self._instructions,
                tools=None,
                disable_file_memory=True,
                file_access_store=None,
                background_agents=None,
                shell_executor=None,
                disable_web_search=True,
                disable_tool_auto_approval=True,
                loop_should_continue=None,
                otel_provider_name="accelerator.harness",
            )
            session = agent.create_session()
            run_task = asyncio.ensure_future(agent.run(prompt, session=session))
            while True:
                done, _pending = await asyncio.wait(
                    {run_task},
                    timeout=HARNESS_HEARTBEAT_SECONDS,
                )
                if run_task in done:
                    response = run_task.result()
                    break
                yield {"type": "heartbeat"}
        finally:
            if run_task is not None and not run_task.done():
                run_task.cancel()
                await asyncio.gather(run_task, return_exceptions=True)
            close = getattr(credential, "close", None)
            if callable(close):
                close()
        raw = getattr(response, "text", None)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Harness agent returned an empty response.")
        transformed = self._transform_response(raw)
        valid, reason = self._validate_response(transformed)
        if not valid:
            raise ValueError(f"Harness response validation failed: {reason}")
        elapsed_ms = round((monotonic() - started) * 1000.0, 1)
        emit_event(
            Event(
                name="response.returned",
                ok=True,
                args_redacted={
                    "implementation_pattern": "harness",
                    "agent": self._agent_id,
                },
                value=elapsed_ms,
                unit="ms",
            )
        )
        yield {"type": "briefing_ready", "briefing": transformed}
        yield {"type": "final", "briefing": transformed}
