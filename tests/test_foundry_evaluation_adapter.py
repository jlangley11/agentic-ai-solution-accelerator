from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "evals" / "foundry" / "run.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("foundry_eval_adapter", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubEvaluator:
    def __init__(self, key: str) -> None:
        self.key = key

    def __call__(self, **_kwargs):
        return {self.key: 5, f"{self.key}_result": "pass"}


def test_evaluate_rows_combines_native_scores() -> None:
    module = _load_module()

    results = module.evaluate_rows(
        [
            {
                "case_id": "q-1",
                "passed": True,
                "query": "What is the policy?",
                "response": "The policy requires approval.",
                "context": "Approval is required.",
            }
        ],
        {
            "relevance": StubEvaluator("relevance"),
            "groundedness": StubEvaluator("groundedness"),
        },
    )

    assert results[0]["passed"] is True
    assert results[0]["relevance"]["relevance"] == 5
    assert results[0]["groundedness"]["groundedness"] == 5


def test_missing_context_skips_groundedness_without_faking_failure() -> None:
    module = _load_module()

    results = module.evaluate_rows(
        [
            {
                "case_id": "q-2",
                "passed": True,
                "query": "Summarize.",
                "response": "Summary.",
                "context": "",
            }
        ],
        {
            "relevance": StubEvaluator("relevance"),
            "groundedness": StubEvaluator("groundedness"),
        },
    )

    assert results[0]["passed"] is True
    assert results[0]["groundedness"]["groundedness_result"] == "not_applicable"
