"""Contract tests for :class:`SupervisorDAG`.

These tests exercise the scheduler's guarantees (validation, parallel exec,
fail-fast, transitive skip, concurrency cap, retrieval memoisation race, SSE
event shape) using stub agent modules — no Foundry, no AI Search, no SDK.
Run in CI via ``pytest tests/test_supervisor_dag.py``.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from src.workflow.supervisor import (
    DAGValidationError,
    SupervisorDAG,
    WorkerSpec,
    WorkerState,
    WorkerStatus,
)


# ---------------------------------------------------------------------------
# Stub agent modules
# ---------------------------------------------------------------------------
def _make_module(name: str, *, raises: bool = False, validates: bool = True) -> Any:
    def build_prompt(req: dict) -> str:
        return f"{name}: {req}"

    def transform_response(raw: str) -> dict:
        return {"agent": name, "raw": raw}

    def validate_response(data: dict) -> tuple[bool, str]:
        if validates:
            return True, ""
        return False, f"{name} failed validation"

    mod = SimpleNamespace(
        AGENT_NAME=name,
        build_prompt=build_prompt,
        transform_response=transform_response,
        validate_response=validate_response,
    )
    if raises:
        async def _unused(*_, **__):  # pragma: no cover
            raise RuntimeError("use invoke_agent to raise")
        mod.explode = _unused
    return mod


def _build(state: WorkerState) -> dict:
    return {"request": dict(state.request)}


# Invoke-agent factory --------------------------------------------------------
@dataclass
class InvokeRecorder:
    calls: list[str] = field(default_factory=list)
    max_concurrent: int = 0
    _current: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def build(self, *, delay: float = 0.0, fail_on: set[str] | None = None):
        fail_on = fail_on or set()

        async def invoke(agent_name: str, prompt: str, state: WorkerState) -> str:
            async with self._lock:
                self.calls.append(agent_name)
                self._current += 1
                if self._current > self.max_concurrent:
                    self.max_concurrent = self._current
            try:
                if delay:
                    await asyncio.sleep(delay)
                if agent_name in fail_on:
                    raise RuntimeError(f"simulated failure: {agent_name}")
                return json.dumps({"ok": True, "agent": agent_name})
            finally:
                async with self._lock:
                    self._current -= 1

        return invoke


async def _drain(dag: SupervisorDAG, state: WorkerState) -> list[dict]:
    events: list[dict] = []
    async for evt in dag.run(state):
        events.append(evt)
    return events


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_validation_self_dependency():
    mod = _make_module("a")
    workers = {
        "a": WorkerSpec(
            id="a", module=mod, build_input=_build,
            depends_on=frozenset({"a"}),
        ),
    }
    with pytest.raises(DAGValidationError, match="self-dependency"):
        SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())


def test_validation_unknown_dep():
    mod = _make_module("a")
    workers = {
        "a": WorkerSpec(
            id="a", module=mod, build_input=_build,
            depends_on=frozenset({"ghost"}),
        ),
    }
    with pytest.raises(DAGValidationError, match="unknown dependency"):
        SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())


def test_validation_key_mismatch():
    mod = _make_module("a")
    workers = {"wrong": WorkerSpec(id="a", module=mod, build_input=_build)}
    with pytest.raises(DAGValidationError, match="!= spec.id"):
        SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())


def test_validation_missing_module_attr():
    bad = SimpleNamespace(AGENT_NAME="a", build_prompt=lambda r: "")
    workers = {"a": WorkerSpec(id="a", module=bad, build_input=_build)}
    with pytest.raises(DAGValidationError, match="missing attribute"):
        SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())


def test_validation_cycle():
    a, b = _make_module("a"), _make_module("b")
    workers = {
        "a": WorkerSpec(id="a", module=a, build_input=_build,
                        depends_on=frozenset({"b"})),
        "b": WorkerSpec(id="b", module=b, build_input=_build,
                        depends_on=frozenset({"a"})),
    }
    with pytest.raises(DAGValidationError, match="cycle detected"):
        SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())


def test_validation_max_concurrency_nonpositive():
    a = _make_module("a")
    workers = {"a": WorkerSpec(id="a", module=a, build_input=_build)}
    with pytest.raises(DAGValidationError, match="max_concurrency"):
        SupervisorDAG(workers, invoke_agent=InvokeRecorder().build(), max_concurrency=0)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parallel_independent_workers():
    a, b = _make_module("a"), _make_module("b")
    workers = {
        "a": WorkerSpec(id="a", module=a, build_input=_build),
        "b": WorkerSpec(id="b", module=b, build_input=_build),
    }
    rec = InvokeRecorder()
    dag = SupervisorDAG(workers, invoke_agent=rec.build(delay=0.05))
    state = WorkerState(request={"k": "v"})
    await _drain(dag, state)
    assert rec.max_concurrent == 2, (
        f"expected both workers to overlap; saw peak {rec.max_concurrent}"
    )
    assert state.status["a"] == WorkerStatus.SUCCEEDED
    assert state.status["b"] == WorkerStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_downstream_validation_receives_upstream_retrieved_uris():
    seen: list[list[str]] = []
    upstream = _make_module("a")
    downstream = _make_module("b")

    def validate_downstream(data: dict) -> tuple[bool, str]:
        seen.append(list(data.get("_retrieved_uris", [])))
        return True, ""

    downstream.validate_response = validate_downstream
    workers = {
        "a": WorkerSpec(id="a", module=upstream, build_input=_build),
        "b": WorkerSpec(
            id="b",
            module=downstream,
            build_input=_build,
            depends_on=frozenset({"a"}),
        ),
    }
    state = WorkerState(request={})
    state.retrieved_uris["a"] = ["https://source.example/document"]
    dag = SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())

    await _drain(dag, state)

    assert seen == [["https://source.example/document"]]


@pytest.mark.asyncio
async def test_fail_fast_required_cancels_peers():
    a, b = _make_module("a"), _make_module("b")
    workers = {
        "a": WorkerSpec(id="a", module=a, build_input=_build),
        "b": WorkerSpec(id="b", module=b, build_input=_build),
    }
    rec = InvokeRecorder()
    dag = SupervisorDAG(workers, invoke_agent=rec.build(delay=0.1, fail_on={"a"}))
    state = WorkerState(request={})
    with pytest.raises(RuntimeError, match="simulated failure: a"):
        await _drain(dag, state)


@pytest.mark.asyncio
async def test_optional_failure_skips_downstream():
    a, b, c = _make_module("a"), _make_module("b"), _make_module("c")
    # a(optional) -> b -> c
    workers = {
        "a": WorkerSpec(id="a", module=a, build_input=_build, required=False),
        "b": WorkerSpec(
            id="b", module=b, build_input=_build,
            depends_on=frozenset({"a"}),
        ),
        "c": WorkerSpec(
            id="c", module=c, build_input=_build,
            depends_on=frozenset({"b"}),
        ),
    }
    rec = InvokeRecorder()
    dag = SupervisorDAG(workers, invoke_agent=rec.build(fail_on={"a"}))
    state = WorkerState(request={})
    events = await _drain(dag, state)
    assert state.status["a"] == WorkerStatus.FAILED
    assert state.status["b"] == WorkerStatus.SKIPPED
    assert state.status["c"] == WorkerStatus.SKIPPED
    assert "a" not in state.outputs and "b" not in state.outputs
    assert rec.calls == ["a"], (
        f"b and c must never be invoked after optional a failed; got {rec.calls}"
    )
    skipped_events = [e for e in events if e.get("type") == "worker_skipped"]
    assert len(skipped_events) == 1 and skipped_events[0]["worker_id"] == "a"
    assert set(skipped_events[0]["downstream_skipped"]) == {"b", "c"}


@pytest.mark.asyncio
async def test_optional_failure_unrelated_downstream_still_runs():
    a, b, c = _make_module("a"), _make_module("b"), _make_module("c")
    workers = {
        "a": WorkerSpec(id="a", module=a, build_input=_build, required=False),
        "b": WorkerSpec(id="b", module=b, build_input=_build),
        "c": WorkerSpec(
            id="c", module=c, build_input=_build,
            depends_on=frozenset({"b"}),
        ),
    }
    rec = InvokeRecorder()
    dag = SupervisorDAG(workers, invoke_agent=rec.build(fail_on={"a"}))
    state = WorkerState(request={})
    await _drain(dag, state)
    assert state.status["a"] == WorkerStatus.FAILED
    assert state.status["b"] == WorkerStatus.SUCCEEDED
    assert state.status["c"] == WorkerStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_max_concurrency_serialises_workers():
    workers = {
        wid: WorkerSpec(id=wid, module=_make_module(wid), build_input=_build)
        for wid in ("a", "b", "c", "d")
    }
    rec = InvokeRecorder()
    dag = SupervisorDAG(
        workers, invoke_agent=rec.build(delay=0.02), max_concurrency=1
    )
    state = WorkerState(request={})
    await _drain(dag, state)
    assert rec.max_concurrent == 1, (
        f"max_concurrency=1 must serialise workers; saw peak {rec.max_concurrent}"
    )


@pytest.mark.asyncio
async def test_sse_event_shape():
    a = _make_module("a")
    b = _make_module("b")
    workers = {
        "a": WorkerSpec(id="a", module=a, build_input=_build),
        "b": WorkerSpec(
            id="b", module=b, build_input=_build,
            depends_on=frozenset({"a"}),
        ),
    }
    dag = SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())
    state = WorkerState(request={})
    events = await _drain(dag, state)

    routed = [e for e in events if e.get("stage") == "supervisor.routed"]
    assert len(routed) == 1
    assert routed[0]["stages"] == [["a"], ["b"]]

    partials = [e for e in events if e.get("type") == "partial"]
    assert [p["worker_id"] for p in partials] == ["a", "b"]
    for p in partials:
        assert "output" in p
        assert p["output"]["agent"] in {"a", "b"}


@pytest.mark.asyncio
async def test_retrieval_memoised_across_workers():
    calls: list[str] = []

    async def retrieve(query: str) -> list[dict]:
        calls.append(query)
        await asyncio.sleep(0.01)
        return [{"content": f"chunk-for-{query}"}]

    a = _make_module("a")
    b = _make_module("b")

    def q_a(state: WorkerState) -> str:
        return "shared"

    def q_b(state: WorkerState) -> str:
        return "shared"

    workers = {
        "a": WorkerSpec(
            id="a", module=a, build_input=_build, grounding_query=q_a
        ),
        "b": WorkerSpec(
            id="b", module=b, build_input=_build, grounding_query=q_b
        ),
    }
    dag = SupervisorDAG(
        workers, invoke_agent=InvokeRecorder().build(), retrieve=retrieve
    )
    state = WorkerState(request={})
    await _drain(dag, state)
    assert calls == ["shared"], (
        f"retrieval must be memoised once across racing workers; got {calls}"
    )
    # Copy-on-assign: each worker's grounding_chunks must be a distinct list
    assert state.grounding_chunks["a"] is not state.grounding_chunks["b"]


@pytest.mark.asyncio
async def test_validation_failure_raises_as_required_exception():
    bad = _make_module("bad", validates=False)
    workers = {"bad": WorkerSpec(id="bad", module=bad, build_input=_build)}
    dag = SupervisorDAG(workers, invoke_agent=InvokeRecorder().build())
    state = WorkerState(request={})
    with pytest.raises(ValueError, match="failed validation"):
        await _drain(dag, state)
