from __future__ import annotations

import json
import pathlib

import jsonschema

from src.accelerator_cli.protocol import CommandResult, ResultStatus, Stage

ROOT = pathlib.Path(__file__).parents[1]
SCHEMA = ROOT / "schemas" / "accelerator-cli-result.schema.json"


def test_command_result_matches_published_json_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    payload = CommandResult(
        stage=Stage.DISCOVER,
        status=ResultStatus.NEEDS_INPUT,
        summary="Discovery needs input.",
    ).to_dict()

    jsonschema.validate(payload, schema)
