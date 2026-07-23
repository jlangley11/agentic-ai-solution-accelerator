from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).parents[1]
LINT_PATH = ROOT / "scripts" / "accelerator-lint.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("raw_exception_lint", LINT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "sink",
    [
        'raise HTTPException(status_code=400, detail=str(exc))',
        'return JSONResponse({"detail": str(exc)}, status_code=400)',
        'yield events.emit_failed(message=f"{exc}")',
        'yield events.emit_failed(message=exc.args[0])',
        'emit_event(Event(error=f"{agent_name}: {exc}"))',
        'error = str(exc)',
    ],
)
def test_raw_exception_text_in_stream_event_is_blocked(
    tmp_path,
    monkeypatch,
    sink: str,
) -> None:
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    source = tmp_path / "src/agent_host.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def handler():\n"
        "    try:\n"
        "        run()\n"
        "    except Exception as exc:\n"
        f"        {sink}\n",
        encoding="utf-8",
    )
    context = lint.Ctx()
    context.load()

    findings = lint.no_raw_exception_streaming(context)

    assert len(findings) == 1
    assert findings[0].rule == "raw-exception-streaming"


def test_exception_type_and_controlled_message_are_allowed(tmp_path, monkeypatch) -> None:
    lint = _load_lint()
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    source = tmp_path / "src/serving/sse.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def handler():\n"
        "    try:\n"
        "        run()\n"
        "    except Exception as exc:\n"
        "        emit_event(Event(error=type(exc).__name__))\n"
        "        return JSONResponse({'message': exc.client_message})\n",
        encoding="utf-8",
    )
    context = lint.Ctx()
    context.load()

    assert lint.no_raw_exception_streaming(context) == []
