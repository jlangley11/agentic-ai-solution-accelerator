"""Run optional Foundry-native relevance and groundedness evaluators.

This supplements, rather than replaces, the accelerator's deterministic
business assertions. It consumes the query/response/context fields written by
``evals/quality/run.py``.

Evaluator input fields are written only when quality evaluation is run with
``--include-evaluator-inputs`` because they can contain customer data.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from collections.abc import Callable
from typing import Any

from azure.identity import DefaultAzureCredential

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent


def load_rows(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def model_config() -> dict[str, Any]:
    endpoint = os.getenv("AZURE_AI_FOUNDRY_OPENAI_ENDPOINT", "").rstrip("/")
    deployment = (
        os.getenv("AZURE_AI_FOUNDRY_MODEL")
        or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        or ""
    )
    if not endpoint or not deployment:
        raise RuntimeError(
            "AZURE_AI_FOUNDRY_OPENAI_ENDPOINT and AZURE_AI_FOUNDRY_MODEL "
            "(or AZURE_AI_MODEL_DEPLOYMENT_NAME) are required."
        )
    return {
        "azure_endpoint": endpoint,
        "azure_deployment": deployment,
        "api_version": os.getenv("AZURE_AI_FOUNDRY_API_VERSION", "2024-10-21"),
    }


def build_evaluators() -> dict[str, Callable[..., dict[str, Any]]]:
    try:
        from azure.ai.evaluation import (  # pyright: ignore[reportMissingImports]
            GroundednessEvaluator,
            RelevanceEvaluator,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Install the optional evaluation dependencies with "
            '`python -m pip install -e ".[evals]"`.'
        ) from exc
    credential = DefaultAzureCredential()
    config = model_config()
    return {
        "relevance": RelevanceEvaluator(config, credential=credential),
        "groundedness": GroundednessEvaluator(config, credential=credential),
    }


def evaluate_rows(
    rows: list[dict[str, Any]],
    evaluators: dict[str, Callable[..., dict[str, Any]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        query = str(row.get("query") or "")
        response = str(row.get("response") or "")
        context = str(row.get("context") or "")
        result = {
            "case_id": row.get("case_id"),
            "suite": "foundry",
            "source_passed": bool(row.get("passed")),
        }
        if not query or not response:
            result.update(
                {
                    "passed": False,
                    "reason": "quality result lacks query/response fields",
                }
            )
            output.append(result)
            continue
        relevance = evaluators["relevance"](query=query, response=response)
        groundedness = (
            evaluators["groundedness"](
                query=query,
                response=response,
                context=context,
            )
            if context
            else {"groundedness": None, "groundedness_result": "not_applicable"}
        )
        result.update(
            {
                "passed": bool(
                    relevance.get("relevance_result") == "pass"
                    and (
                        groundedness.get("groundedness_result")
                        in {"pass", "not_applicable"}
                    )
                ),
                "relevance": relevance,
                "groundedness": groundedness,
            }
        )
        output.append(result)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        default=ROOT / "evals" / "quality" / "results.jsonl",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=HERE / "results.jsonl",
    )
    args = parser.parse_args(argv)
    rows = load_rows(args.input)
    if not rows:
        print(f"error: no quality results found at {args.input}", file=sys.stderr)
        return 1
    try:
        results = evaluate_rows(rows, build_evaluators())
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports evaluator failure
        print(f"error: Foundry evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(result) for result in results) + "\n",
        encoding="utf-8",
    )
    for result in results:
        print(json.dumps(result))
    return 0 if all(result.get("passed") for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
