from __future__ import annotations

from pydantic import BaseModel

from src.serving.metadata import FeedbackRequest, record_feedback, scenario_metadata
from src.workflow.registry import (
    ScenarioAgent,
    ScenarioBundle,
    ScenarioExperience,
    ScenarioImplementation,
)


class RequestModel(BaseModel):
    query: str


class ResponseModel(BaseModel):
    answer: str


class StubWorkflow:
    async def stream(self, request):
        if False:
            yield request


class ValidatedPartialWorkflow(StubWorkflow):
    validated_partials = True


def _bundle(workflow=None) -> ScenarioBundle:
    return ScenarioBundle(
        id="demo",
        package="tests",
        request_schema=RequestModel,
        response_schema=ResponseModel,
        workflow=workflow or StubWorkflow(),
        endpoint_path="/demo/stream",
        agents=(ScenarioAgent(id="worker", foundry_name="demo-worker"),),
        retrieval_indexes=(),
        evals_quality="",
        evals_redteam="",
        experience=ScenarioExperience(
            kind="form-report",
            title="Demo",
            output_sections=({"key": "answer", "label": "Answer"},),
        ),
        implementation=ScenarioImplementation(
            agent_type="prompt-agent",
            implementation_pattern="managed-prompt",
            orchestration_pattern="single-agent",
            application_shell="workbench",
        ),
    )


def test_scenario_metadata_exposes_schemas_and_experience() -> None:
    payload = scenario_metadata(_bundle())

    assert payload["id"] == "demo"
    assert payload["endpoint_path"] == "/demo/stream"
    assert payload["request_schema"]["required"] == ["query"]
    assert payload["response_schema"]["required"] == ["answer"]
    assert payload["output_sections"][0]["key"] == "answer"
    assert payload["implementation"]["agent_type"] == "prompt-agent"
    assert payload["implementation"]["implementation_pattern"] == "managed-prompt"
    assert payload["approval"] == {"mode": "external"}
    assert payload["stream_contract"]["validated_partial_event"] is None


def test_metadata_advertises_validated_partials_only_when_declared() -> None:
    payload = scenario_metadata(_bundle(ValidatedPartialWorkflow()))

    assert payload["stream_contract"]["validated_partial_event"] == "partial"


def test_feedback_emits_only_redacted_dimensions(monkeypatch) -> None:
    emitted = []
    monkeypatch.setattr("src.serving.metadata.emit_event", emitted.append)

    result = record_feedback(
        FeedbackRequest(
            run_id="run-1",
            section="answer",
            rating="down",
            comment="Contains customer detail that must not be logged.",
        )
    )

    assert result["status"] == "accepted"
    assert emitted[0].name == "ux.feedback"
    assert "comment" not in emitted[0].args_redacted
    assert "run_id" not in emitted[0].args_redacted
    assert len(emitted[0].args_redacted["run_id_hash"]) == 16
    assert emitted[0].args_redacted["comment_length"] == 49
