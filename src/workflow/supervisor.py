"""Declarative DAG scheduler for supervisor-pattern scenarios.

This is the single attachment point a scenario exposes for its worker graph:
a ``dict[str, WorkerSpec]``. The scenario's workflow facade hands that dict
to :class:`SupervisorDAG` and yields its events. Everything a partner needs
to add, remove, reorder, or parallelise workers lives in the dict — there is
no hand-wired ``asyncio.gather`` block or stage counter in scenario code, so
``scripts/scaffold-agent.py`` (G5) can append an entry and the graph is done.

Design notes
============

* **Dynamic scheduler.** Workers become tasks as soon as their declared
  ``depends_on`` set is satisfied — no stage barriers. A fast worker's
  dependents launch immediately even if an unrelated peer is still running.

* **Per-run state.** All mutable state lives in :class:`WorkerState`, which
  is constructed fresh for every ``stream()``. The DAG and workflow
  instances are stateless across requests, so concurrent callers never race.

* **Failure telemetry is exactly-once.** ``worker.completed`` events (both
  ``ok=True`` and ``ok=False``) are emitted centrally by the scheduler so
  dashboards and replay tooling see every terminal transition. Skipped
  workers get their own ``worker.skipped`` event so DAG-terminal counts
  match worker count.

* **Transitive skip propagation.** When an optional (``required=False``)
  worker fails, every downstream dependent is marked skipped immediately via
  reverse-edge BFS. Without this, dependents would sit with a non-zero
  indegree forever and hang the scheduler.

* **Fail-fast for required workers.** A required-worker exception cancels
  peers, drains them with ``gather(return_exceptions=True)`` to avoid
  orphaned tasks (and lingering token spend), then re-raises to the caller.

* **Retrieval memoised per query** via a cached ``asyncio.Task`` rather than
  the resolved list, so two workers with the same ``grounding_query`` share
  exactly one retrieve call even under racing launches.
"""
from __future__ import annotations

import asyncio
import enum
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from src.accelerator_baseline.telemetry import Event, emit_event

logger = logging.getLogger("accelerator.supervisor")
_DEBUG_RAW = os.environ.get("SUPERVISOR_DEBUG_RAW") == "1"

_REQUIRED_MODULE_ATTRS: tuple[str, ...] = (
    "AGENT_NAME",
    "build_prompt",
    "transform_response",
    "validate_response",
)


class WorkerStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkerState:
    """Per-invocation state. Constructed fresh for every ``stream()``.

    Never reuse a ``WorkerState`` across requests — that would reintroduce the
    cross-request race the G6 rewrite fixes.
    """

    request: Mapping[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)
    grounding_chunks: dict[str, list[Mapping[str, Any]]] = field(default_factory=dict)
    usage_totals: dict[str, int] = field(default_factory=dict)
    status: dict[str, WorkerStatus] = field(default_factory=dict)
    # URIs the Foundry tool trace surfaced for each agent's most recent
    # turn, keyed by ``foundry_name`` (== ``spec.module.AGENT_NAME``).
    # Populated by the workflow's ``_invoke_agent`` via
    # :func:`src.accelerator_baseline.citations.extract_tool_trace_uris`
    # so per-agent validators can reject hallucinated URLs in
    # ``foundry_tool`` retrieval mode (where Python never sees the
    # search call directly). Empty list when no annotations were
    # surfaced — validators receive ``[]`` and fail open per the
    # ``assert_no_hallucinated_urls`` contract.
    retrieved_uris: dict[str, list[str]] = field(default_factory=dict)
    # Optional sink for streaming chunk events. Scenarios that want
    # token-level streaming during ``_invoke_agent`` create a queue per
    # request and the workflow merges it into the SSE event stream. Left
    # ``None`` for non-streaming callers (unit tests, batch invocations)
    # so the agent_framework streaming path is bypassed and behaviour is
    # identical to pre-streaming code.
    chunks: "asyncio.Queue[Any] | None" = None


BuildInput = Callable[[WorkerState], Mapping[str, Any]]
GroundingQuery = Callable[[WorkerState], "str | None"]
InvokeAgent = Callable[[str, str, WorkerState], Awaitable[str]]
Retrieve = Callable[[str], Awaitable[list[Mapping[str, Any]]]]


@dataclass(frozen=True)
class WorkerSpec:
    """Declarative record describing how to run one worker inside a DAG.

    ``build_input`` must be a **module-level function** (not a lambda) so the
    G5 scaffolder can append new entries via AST rewrite without generating
    anonymous code. Lambdas will still work at runtime, but the scaffolder
    contract assumes named callables.
    """

    id: str
    module: Any
    build_input: BuildInput
    depends_on: frozenset[str] = frozenset()
    grounding_query: GroundingQuery | None = None
    timeout_s: float | None = None
    required: bool = True
    validation_max_attempts: int = 2
    """How many times to invoke the agent if ``validate_response`` fails.

    Defaults to 2 (one transparent retry). LLMs occasionally drop a required
    field or violate a length constraint on a single sample even with stable
    instructions; re-sampling once with no prompt change is enough to recover
    in the vast majority of cases without masking genuine agent regressions.
    Set to 1 to disable retry, or higher for flaky models. The same retrieval
    and built input are reused across attempts — only the model sample is
    redrawn — so retries do not multiply token spend on grounding."""


class DAGValidationError(Exception):
    """Raised at DAG construction when the worker graph is malformed."""


class SupervisorDAG:
    def __init__(
        self,
        workers: dict[str, WorkerSpec],
        *,
        invoke_agent: InvokeAgent,
        retrieve: Retrieve | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        if max_concurrency is not None and max_concurrency <= 0:
            raise DAGValidationError(
                f"max_concurrency must be positive or None, got {max_concurrency!r}"
            )
        self._workers = dict(workers)
        self._invoke = invoke_agent
        self._retrieve = retrieve
        self._sem: asyncio.Semaphore | None = (
            asyncio.Semaphore(max_concurrency) if max_concurrency else None
        )
        self._validate_graph()
        self._stages_cache = self._compute_stages()

    # ------------------------------------------------------------------ validation
    def _validate_graph(self) -> None:
        errs: list[str] = []
        for wid, spec in self._workers.items():
            if wid != spec.id:
                errs.append(f"dict key {wid!r} != spec.id {spec.id!r}")
            for attr in _REQUIRED_MODULE_ATTRS:
                value = getattr(spec.module, attr, None)
                if value is None:
                    errs.append(f"{wid}: module missing attribute {attr!r}")
                elif attr == "AGENT_NAME":
                    if not isinstance(value, str) or not value.strip():
                        errs.append(f"{wid}: AGENT_NAME must be a non-empty string")
                elif not callable(value):
                    errs.append(f"{wid}: module attribute {attr!r} is not callable")
            if wid in spec.depends_on:
                errs.append(f"{wid}: self-dependency")
            for dep in spec.depends_on:
                if dep not in self._workers:
                    errs.append(f"{wid}: unknown dependency {dep!r}")
            if not callable(spec.build_input):
                errs.append(f"{wid}: build_input is not callable")
            if spec.grounding_query is not None and not callable(spec.grounding_query):
                errs.append(f"{wid}: grounding_query is not callable")

        indeg: dict[str, int] = {wid: 0 for wid in self._workers}
        for wid, spec in self._workers.items():
            for dep in spec.depends_on:
                if dep in indeg:
                    indeg[wid] += 1
        ready = [w for w, d in indeg.items() if d == 0]
        visited = 0
        while ready:
            w = ready.pop()
            visited += 1
            for wid, spec in self._workers.items():
                if w in spec.depends_on:
                    indeg[wid] -= 1
                    if indeg[wid] == 0:
                        ready.append(wid)
        if visited != len(self._workers):
            errs.append(f"cycle detected in DAG; visited {visited}/{len(self._workers)}")

        if errs:
            raise DAGValidationError(
                "\n  - ".join(["SupervisorDAG validation failed:"] + errs)
            )

    def _compute_stages(self) -> list[list[str]]:
        """Purely informational stage decomposition for telemetry.

        Execution uses dynamic scheduling; this is just the partition App
        Insights dashboards use to render the DAG shape. Built once at
        construction.
        """
        remaining = dict(self._workers)
        done: set[str] = set()
        stages: list[list[str]] = []
        while remaining:
            ready = sorted(
                w for w, s in remaining.items() if s.depends_on <= done
            )
            stages.append(ready)
            done.update(ready)
            for w in ready:
                remaining.pop(w)
        return stages

    # ------------------------------------------------------------------ execution
    async def run(
        self, state: WorkerState
    ) -> AsyncIterator[Mapping[str, Any]]:
        stages = self._stages_cache
        emit_event(
            Event(
                name="supervisor.routed",
                args_redacted={
                    "route_json": json.dumps(stages),
                    "worker_count": len(self._workers),
                    "stage_count": len(stages),
                },
            )
        )
        yield {"type": "status", "stage": "supervisor.routed", "stages": stages}

        # indegree and reverse edges
        indeg: dict[str, int] = {
            wid: sum(1 for d in s.depends_on if d in self._workers)
            for wid, s in self._workers.items()
        }
        reverse: dict[str, list[str]] = {wid: [] for wid in self._workers}
        for wid, s in self._workers.items():
            for d in s.depends_on:
                reverse[d].append(wid)

        for wid in self._workers:
            state.status[wid] = WorkerStatus.PENDING

        retrieval_tasks: dict[str, asyncio.Task] = {}
        pending: set[asyncio.Task] = set()
        task_to_wid: dict[asyncio.Task, str] = {}
        worker_start_times: dict[str, float] = {}

        def _launch(wid: str) -> None:
            spec = self._workers[wid]
            state.status[wid] = WorkerStatus.RUNNING
            worker_start_times[wid] = time.monotonic()
            task = asyncio.create_task(
                self._run_one(state, spec, retrieval_tasks),
                name=f"worker:{wid}",
            )
            pending.add(task)
            task_to_wid[task] = wid

        async def _drain_and_raise(exc: BaseException) -> None:
            for p in pending:
                p.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for t in retrieval_tasks.values():
                if not t.done():
                    t.cancel()
            if retrieval_tasks:
                await asyncio.gather(
                    *retrieval_tasks.values(), return_exceptions=True
                )
            raise exc

        def _propagate_skip(failed_wid: str, reason: str) -> list[str]:
            """Mark failed_wid's transitive dependents as SKIPPED.

            Returns the ordered list of workers newly marked skipped so the
            caller can emit a ``worker.skipped`` event for each. Uses BFS
            over the reverse-edge graph.
            """
            skipped_order: list[str] = []
            queue = list(reverse.get(failed_wid, ()))
            while queue:
                nxt = queue.pop(0)
                if state.status.get(nxt) in {
                    WorkerStatus.SKIPPED,
                    WorkerStatus.FAILED,
                    WorkerStatus.SUCCEEDED,
                    WorkerStatus.RUNNING,
                }:
                    continue
                state.status[nxt] = WorkerStatus.SKIPPED
                skipped_order.append(nxt)
                queue.extend(reverse.get(nxt, ()))
            for wid in skipped_order:
                emit_event(
                    Event(
                        name="worker.skipped",
                        external_system=self._workers[wid].module.AGENT_NAME,
                        args_redacted={"reason": reason, "triggered_by": failed_wid},
                    )
                )
            return skipped_order

        for wid, d in list(indeg.items()):
            if d == 0:
                _launch(wid)
                spec = self._workers[wid]
                yield {
                    "type": "worker_started",
                    "worker_id": wid,
                    "agent": spec.module.AGENT_NAME,
                }

        while pending:
            done_tasks, _ = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for t in done_tasks:
                pending.discard(t)
                wid = task_to_wid.pop(t)
                spec = self._workers[wid]
                try:
                    out = t.result()
                except asyncio.CancelledError:
                    # Propagate cancellation to the caller, preserving asyncio semantics.
                    raise
                except Exception as exc:
                    logger.exception("Worker %s failed", wid)
                    emit_event(
                        Event(
                            name="worker.completed",
                            ok=False,
                            error=type(exc).__name__,
                            external_system=spec.module.AGENT_NAME,
                        )
                    )
                    if spec.required:
                        state.status[wid] = WorkerStatus.FAILED
                        await _drain_and_raise(exc)
                    state.status[wid] = WorkerStatus.FAILED
                    skipped = _propagate_skip(wid, reason=f"optional upstream {wid} failed")
                    yield {
                        "type": "worker_skipped",
                        "worker_id": wid,
                        "error": "Optional worker failed.",
                        "downstream_skipped": skipped,
                    }
                    continue

                emit_event(
                    Event(
                        name="worker.completed",
                        ok=True,
                        external_system=spec.module.AGENT_NAME,
                    )
                )
                state.outputs[wid] = out
                state.status[wid] = WorkerStatus.SUCCEEDED
                elapsed = round(time.monotonic() - worker_start_times.get(wid, 0), 1)
                yield {"type": "partial", "worker_id": wid, "output": out, "elapsed_s": elapsed}

                for dep_wid in reverse[wid]:
                    if state.status.get(dep_wid) != WorkerStatus.PENDING:
                        continue
                    indeg[dep_wid] -= 1
                    if indeg[dep_wid] > 0:
                        continue
                    ready_spec = self._workers[dep_wid]
                    if all(
                        state.status.get(d) == WorkerStatus.SUCCEEDED
                        for d in ready_spec.depends_on
                    ):
                        _launch(dep_wid)
                        yield {
                            "type": "worker_started",
                            "worker_id": dep_wid,
                            "agent": ready_spec.module.AGENT_NAME,
                        }

        # Drain any in-flight retrieval tasks that outlived their workers
        # (e.g. a retrieval completed after its worker was skipped).
        for t in retrieval_tasks.values():
            if not t.done():
                t.cancel()
        if retrieval_tasks:
            await asyncio.gather(
                *retrieval_tasks.values(), return_exceptions=True
            )

    async def _run_one(
        self,
        state: WorkerState,
        spec: WorkerSpec,
        retrieval_tasks: dict[str, asyncio.Task],
    ) -> Any:
        async def _body() -> Any:
            if spec.grounding_query is not None and self._retrieve is not None:
                query = spec.grounding_query(state)
                if query:
                    if query not in retrieval_tasks:
                        retrieval_tasks[query] = asyncio.create_task(
                            self._retrieve(query),  # pyright: ignore[reportArgumentType]  # Retrieve protocol is awaitable-returning at runtime
                            name=f"retrieve:{query[:32]}",
                        )
                    chunks = await retrieval_tasks[query]
                    # Copy so that downstream mutation by one worker does not
                    # alias another worker's cached chunks.
                    state.grounding_chunks[spec.id] = list(chunks)
            inp = spec.build_input(state)
            prompt = spec.module.build_prompt(inp)
            attempts = max(1, spec.validation_max_attempts)
            last_err = ""
            last_raw = ""
            for attempt_idx in range(attempts):
                raw = await self._invoke(spec.module.AGENT_NAME, prompt, state)
                last_raw = raw or ""
                data = spec.module.transform_response(raw or "{}")
                # Stamp the per-call retrieved-URI set onto the parsed
                # dict so validators can call
                # ``assert_no_hallucinated_urls`` without a signature
                # change. Popped after validation so downstream
                # consumers (other workers, the SSE wire format) never
                # see the private key.
                allowed_sources = set(
                    state.retrieved_uris.get(spec.module.AGENT_NAME, [])
                )
                dependency_queue = list(spec.depends_on)
                visited_dependencies: set[str] = set()
                while dependency_queue:
                    dependency_id = dependency_queue.pop()
                    if dependency_id in visited_dependencies:
                        continue
                    visited_dependencies.add(dependency_id)
                    dependency = self._workers[dependency_id]
                    allowed_sources.update(
                        state.retrieved_uris.get(
                            dependency.module.AGENT_NAME,
                            [],
                        )
                    )
                    dependency_queue.extend(dependency.depends_on)
                data["_retrieved_uris"] = sorted(allowed_sources)
                try:
                    ok, err = spec.module.validate_response(data)
                finally:
                    data.pop("_retrieved_uris", None)
                if ok:
                    return data
                last_err = err
                if _DEBUG_RAW:
                    snippet = last_raw[:300].replace("\n", " ")
                    logger.warning(
                        "validation_failed agent=%s attempt=%d/%d err=%s raw=%r",
                        spec.module.AGENT_NAME, attempt_idx + 1, attempts,
                        err, snippet,
                    )
            raise ValueError(f"{spec.module.AGENT_NAME}: {last_err}")

        async def _with_sem() -> Any:
            if self._sem is None:
                return await _body()
            async with self._sem:
                return await _body()

        if spec.timeout_s is not None:
            return await asyncio.wait_for(_with_sem(), timeout=spec.timeout_s)
        return await _with_sem()
