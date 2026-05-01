"""Workflow for the contoso-supplier-risk scenario.

Skeleton supervisor + workers shape, scaffold-managed. The
``WORKERS`` dict and the ``from .agents import (...)`` block are
the canonical attachment points that ``scripts/scaffold-agent.py``
edits when partners run ``/add-worker-agent``. Keep both in the
tuple form; hand edits whose shape doesn't match flip the file
to "no longer scaffold-managed" and break future automation.

Graph::

    [analyst intake]
        v
    intake_validator
        v
    evidence_retriever  (FoundryIQ knowledge tool)
        v
    risk_scorer         (FoundryIQ knowledge tool, targeted)
        v
    case_drafter
        v
    supervisor aggregator  (deterministic Python, no LLM call)
        v
    HITL gate -> ServiceNow / D365 side-effect tools

The aggregator is deterministic Python over the worker outputs (no
supervisor LLM call). Brief Section 6 RAI guards are applied here
BEFORE any side-effect tool is queued: when ``intake_validator``
reports missing required inputs OR ``risk_scorer.policy_matrix_match``
is false, ``requires_approval`` is forced empty regardless of what
``case_drafter`` proposed -- the analyst is shown the blocker
instead, and no ServiceNow / D365 write is attempted.
"""
from __future__ import annotations

import asyncio
import logging
import os
from time import monotonic
from typing import Any, AsyncIterator

from azure.identity.aio import DefaultAzureCredential

try:
    # GA SDK rename: agent-framework-azure-ai -> agent-framework-foundry,
    # agent_framework.azure -> agent_framework.foundry,
    # AzureAIClient -> FoundryAgent.
    from agent_framework.foundry import FoundryAgent  # type: ignore
except Exception:  # pragma: no cover - SDK may not be installed in lint envs
    FoundryAgent = None  # type: ignore

from src.accelerator_baseline.killswitch import assert_enabled
from src.accelerator_baseline.telemetry import Event, emit_event
from src.tools import SIDE_EFFECT_TOOLS
from src.workflow.base import BaseWorkflow
from src.workflow.supervisor import SupervisorDAG, WorkerSpec, WorkerState

from .agents import (
    case_drafter,
    evidence_retriever,
    intake_validator,
    risk_scorer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker input builders -- module-level ``def`` so ``scripts/scaffold-agent.py``
# can append new helpers via AST rewrite. Do NOT inline as lambdas.
# ---------------------------------------------------------------------------
def _build_input_intake_validator(state: WorkerState) -> dict[str, Any]:
    # Intake validator only needs the original analyst request -- no
    # upstream outputs exist at this point in the DAG.
    return {"request": dict(state.request)}


def _build_input_evidence_retriever(state: WorkerState) -> dict[str, Any]:
    return {
        "intake_validator": state.outputs["intake_validator"],
        "request": dict(state.request),
    }


def _build_input_risk_scorer(state: WorkerState) -> dict[str, Any]:
    # Risk scorer needs intake (to know whether the request is blocked
    # by missing inputs) AND the full evidence pack to score against.
    return {
        "intake_validator": state.outputs["intake_validator"],
        "evidence_retriever": state.outputs["evidence_retriever"],
        "request": dict(state.request),
    }


def _build_input_case_drafter(state: WorkerState) -> dict[str, Any]:
    # Case drafter consumes the full upstream chain: intake (to know
    # whether tools should be queued at all), evidence (for citation
    # indices in the recommendation summary), and the risk scorecard
    # (to populate tool kwargs and the HITL decision prompt).
    return {
        "intake_validator": state.outputs["intake_validator"],
        "evidence_retriever": state.outputs["evidence_retriever"],
        "risk_scorer": state.outputs["risk_scorer"],
        "request": dict(state.request),
    }


WORKERS: dict[str, WorkerSpec] = {
    "intake_validator": WorkerSpec(
        id="intake_validator",
        module=intake_validator,
        build_input=_build_input_intake_validator,
        depends_on=frozenset(),
    ),
    "evidence_retriever": WorkerSpec(
        id="evidence_retriever",
        module=evidence_retriever,
        build_input=_build_input_evidence_retriever,
        # FoundryIQ knowledge tool attached to this agent in
        # accelerator.yaml -- no Python grounding_query.
        depends_on=frozenset({"intake_validator"}),
    ),
    "risk_scorer": WorkerSpec(
        id="risk_scorer",
        module=risk_scorer,
        build_input=_build_input_risk_scorer,
        # FoundryIQ knowledge tool attached (top_k=3, targeted).
        depends_on=frozenset({"evidence_retriever"}),
    ),
    "case_drafter": WorkerSpec(
        id="case_drafter",
        module=case_drafter,
        build_input=_build_input_case_drafter,
        depends_on=frozenset({"risk_scorer"}),
    ),
}


class ContosoSupplierRiskWorkflow:
    """Thin scenario facade over :class:`SupervisorDAG`.

    The DAG is constructed (and validated) once at workflow build time
    so a malformed ``WORKERS`` dict fails at FastAPI startup rather
    than on first request.
    """

    def __init__(self, *, primary_index_name: str = "supplier-evidence") -> None:
        self._credential = DefaultAzureCredential()
        self._primary_index_name = primary_index_name
        self._agent_versions: dict[str, str] = {}
        self._version_lock: Any = None  # lazily created asyncio.Lock
        self._agent_to_wid: dict[str, str] = {
            spec.module.AGENT_NAME: wid for wid, spec in WORKERS.items()
        }
        # No grounding_query on any worker -- evidence_retriever and
        # risk_scorer ground via the FoundryIQ MCPTool inside the
        # Foundry agent (see accelerator.yaml scenario.agents[].retrieval).
        # Therefore no ``retrieve=`` callable is wired here.
        self._dag = SupervisorDAG(
            WORKERS,
            invoke_agent=self._invoke_agent,
        )

    async def warmup(self) -> None:
        """Pre-resolve agent versions and warm the credential token.

        Called from the FastAPI lifespan so the first user request does
        not pay the cold-start penalty (~3-8 s) of credential
        acquisition and version API lookups.
        """
        agent_names = {spec.module.AGENT_NAME for spec in WORKERS.values()}
        results = await asyncio.gather(
            *(self._resolve_agent_version(name) for name in agent_names),
            return_exceptions=True,
        )
        resolved = sum(
            1 for r in results
            if r is not None and not isinstance(r, Exception)
        )
        logger.info(
            "warmup: resolved %d/%d agent versions",
            resolved, len(agent_names),
        )

    async def stream(
        self, request: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield SSE events for one supplier-review request.

        See ``src/scenarios/sales_research/workflow.py`` for the
        rationale on the merged-queue + persistent-get-task pattern
        (avoids the queue item-loss race when a heartbeat timeout
        cancels ``Queue.get`` mid-handoff).
        """
        assert_enabled("workflow")
        request_start = monotonic()
        emit_event(Event(
            name="request.received",
            args_redacted={
                "supplier_id": request.get("supplier_id"),
                "review_reason": request.get("review_reason"),
            },
        ))

        state = WorkerState(request=request)
        out_q: asyncio.Queue[Any] = asyncio.Queue()
        state.chunks = out_q

        async def orchestrate() -> None:
            try:
                async for evt in self._dag.run(state):
                    await out_q.put(evt)

                agg_start = monotonic()
                await out_q.put({"type": "status", "stage": "aggregating"})
                final = await self._aggregate(state)
                agg_elapsed = round(monotonic() - agg_start, 1)
                await out_q.put({
                    "type": "status",
                    "stage": "aggregated",
                    "elapsed_s": agg_elapsed,
                })

                if state.usage_totals:
                    final.setdefault("usage", dict(state.usage_totals))

                # Final report is renderable BEFORE side-effect tools so
                # a HITL rejection / approver outage cannot wipe it from
                # the analyst UI. Wire-format key is ``briefing`` to match
                # the scenario-agnostic ``evals/quality/run.py`` runner
                # contract -- the runner reads ``event['briefing']`` on
                # both ``briefing_ready`` and ``final``. Internally the
                # supplier-risk report has its own structure (5 §5d
                # sections plus an audit trail); the wire field name is
                # only the envelope.
                await out_q.put({"type": "briefing_ready", "briefing": final})

                approvals_needed = list(final.get("requires_approval", []) or [])
                tool_args_map = final.get("tool_args", {}) or {}
                approver = os.getenv("HITL_APPROVER_ENDPOINT")
                dev_mode = os.getenv("HITL_DEV_MODE", "").lower() in (
                    "1", "true", "on",
                )
                hitl_configured = bool(approver) or dev_mode
                tool_results: dict[str, dict[str, Any]] = {}
                for tool_name in approvals_needed:
                    if tool_name not in SIDE_EFFECT_TOOLS:
                        continue
                    fn, _schema = SIDE_EFFECT_TOOLS[tool_name]
                    args = tool_args_map.get(tool_name, {})
                    if not args:
                        await out_q.put({
                            "type": "tool_skipped",
                            "tool": tool_name,
                            "reason": "no tool_args produced by case_drafter",
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
                        emit_event(Event(
                            name="tool.failed",
                            ok=False,
                            error=str(exc),
                            args_redacted={"tool": tool_name},
                        ))
                        await out_q.put({
                            "type": "tool_error",
                            "tool": tool_name,
                            "error": str(exc),
                        })
                        continue
                    tool_results[tool_name] = result
                    await out_q.put({
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result,
                    })

                cycle_ms = round((monotonic() - request_start) * 1000.0, 1)
                blocked = bool(
                    final.get("audit_trail", {}).get("blocked_reasons")
                )
                emit_event(Event(
                    name="response.returned",
                    ok=True,
                    value=cycle_ms,
                    unit="ms",
                ))
                # Brief Section 4 KPI emitters. Wired here so a single
                # supplier-review request stamps every KPI declared in
                # ``accelerator.yaml.kpis`` without scattering emitters
                # across workers.
                emit_event(Event(
                    name="supplier_review_cycle_time",
                    value=cycle_ms,
                    unit="ms",
                    args_redacted={
                        "supplier_id": request.get("supplier_id"),
                        "blocked": blocked,
                    },
                ))
                # autonomous_triage_coverage: 1.0 when the workflow
                # produced both side-effect tool args AND was not
                # blocked by an upstream guard; 0.0 otherwise. Per-call
                # ratio rolls up to the brief-target % over a window.
                triage_ok = bool(approvals_needed) and not blocked
                emit_event(Event(
                    name="autonomous_triage_coverage",
                    value=1.0 if triage_ok else 0.0,
                    unit="ratio",
                    args_redacted={
                        "supplier_id": request.get("supplier_id"),
                    },
                ))
                if tool_results:
                    final["tool_results"] = tool_results
                await out_q.put({"type": "final", "briefing": final})
            except Exception as exc:
                # In-band exception so the consumer loop can re-raise on
                # the same task and FastAPI's outer ``gen()`` emits a
                # typed ``error`` event.
                await out_q.put({"_error": exc})
            finally:
                await out_q.put(None)

        orch_task = asyncio.create_task(
            orchestrate(), name="contoso-supplier-risk-orchestrate",
        )
        get_task: asyncio.Task[Any] | None = None
        try:
            while True:
                if get_task is None:
                    get_task = asyncio.ensure_future(out_q.get())
                done, _pending = await asyncio.wait({get_task}, timeout=15.0)
                if get_task not in done:
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
            if get_task is not None and not get_task.done():
                get_task.cancel()
            if not orch_task.done():
                orch_task.cancel()
                try:
                    await orch_task
                except (asyncio.CancelledError, Exception):  # noqa: S110
                    pass

    # ----------------------------------------------------------- internals
    async def _resolve_agent_version(self, agent_name: str) -> str | None:
        """Return the latest version id for a Foundry PromptAgent.

        ``FoundryAgent`` requires an explicit ``agent_version`` for
        PromptAgents (the kind bootstrap creates). When omitted, the
        SDK silently falls back to inline chat mode and the model
        service rejects the request with ``Missing required parameter:
        'model'``. Cached per workflow.
        """
        if agent_name in self._agent_versions:
            return self._agent_versions[agent_name]
        if self._version_lock is None:
            self._version_lock = asyncio.Lock()
        async with self._version_lock:
            if agent_name in self._agent_versions:
                return self._agent_versions[agent_name]
            endpoint = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT")
            if not endpoint:
                return None
            try:
                from azure.ai.projects.aio import AIProjectClient
            except Exception:
                return None
            try:
                proj = AIProjectClient(
                    endpoint=endpoint, credential=self._credential,
                )
                try:
                    versions: list[str] = []
                    async for v in proj.agents.list_versions(agent_name):
                        vid = getattr(v, "version", None)
                        if isinstance(vid, str) and vid:
                            versions.append(vid)
                finally:
                    await proj.close()
            except Exception as exc:
                emit_event(Event(
                    name="agent.version_lookup_failed",
                    ok=False, error=f"{agent_name}: {exc}",
                ))
                return None
            if not versions:
                return None
            try:
                latest = max(versions, key=lambda x: int(x))
            except ValueError:
                latest = max(versions)
            self._agent_versions[agent_name] = latest
            return latest

    async def _invoke_agent(
        self, agent_name: str, prompt: str, state: WorkerState,
    ) -> str:
        """Retrieve a Foundry agent and run one turn.

        When ``state.chunks`` is set (the streaming SSE path), the
        agent runs with ``stream=True`` and each
        ``AgentResponseUpdate`` is forwarded as a ``chunk`` event into
        the merged event queue for live UI feedback. The full text is
        reassembled from the final response so downstream parsing
        operates on the complete payload.
        """
        if FoundryAgent is None:
            emit_event(Event(
                name="worker.completed",
                args_redacted={"agent": agent_name, "stub": True},
            ))
            return "{}"
        project_endpoint = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT")
        if not project_endpoint:
            raise RuntimeError(
                "AZURE_AI_FOUNDRY_ENDPOINT is not set -- required by "
                "FoundryAgent"
            )
        agent_version = await self._resolve_agent_version(agent_name)
        agent = FoundryAgent(
            project_endpoint=project_endpoint,
            credential=self._credential,
            agent_name=agent_name,
            agent_version=agent_version,
            allow_preview=True,
        )

        if state.chunks is None:
            result = await agent.run(prompt)
            self._merge_usage(state, getattr(result, "usage", None))
            self._capture_retrieved_uris(state, agent_name, result)
            return result.text

        response_stream = agent.run(prompt, stream=True)
        chunks_buf: list[str] = []
        async for update in response_stream:
            delta = getattr(update, "text", None) or ""
            if not delta:
                continue
            chunks_buf.append(delta)
            try:
                state.chunks.put_nowait({
                    "type": "chunk",
                    "agent": agent_name,
                    "worker_id": self._agent_to_wid.get(agent_name),
                    "delta": delta,
                })
            except asyncio.QueueFull:  # pragma: no cover - defensive
                pass
        final_response = await response_stream.get_final_response()
        self._merge_usage(state, getattr(final_response, "usage", None))
        self._capture_retrieved_uris(state, agent_name, final_response)
        return getattr(final_response, "text", None) or "".join(chunks_buf)

    @staticmethod
    def _capture_retrieved_uris(
        state: WorkerState, agent_name: str, response: Any,
    ) -> None:
        """Stash citation URIs from a Foundry tool trace onto ``state``.

        ``SupervisorDAG._run_one`` reads this back via
        ``state.retrieved_uris[agent_name]`` and stamps it onto the
        parsed dict (as ``_retrieved_uris``) before invoking the
        worker's validator, so per-agent validators can call
        :func:`assert_no_hallucinated_urls` in ``foundry_tool``
        retrieval mode where Python never sees the search call
        directly. Capture failure is swallowed -- validators fail
        open on empty allowed sets.
        """
        try:
            from src.accelerator_baseline.citations import (
                extract_tool_trace_uris,
            )
            uris = extract_tool_trace_uris(response)
            state.retrieved_uris[agent_name] = sorted(uris)
        except Exception:  # noqa: BLE001 - never fail on telemetry
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

    async def _aggregate(self, state: WorkerState) -> dict[str, Any]:
        """Compose the 5-section supplier-risk report deterministically.

        The workflow does NOT call a supervisor LLM here -- worker
        outputs are merged in code so the response is auditable, the
        cost contribution of the aggregation step is zero, and the
        brief Section 6 RAI guards run BEFORE any side-effect tool is
        queued.

        Brief Section 6 RAI guards (this is the canonical enforcement
        point; ``case_drafter.validate.py`` now only enforces shape /
        allow-list / PII):

        * If ``intake_validator.missing_required_inputs`` is non-empty
          OR ``risk_scorer.risk_scorecard.policy_matrix_match`` is
          false, ``requires_approval`` is forced to ``[]`` and
          ``tool_args`` to ``{}``. The blocker is surfaced in
          ``audit_trail.blocked_reasons`` and the executive summary.
        * Tool names are filtered to ``src.tools.SIDE_EFFECT_TOOLS`` --
          a defense-in-depth check against drift between the
          case_drafter allow-list and the registry.
        """
        outputs = state.outputs
        intake = outputs.get("intake_validator") or {}
        evidence = outputs.get("evidence_retriever") or {}
        risk = outputs.get("risk_scorer") or {}
        drafter = outputs.get("case_drafter") or {}

        intake_summary = intake.get("intake_summary") or {}
        missing_required = list(intake.get("missing_required_inputs") or [])
        data_quality_warnings = list(
            intake.get("data_quality_warnings") or []
        )

        evidence_pack = list(evidence.get("evidence_pack") or [])
        coverage_gaps = list(evidence.get("coverage_gaps") or [])

        scorecard = risk.get("risk_scorecard") or {}
        unresolved_questions = list(risk.get("unresolved_questions") or [])
        risk_level = scorecard.get("overall_risk_level") or "unknown"
        confidence = scorecard.get("confidence") or "low"
        policy_matrix_match = bool(scorecard.get("policy_matrix_match"))

        next_actions = list(drafter.get("recommended_next_actions") or [])
        recommendation_summary = drafter.get("recommendation_summary") or ""
        hitl_decision_prompt = drafter.get("hitl_decision_prompt") or ""
        tool_previews = drafter.get("tool_previews") or {}

        # Brief Section 6 RAI guards.
        blocked_reasons: list[str] = []
        if missing_required:
            blocked_reasons.append(
                f"missing required inputs: {missing_required}"
            )
        if not policy_matrix_match:
            blocked_reasons.append("risk_scorer.policy_matrix_match=false")

        if blocked_reasons:
            requires_approval: list[str] = []
            tool_args: dict[str, dict[str, Any]] = {}
        else:
            # Only allow tools the registry knows about.
            requires_approval = [
                t for t in tool_previews if t in SIDE_EFFECT_TOOLS
            ]
            tool_args = {
                t: dict(tool_previews[t]) for t in requires_approval
            }

        # Audit trail: workers invoked, confidence, dedupe citations
        # across worker outputs, list HITL checkpoints to be triggered.
        citations: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for src_list in (
            evidence.get("sources") or [],
            risk.get("sources") or [],
            drafter.get("sources") or [],
        ):
            for s in src_list:
                if not isinstance(s, dict):
                    continue
                ss = s.get("source_system", "")
                src = s.get("source", "")
                key = (ss, src)
                if not (ss and src) or key in seen:
                    continue
                seen.add(key)
                citations.append({"source_system": ss, "source": src})
        audit_trail: dict[str, Any] = {
            "workers_invoked": list(outputs.keys()),
            "confidence": confidence,
            "citations": citations,
            "hitl_checkpoints": list(requires_approval),
            "blocked_reasons": blocked_reasons,
        }

        # Executive summary -- 3 deterministic bullets that always
        # name the supplier and the blocker (if any) or the queued
        # tools so the analyst reads the punchline first.
        bullets: list[str] = []
        supplier_name = (
            intake_summary.get("supplier_name")
            or state.request.get("supplier_name")
            or "the supplier"
        )
        supplier_id = (
            intake_summary.get("supplier_id")
            or state.request.get("supplier_id")
            or ""
        )
        if blocked_reasons:
            bullets.append(
                f"Review for {supplier_name} ({supplier_id}) is blocked: "
                f"{'; '.join(blocked_reasons)}."
            )
        else:
            bullets.append(
                f"Risk for {supplier_name} ({supplier_id}) is "
                f"{risk_level} with {confidence} confidence."
            )
        if evidence_pack:
            distinct_systems = len({
                i.get("source_system") for i in evidence_pack
                if isinstance(i, dict)
            })
            gap_tail = (
                f" Coverage gap: {coverage_gaps[0]}" if coverage_gaps else ""
            )
            bullets.append(
                f"Evidence pack contains {len(evidence_pack)} cited "
                f"items across {distinct_systems} approved sources."
                + gap_tail
            )
        else:
            bullets.append(
                "No evidence retrieved -- "
                + (
                    coverage_gaps[0] if coverage_gaps
                    else "verify the knowledge base is wired."
                )
            )
        if blocked_reasons:
            bullets.append(
                "No side-effect tools queued; analyst must resolve the "
                "blocker before any case is created."
            )
        elif requires_approval:
            bullets.append(
                f"Drafted {len(requires_approval)} side-effect tool "
                f"call(s) pending HITL approval: "
                f"{', '.join(requires_approval)}."
            )
        else:
            bullets.append(
                "No side-effect tools required; recommendation is "
                "advisory only."
            )

        return {
            "executive_summary": bullets[:3],
            "audit_trail": audit_trail,
            "requires_approval": requires_approval,
            "tool_args": tool_args,
            # Pass-through worker outputs (5-section UI rendering).
            "intake_summary": intake_summary,
            "missing_required_inputs": missing_required,
            "data_quality_warnings": data_quality_warnings,
            "evidence_pack": evidence_pack,
            "coverage_gaps": coverage_gaps,
            "risk_scorecard": scorecard,
            "unresolved_questions": unresolved_questions,
            "recommended_next_actions": next_actions,
            "recommendation_summary": recommendation_summary,
            "hitl_decision_prompt": hitl_decision_prompt,
            # ``citations`` at the top level is what the eval runner's
            # ``must_cite: true`` predicate looks for.
            "citations": citations,
        }


def build_workflow(context: Any) -> BaseWorkflow:
    """Scenario workflow factory.

    Signature matches the contract in ``src.workflow.registry``:
    ``build_workflow(ScenarioContext) -> BaseWorkflow``.
    """
    indexes = getattr(context, "retrieval_indexes", ()) or ()
    primary = indexes[0].name if indexes else "supplier-evidence"
    return ContosoSupplierRiskWorkflow(primary_index_name=primary)
