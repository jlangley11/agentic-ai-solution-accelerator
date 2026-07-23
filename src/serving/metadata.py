"""Scenario metadata and UX feedback endpoints."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.accelerator_baseline.telemetry import Event, emit_event
from src.workflow.registry import ScenarioBundle


class FeedbackRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    section: str = Field(
        default="overall",
        max_length=128,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    rating: Literal["up", "down"]
    comment: str = Field(default="", max_length=4000)


def scenario_metadata(bundle: ScenarioBundle) -> dict[str, Any]:
    response_schema = (
        bundle.response_schema.model_json_schema()
        if bundle.response_schema is not None
        else None
    )
    experience = bundle.experience
    return {
        "id": bundle.id,
        "title": experience.title if experience else bundle.id.replace("-", " ").title(),
        "description": experience.description if experience else "",
        "experience_kind": experience.kind if experience else "api",
        "endpoint_path": bundle.endpoint_path,
        "request_schema": bundle.request_schema.model_json_schema(),
        "response_schema": response_schema,
        "implementation": (
            {
                "agent_type": bundle.implementation.agent_type,
                "implementation_pattern": (
                    bundle.implementation.implementation_pattern
                ),
                "orchestration_pattern": (
                    bundle.implementation.orchestration_pattern
                ),
                "application_shell": bundle.implementation.application_shell,
            }
            if bundle.implementation is not None
            else None
        ),
        "agents": [
            {
                "id": agent.id,
                "foundry_name": agent.foundry_name,
                "grounding": (
                    agent.retrieval.mode if agent.retrieval is not None else "none"
                ),
            }
            for agent in bundle.agents
        ],
        "output_sections": list(experience.output_sections) if experience else [],
        "approval": {
            "mode": "external",
        },
        "stream_contract": {
            "validated_partial_event": (
                "partial"
                if bool(getattr(bundle.workflow, "validated_partials", False))
                else None
            ),
            "final_event": "final",
            "terminal_event": "done",
            "unvalidated_chunk_event": "chunk",
        },
    }


def record_feedback(payload: FeedbackRequest) -> dict[str, str]:
    feedback_id = uuid.uuid4().hex
    run_hash = hashlib.sha256(payload.run_id.encode("utf-8")).hexdigest()[:16]
    emit_event(
        Event(
            name="ux.feedback",
            args_redacted={
                "feedback_id": feedback_id,
                "run_id_hash": run_hash,
                "section": payload.section,
                "rating": payload.rating,
                "comment_length": len(payload.comment),
            },
        )
    )
    return {"status": "accepted", "feedback_id": feedback_id}
