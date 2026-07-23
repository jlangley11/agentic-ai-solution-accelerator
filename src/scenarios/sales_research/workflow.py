"""Sales Research & Outreach workflow — Supervisor DAG over four workers.

Graph (declared once as ``WORKERS`` below; the DAG scheduler infers stages
from ``depends_on`` and streams partials as each worker completes)::

    [request]
        v
    account_planner (grounded)
        v
    +-----+------+
    v            v
    icp_fit   competitive
    analyst   context
    +-----+------+
        v
    outreach_personalizer
        v
    supervisor aggregator  ->  HITL gate  ->  side-effect tools

The scenario facade is intentionally thin: a fresh ``WorkerState`` per
request (so concurrent callers never share mutable state), plus an
aggregator + side-effect driver around the DAG. Adding, swapping, or
parallelising a worker is a data change to ``WORKERS``; the scaffolder in
``scripts/scaffold-agent.py`` rewrites this dict directly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from time import monotonic
from typing import Any, AsyncIterator

from azure.identity.aio import DefaultAzureCredential

try:
    # GA SDK rename: agent-framework-azure-ai → agent-framework-foundry,
    # agent_framework.azure → agent_framework.foundry, AzureAIClient → FoundryAgent.
    from agent_framework.foundry import FoundryAgent  # type: ignore
except Exception:  # pragma: no cover - SDK may not be installed in lint envs
    FoundryAgent = None  # type: ignore

from src.accelerator_baseline.killswitch import assert_enabled
from src.accelerator_baseline.telemetry import Event, emit_event
from src.config.settings import foundry_project_endpoint
from src.tools import SIDE_EFFECT_TOOLS
from src.workflow.base import BaseWorkflow
from src.workflow.supervisor import SupervisorDAG, WorkerSpec, WorkerState

from .agents import (
    account_planner,
    competitive_context,
    icp_fit_analyst,
    outreach_personalizer,
)
from .schema import ResearchBriefing

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input compaction — reduces prompt tokens for downstream workers so they
# respond faster.  The raw account_planner output can be 2-4K tokens; this
# keeps the key structure but trims arrays and strings.
# ---------------------------------------------------------------------------
def _compact(raw: Any, max_items: int = 3, max_str: int = 200) -> str:
    """Compress a worker output to reduce downstream input tokens."""
    if raw is None:
        return "{}"
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError, ValueError):
        return str(raw)[:500]
    if not isinstance(data, dict):
        return str(data)[:500]

    def _cv(v: Any) -> Any:
        if isinstance(v, str) and len(v) > max_str:
            return v[:max_str] + "..."
        if isinstance(v, list):
            trunc = v[:max_items]
            if all(isinstance(x, dict) for x in trunc):
                return [{kk: _cv(vv) for kk, vv in x.items()} for x in trunc]
            return trunc
        if isinstance(v, dict):
            return {kk: _cv(vv) for kk, vv in v.items()}
        return v

    return json.dumps({k: _cv(v) for k, v in data.items()}, default=str)


# ---------------------------------------------------------------------------
# Worker input builders — module-level ``def`` so ``scripts/scaffold-agent.py``
# can append new named functions and register them in ``WORKERS`` via a single
# AST rewrite. Do NOT inline as lambdas.
# ---------------------------------------------------------------------------
def _build_input_account_planner(state: WorkerState) -> dict[str, Any]:
    return {
        "company_name": state.request["company_name"],
        "domain": state.request.get("domain", ""),
        "context_hints": state.request.get("context_hints", []),
    }


def _build_input_icp_fit_analyst(state: WorkerState) -> dict[str, Any]:
    return {
        "account_profile": _compact(state.outputs["account_planner"]),
        "icp_definition": state.request["icp_definition"],
    }


def _build_input_competitive_context(state: WorkerState) -> dict[str, Any]:
    return {
        "account_profile": _compact(state.outputs["account_planner"]),
        "our_solution": state.request["our_solution"],
    }


def _build_input_outreach_personalizer(state: WorkerState) -> dict[str, Any]:
    fit = state.outputs.get("icp_fit_analyst", "(not yet available)")
    comp_ctx = state.outputs.get("competitive_context", "(not yet available)")
    return {
        "account_profile": _compact(state.outputs["account_planner"]),
        "fit_summary": _compact(fit),
        "competitive_context": _compact(comp_ctx),
        "persona": state.request.get("persona", "Decision maker"),
    }


WORKERS: dict[str, WorkerSpec] = {
    "account_planner": WorkerSpec(
        id="account_planner",
        module=account_planner,
        build_input=_build_input_account_planner,
        # No grounding_query — retrieval runs as a Foundry tool inside the
        # agent (see accelerator.yaml scenario.agents[].retrieval). The
        # Python supervisor's _retrieve path is bypassed for this worker.
    ),
    "icp_fit_analyst": WorkerSpec(
        id="icp_fit_analyst",
        module=icp_fit_analyst,
        build_input=_build_input_icp_fit_analyst,
        depends_on=frozenset({"account_planner"}),
    ),
    "competitive_context": WorkerSpec(
        id="competitive_context",
        module=competitive_context,
        build_input=_build_input_competitive_context,
        depends_on=frozenset({"account_planner"}),
    ),
    # Parallelized: outreach now runs alongside icp+competitive (only needs
    # account_planner). This cuts ~30-50s off wall-clock by removing the
    # serial wait for icp+competitive to finish before outreach starts.
    "outreach_personalizer": WorkerSpec(
        id="outreach_personalizer",
        module=outreach_personalizer,
        build_input=_build_input_outreach_personalizer,
        depends_on=frozenset({"account_planner"}),
    ),
}


class SalesResearchWorkflow:
    """Thin scenario facade over :class:`SupervisorDAG`.

    The DAG is constructed (and validated) once at workflow build time so
    a malformed ``WORKERS`` dict fails at FastAPI startup rather than on
    first request.
    """

    validated_partials = True

    def __init__(self, *, primary_index_name: str = "accounts") -> None:
        self._credential = DefaultAzureCredential()
        self._primary_index_name = primary_index_name
        self._agent_versions: dict[str, str] = {}
        self._version_lock: Any = None  # lazily created asyncio.Lock
        self._agent_to_wid: dict[str, str] = {
            spec.module.AGENT_NAME: wid for wid, spec in WORKERS.items()
        }
        self._dag = SupervisorDAG(
            WORKERS,
            invoke_agent=self._invoke_agent,
            retrieve=self._retrieve_grounding,  # pyright: ignore[reportArgumentType]  # bound method matches Retrieve protocol at runtime
        )

    async def warmup(self) -> None:
        """Pre-resolve agent versions and warm the credential token.

        Called from the FastAPI lifespan so the first user request does
        not pay the cold-start penalty (~3-8s) of credential acquisition
        and version API lookups.
        """
        agent_names = {spec.module.AGENT_NAME for spec in WORKERS.values()}
        results = await asyncio.gather(
            *(self._resolve_agent_version(name) for name in agent_names),
            return_exceptions=True,
        )
        resolved = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        logger.info("warmup: resolved %d/%d agent versions", resolved, len(agent_names))

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Yield SSE events for one research request.

        Architecture: a single background ``orchestrate`` task drives the
        DAG, the aggregator, and side-effect tools, pushing every event
        into a merged queue. ``_invoke_agent`` runs the Foundry agent in
        streaming mode and pushes per-token ``chunk`` events into the
        SAME queue, so worker thoughts interleave naturally with DAG
        ``partial`` events. The consumer loop emits a ``heartbeat`` every
        15 s of silence so dev proxies / Container Apps ingress / browser
        intermediaries do not close the connection during long worker
        runs (root cause of the "1 partial then dead stream" UX bug).

        We deliberately use ``asyncio.wait`` on a *persistent* get task
        rather than ``asyncio.wait_for`` to avoid the well-known queue
        item-loss race where a timeout cancels ``Queue.get`` after it has
        already taken an item but before it has returned it to the
        caller. With the persistent-task pattern the get is never
        cancelled by the heartbeat path; we just check ``done`` next
        iteration.
        """
        assert_enabled("workflow")
        # Capture the orchestration start time so ``response.returned`` can
        # carry an authoritative ``elapsed_ms``. The FastAPI ``requests``
        # table only sees the SSE handler latency (which returns near-zero
        # because the body streams) — partners who want real end-to-end
        # latency need this value, not the stream-handler duration.
        request_start = monotonic()
        emit_event(
            Event(
                name="request.received",
                args_redacted={"company": request["company_name"]},
            )
        )

        state = WorkerState(request=request)
        # Single merged queue: orchestrator events AND streaming chunks
        # both flow through here. ``None`` is the end-of-stream sentinel
        # and a dict containing key ``_error`` is the in-band exception
        # marker (we cannot raise across a task boundary cleanly).
        out_q: asyncio.Queue[Any] = asyncio.Queue()
        state.chunks = out_q

        async def orchestrate() -> None:
            try:
                async for evt in self._dag.run(state):
                    await out_q.put(evt)

                agg_start = __import__("time").monotonic()
                await out_q.put({"type": "status", "stage": "aggregating"})
                final = await self._aggregate(state)
                agg_elapsed = round(__import__("time").monotonic() - agg_start, 1)
                await out_q.put({"type": "status", "stage": "aggregated", "elapsed_s": agg_elapsed})

                if state.usage_totals:
                    final.setdefault("usage", dict(state.usage_totals))

                # Briefing renderable BEFORE side-effect tools — a HITL
                # or permission failure later cannot wipe it from the UI.
                await out_q.put({"type": "briefing_ready", "briefing": final})

                approvals_needed = final.get("requires_approval", []) or []
                tool_args_map = final.get("tool_args", {}) or {}
                # Lab / partner-starter mode: when no approver is wired up
                # AND HITL_DEV_MODE is off, we deliberately do NOT execute
                # side-effect tools. Surfacing the proposed action as
                # ``tool_pending_approval`` keeps the UX honest (no green
                # "approved" lie, no red "error") and is the safe default
                # for partner forks until they integrate their own
                # approver (Teams bot, ITSM queue, etc.).
                approver = os.getenv("HITL_APPROVER_ENDPOINT")
                dev_mode = os.getenv("HITL_DEV_MODE", "").lower() in (
                    "1", "true", "on",
                )
                hitl_configured = bool(approver) or dev_mode
                for tool_name in approvals_needed:
                    if tool_name not in SIDE_EFFECT_TOOLS:
                        continue
                    fn, _schema = SIDE_EFFECT_TOOLS[tool_name]
                    args = tool_args_map.get(tool_name, {})
                    if not args:
                        await out_q.put({
                            "type": "tool_skipped",
                            "tool": tool_name,
                            "reason": "no tool_args produced by supervisor",
                        })
                        continue
                    if not hitl_configured:
                        await out_q.put({
                            "type": "tool_pending_approval",
                            "tool": tool_name,
                            "args": dict(args),
                        })
                        continue
                    try:
                        result = await fn(**args)
                    except Exception as exc:
                        logger.exception("Side-effect tool %s failed", tool_name)
                        emit_event(Event(
                            name="tool.failed",
                            ok=False,
                            error=type(exc).__name__,
                            args_redacted={"tool": tool_name},
                        ))
                        await out_q.put({
                            "type": "tool_error",
                            "tool": tool_name,
                            "error": "Tool execution failed.",
                        })
                        continue
                    await out_q.put({
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result,
                    })

                emit_event(Event(
                    name="response.returned",
                    ok=True,
                    value=round((monotonic() - request_start) * 1000.0, 1),
                    unit="ms",
                ))
                await out_q.put({"type": "final", "briefing": final})
            except Exception as exc:
                # Surface the exception as an in-band marker so the
                # consumer loop can re-raise it on the same task that
                # owns the generator — keeps stack traces meaningful and
                # lets FastAPI's outer ``gen()`` emit a typed ``error``
                # event.
                await out_q.put({"_error": exc})
            finally:
                await out_q.put(None)

        orch_task = asyncio.create_task(orchestrate(), name="sales-research-orchestrate")
        get_task: asyncio.Task[Any] | None = None
        try:
            while True:
                if get_task is None:
                    get_task = asyncio.ensure_future(out_q.get())
                done, _pending = await asyncio.wait({get_task}, timeout=15.0)
                if get_task not in done:
                    # Idle period — emit a non-data heartbeat so the
                    # connection stays warm. Loop again WITHOUT cancelling
                    # ``get_task``; on the next pass it will already be
                    # in ``done`` if a real event landed meanwhile.
                    yield {"type": "heartbeat"}
                    continue
                evt = get_task.result()
                get_task = None
                if evt is None:
                    break
                if isinstance(evt, dict) and "_error" in evt:
                    raise evt["_error"]
                yield evt
        finally:
            # Make sure the orchestrator + any pending get future are
            # not leaked when the consumer (e.g. FastAPI client
            # disconnect) bails out early.
            if get_task is not None and not get_task.done():
                get_task.cancel()
            if not orch_task.done():
                orch_task.cancel()
                try:
                    await orch_task
                except (asyncio.CancelledError, Exception):  # noqa: S110  # task already failed/cancelled
                    pass

    # ---- internals --------------------------------------------------------
    async def _resolve_agent_version(self, agent_name: str) -> str | None:
        """Return the latest version id for a Foundry PromptAgent.

        ``FoundryAgent`` requires an explicit ``agent_version`` for PromptAgents
        (the kind bootstrap creates). When omitted, the SDK silently falls
        back to inline chat mode and the model service rejects the request
        with ``Missing required parameter: 'model'``. The Indexes/Agents
        preview API also rejects ``"latest"`` (returns 400) so we list
        versions and pick the highest numeric one. Cached per workflow.
        """
        if agent_name in self._agent_versions:
            return self._agent_versions[agent_name]
        import asyncio
        if self._version_lock is None:
            self._version_lock = asyncio.Lock()
        async with self._version_lock:
            if agent_name in self._agent_versions:
                return self._agent_versions[agent_name]
            try:
                endpoint = foundry_project_endpoint()
            except RuntimeError:
                return None
            try:
                from azure.ai.projects.aio import AIProjectClient
            except Exception:
                return None
            try:
                proj = AIProjectClient(endpoint=endpoint, credential=self._credential)
                try:
                    versions: list[str] = []
                    async for v in proj.agents.list_versions(agent_name):
                        vid = getattr(v, "version", None)
                        if isinstance(vid, str) and vid:
                            versions.append(vid)
                finally:
                    await proj.close()
            except Exception as exc:
                logger.exception(
                    "Foundry agent version lookup failed for %s",
                    agent_name,
                )
                emit_event(Event(
                    name="agent.version_lookup_failed",
                    ok=False, error=f"{agent_name}: {type(exc).__name__}",
                ))
                return None
            if not versions:
                return None
            # Pick highest numeric version, fallback to lexicographic max.
            try:
                latest = max(versions, key=lambda x: int(x))
            except ValueError:
                latest = max(versions)
            self._agent_versions[agent_name] = latest
            return latest

    async def _invoke_agent(
        self, agent_name: str, prompt: str, state: WorkerState
    ) -> str:
        """Retrieve a Foundry agent and run one turn.

        When ``state.chunks`` is set (the streaming SSE path), the agent
        is invoked with ``stream=True`` and each ``AgentResponseUpdate``
        is forwarded as a ``chunk`` event into the merged event queue
        for live UI feedback. The full text is reassembled from the
        final ``AgentResponse`` (``ResponseStream.get_final_response``)
        so downstream parsing/validation operates on the complete
        payload and not a partial.

        Without ``state.chunks`` (unit tests, batch invocations) the
        non-streaming code path is used unchanged — required for the
        existing test stubs that monkey-patch ``agent.run``.

        Token usage from either path accumulates into
        ``state.usage_totals`` so concurrent requests do not corrupt
        each other's cost totals.
        """
        if FoundryAgent is None:
            emit_event(
                Event(
                    name="worker.completed",
                    args_redacted={"agent": agent_name, "stub": True},
                )
            )
            return "{}"
        project_endpoint = foundry_project_endpoint()
        agent_version = await self._resolve_agent_version(agent_name)
        agent = FoundryAgent(
            project_endpoint=project_endpoint,
            credential=self._credential,
            agent_name=agent_name,
            agent_version=agent_version,
            allow_preview=True,
        )

        if state.chunks is None:
            # Non-streaming path (unit tests / batch). Behaviour identical
            # to pre-streaming workflow.
            result = await agent.run(prompt)
            self._merge_usage(state, getattr(result, "usage", None))
            self._capture_retrieved_uris(state, agent_name, result)
            return result.text

        # Streaming path: iterate updates, push chunk events, reassemble.
        # ``agent.run(stream=True)`` returns a ``ResponseStream`` that is
        # async-iterable (yields ``AgentResponseUpdate``) and exposes
        # ``get_final_response()`` for the consolidated response with
        # accurate usage. We rely on the SDK's batching of updates rather
        # than per-token chunks so we don't drown the UI; if a future SDK
        # rev emits very granular tokens we may add coalescing here.
        response_stream = agent.run(prompt, stream=True)
        chunks_buf: list[str] = []
        try:
            async for update in response_stream:
                delta = getattr(update, "text", None) or ""
                if not delta:
                    continue
                chunks_buf.append(delta)
                # Best-effort: never let a slow consumer (browser, proxy)
                # back-pressure the agent SDK. Drop the chunk silently
                # if the queue is bounded and full — the final text is
                # still preserved in ``chunks_buf``.
                try:
                    state.chunks.put_nowait({
                        "type": "chunk",
                        "agent": agent_name,
                        # Canonical UI key — matches partial.worker_id and
                        # worker_started.worker_id. ``agent`` is retained
                        # for telemetry / debug. ``None`` for the
                        # supervisor (post-DAG aggregator) since it isn't
                        # a registered worker.
                        "worker_id": self._agent_to_wid.get(agent_name),
                        "delta": delta,
                    })
                except asyncio.QueueFull:  # pragma: no cover - defensive
                    pass
            final_response = await response_stream.get_final_response()
        except Exception:
            # Make sure the SSE stream surfaces the failure cleanly via
            # the orchestrator's ``_error`` channel rather than hanging.
            raise
        self._merge_usage(state, getattr(final_response, "usage", None))
        self._capture_retrieved_uris(state, agent_name, final_response)
        return getattr(final_response, "text", None) or "".join(chunks_buf)

    @staticmethod
    def _capture_retrieved_uris(
        state: WorkerState, agent_name: str, response: Any
    ) -> None:
        """Stash citation URIs from a Foundry tool trace onto ``state``.

        The supervisor reads this back via
        ``state.retrieved_uris[agent_name]`` and stamps it onto the
        parsed dict (as ``_retrieved_uris``) before invoking the
        worker's validator, so per-agent validators can call
        :func:`assert_no_hallucinated_urls` in ``foundry_tool``
        retrieval mode where Python never sees the search call
        directly. The capture failing gracefully (empty list) is the
        documented contract — validators fail open on empty allowed
        sets.
        """
        try:
            from src.accelerator_baseline.citations import (
                extract_tool_trace_uris,
            )
            uris = extract_tool_trace_uris(response)
            state.retrieved_uris[agent_name] = sorted(uris)
        except Exception:  # noqa: BLE001 - never fail the run on telemetry
            state.retrieved_uris.setdefault(agent_name, [])

    @staticmethod
    def _merge_usage(state: WorkerState, usage: Any) -> None:
        if usage is None:
            return
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            val = getattr(usage, key, None)
            if isinstance(val, (int, float)):
                state.usage_totals[key] = (
                    state.usage_totals.get(key, 0) + int(val)
                )
        state.usage_totals["agent_calls"] = (
            state.usage_totals.get("agent_calls", 0) + 1
        )

    async def _retrieve_grounding(self, query: str) -> list[dict[str, Any]]:
        """Pull top-K grounded chunks from the scenario's primary AI Search index.

        Fails open (empty list) when retrieval isn't configured so the unit-
        test stub path still works; agent validators enforce citations.
        """
        try:
            from src.retrieval.ai_search import SearchRetriever
        except Exception as exc:
            logger.exception("Could not initialize SearchRetriever")
            emit_event(Event(
                name="retrieval.returned",
                ok=False,
                error=type(exc).__name__,
            ))
            return []
        try:
            retriever = SearchRetriever(self._primary_index_name)
        except Exception:
            return []
        try:
            chunks = await retriever.search(query, top=5)
            return [
                {
                    "id": c.id,
                    "content": c.content,
                    "source": c.source,
                    "score": c.score,
                }
                for c in chunks
            ]
        except Exception as exc:
            logger.exception("Retrieval failed")
            emit_event(Event(
                name="retrieval.returned",
                ok=False,
                error=type(exc).__name__,
            ))
            return []
        finally:
            try:
                await retriever.close()
            except Exception:  # noqa: S110  # best-effort cleanup in finally
                pass

    @staticmethod
    def _compact_output(raw: Any, max_items: int = 3, max_str: int = 300) -> str:
        """Backward-compat wrapper — delegates to module-level ``_compact``."""
        return _compact(raw, max_items=max_items, max_str=max_str)

    async def _aggregate(self, state: WorkerState) -> dict[str, Any]:
        """Build the final ResearchBriefing deterministically — no LLM call.

        Exec summary and next steps are extracted from the already-transformed
        worker outputs.  This eliminates the ~34s supervisor LLM round-trip
        while keeping grounded, data-driven synthesis.  Pass-through fields
        are merged verbatim.
        """
        outputs = state.outputs
        acct = outputs.get("account_planner") or {}
        icp = outputs.get("icp_fit_analyst") or {}
        comp = outputs.get("competitive_context") or {}
        outreach = outputs.get("outreach_personalizer") or {}

        # ---- executive_summary (3 bullets) --------------------------------
        bullets: list[str] = []

        overview = acct.get("company_overview", "") if isinstance(acct, dict) else ""
        if overview:
            first = overview.split(". ")[0].rstrip(".") + "."
            bullets.append(first)
        else:
            bullets.append("Account profile gathered — see details below.")

        score = icp.get("fit_score", 0) if isinstance(icp, dict) else 0
        segment = icp.get("recommended_segment", "unknown") if isinstance(icp, dict) else "unknown"
        tier = icp.get("tier_recommendation", "watchlist") if isinstance(icp, dict) else "watchlist"
        reasons = icp.get("fit_reasons", []) if isinstance(icp, dict) else []
        reason_tail = f" — {reasons[0]}" if reasons else ""
        bullets.append(f"ICP fit: {score}/100 ({segment}, {tier}){reason_tail}")

        competitors = comp.get("competitors", []) if isinstance(comp, dict) else []
        diffs = comp.get("differentiators", []) if isinstance(comp, dict) else []
        if competitors:
            names = ", ".join(c.get("name", "?") for c in competitors[:2] if isinstance(c, dict))
            diff_note = f"; differentiator: {diffs[0]}" if diffs else ""
            bullets.append(f"Competitive landscape includes {names}{diff_note}.")
        elif diffs:
            bullets.append(f"Key differentiator: {diffs[0]}.")
        else:
            bullets.append("No significant competitive presence detected.")

        # ---- next_steps (3 actions) ---------------------------------------
        steps: list[str] = []
        action = icp.get("recommended_action", "nurture") if isinstance(icp, dict) else "nurture"

        if action == "pursue":
            steps.append(
                f"Pursue this {tier} account — schedule a discovery call "
                f"with the buying committee."
            )
        elif action == "disqualify":
            steps.append(
                f"Re-evaluate fit — account scored {score}/100; "
                f"consider deprioritizing."
            )
        else:
            steps.append(
                f"Nurture this {tier} account — share relevant case studies "
                f"and monitor for triggers."
            )

        tps = comp.get("talking_points", []) if isinstance(comp, dict) else []
        if tps:
            steps.append(f"Lead with: {tps[0]}")
        elif diffs:
            steps.append(f"Emphasize differentiator: {diffs[0]}")
        else:
            steps.append("Prepare competitive positioning talking points.")

        cta = outreach.get("primary_cta", "") if isinstance(outreach, dict) else ""
        if cta:
            steps.append(f"Outreach CTA: {cta}")
        else:
            steps.append("Draft personalized outreach referencing strategic initiatives.")

        briefing = {
            "executive_summary": bullets[:3],
            "next_steps": steps[:3],
            "requires_approval": [],
            "tool_args": {},
            "account_profile": acct,
            "icp_fit": icp,
            "competitive_play": comp,
            "recommended_outreach": outreach,
        }
        return ResearchBriefing.model_validate(briefing).model_dump(exclude_none=True)


def build_workflow(context: Any) -> BaseWorkflow:
    """Scenario workflow factory.

    Signature matches the contract in ``src.workflow.registry``:
    ``build_workflow(ScenarioContext) -> BaseWorkflow``. The context exposes
    ``retrieval_indexes``; we pick the first declared index as the primary
    grounding source so partners can rename without editing this file.
    """
    indexes = getattr(context, "retrieval_indexes", ()) or ()
    primary = indexes[0].name if indexes else "accounts"
    return SalesResearchWorkflow(primary_index_name=primary)
