from __future__ import annotations

import asyncio
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).parents[1]
RUNNER = ROOT / "evals" / "quality" / "run.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("quality_privacy_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubResponse:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def aiter_lines(self):
        yield (
            'data: {"type":"final","briefing":{"answer":"Sensitive answer",'
            '"citations":[{"quote":"Sensitive context"}]}}'
        )


class StubClient:
    def stream(self, *_args, **_kwargs):
        return StubResponse()


def test_evaluator_inputs_are_opt_in() -> None:
    runner = _load_runner()
    case = {
        "case_id": "q-privacy",
        "query": "Sensitive query",
        "expected": {},
    }

    default = asyncio.run(
        runner.run_case(
            StubClient(),
            "https://example.invalid",
            "/run",
            case,
            model="gpt-5-mini",
            cost_override=0.01,
            cost_per_second=0.0,
        )
    )
    enabled = asyncio.run(
        runner.run_case(
            StubClient(),
            "https://example.invalid",
            "/run",
            case,
            model="gpt-5-mini",
            cost_override=0.01,
            cost_per_second=0.0,
            include_evaluator_inputs=True,
        )
    )

    assert "response" not in default
    assert "context" not in default
    assert "Sensitive answer" in enabled["response"]
    assert enabled["context"] == "Sensitive context"
