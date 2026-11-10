"""Focused tests for the standalone Ginflow trace package."""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ginflow_trace.decorator import trace
from ginflow_trace.identity import resolve_identity
from ginflow_trace.sanitize import sanitize
from ginflow_trace.storage import append_record


def test_identity_filenames():
    known = resolve_identity((), {"session_worker_id": "session-1", "task_id": "task-2"})
    assert known.filename == "session-1__task-2.json"
    unknown = resolve_identity((), {"task_id": "task-2"})
    assert unknown.filename.startswith("unknown__task-2__") and unknown.filename.endswith(".json")


def test_identity_prefers_hook_context():
    context = SimpleNamespace(session_worker_id="hook-session", kanban_worker_id="hook-task")
    identity = resolve_identity((context,), {"session_worker_id": "argument-session"})
    assert identity.filename == "argument-session__hook-task.json"


def test_storage_appends_valid_json():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        append_record(root, "worker__task.json", {"timestamp": "now", "function": "one"})
        append_record(root, "worker__task.json", {"timestamp": "later", "function": "two"})
        records = json.loads((root / "worker__task.json").read_text())
        assert isinstance(records, list)
        assert [record["function"] for record in records] == ["one", "two"]


def test_sanitizes_sensitive_and_large_values():
    value = sanitize({"api_key": "secret", "body": "x" * 5000})
    assert isinstance(value, dict)
    assert value["api_key"] == "<redacted>"
    assert value["body"].endswith("<truncated>")


def test_disabled_trace_is_noop():
    old = os.environ.get("GINFLOW_LOG")
    os.environ["GINFLOW_LOG"] = "0"  # explicit off overrides any ginflow.trace config
    try:
        calls = []

        @trace
        def function(value):
            calls.append(value)
            return value + 1

        assert function(1) == 2
        assert calls == [1]
    finally:
        if old is None:
            os.environ.pop("GINFLOW_LOG", None)
        else:
            os.environ["GINFLOW_LOG"] = old


def test_trace_success_records_result_in_configured_workspace():
    old = os.environ.get("GINFLOW_LOG")
    os.environ["GINFLOW_LOG"] = "1"
    try:
        with TemporaryDirectory() as directory:
            import ginflow_trace.decorator as decorator

            workspace = Path(directory) / "working-repo"
            workspace.mkdir()
            config = {"ginflow": {"workspace": str(workspace), "trace": True}}

            @trace
            def compute_doubled(value, **kwargs):
                return {"doubled": value * 2}

            log_file = workspace / ".ginflow/logs/session-1__task-2.json"
            with patch.object(decorator, "_project_config", return_value=config):
                assert compute_doubled(21, session_worker_id="session-1", task_id="task-2") == {"doubled": 42}

            records = json.loads(log_file.read_text(encoding="utf-8"))
            assert records == [
                {
                    "timestamp": records[0]["timestamp"],
                    "function": "compute_doubled",
                    "input": {
                        "args": [21],
                        "kwargs": {
                            "session_worker_id": "session-1",
                            "task_id": "task-2",
                        },
                    },
                    "output": {"doubled": 42},
                    "status": "success",
                }
            ]
    finally:
        if old is None:
            os.environ.pop("GINFLOW_LOG", None)
        else:
            os.environ["GINFLOW_LOG"] = old


def test_trace_does_not_fall_back_when_workspace_is_invalid():
    import ginflow_trace.decorator as decorator

    identity = resolve_identity((), {"session_worker_id": "session-1", "task_id": "task-2"})
    with patch.object(decorator, "_find_config", return_value={"ginflow": {"workspace": "relative"}}):
        with patch.object(decorator, "append_record") as append:
            decorator._write("logs", identity, {"function": "function", "status": "success"})
    append.assert_not_called()


def test_trace_records_plugin_function_name():
    """The recorded function name must match the decorated plugin function,
    not a generic or fixed value (ginflow-gate decorates real gate functions)."""
    old = os.environ.get("GINFLOW_LOG")
    os.environ["GINFLOW_LOG"] = "1"
    try:
        import ginflow_trace.decorator as decorator

        @trace
        def validate_completion(card, metadata=None, **kwargs):
            return None

        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            config = {"ginflow": {"workspace": str(workspace)}}
            log_file = workspace / ".ginflow/logs/session-1__task-2.json"

            with patch.object(decorator, "_project_config", return_value=config):
                validate_completion({"id": "X"}, session_worker_id="session-1", task_id="task-2")

            records = json.loads(log_file.read_text(encoding="utf-8"))
            assert records[-1]["function"] == "validate_completion"
    finally:
        if old is None:
            os.environ.pop("GINFLOW_LOG", None)
        else:
            os.environ["GINFLOW_LOG"] = old


def test_trace_error_does_not_replace_function_error():
    old = os.environ.get("GINFLOW_LOG")
    os.environ["GINFLOW_LOG"] = "1"
    try:
        @trace
        def function():
            raise ValueError("expected")

        try:
            function()
        except ValueError as error:
            assert str(error) == "expected"
        else:
            raise AssertionError("function exception was swallowed")
    finally:
        if old is None:
            os.environ.pop("GINFLOW_LOG", None)
        else:
            os.environ["GINFLOW_LOG"] = old


def test_trace_write_failure_is_non_blocking_and_recorded():
    old = os.environ.get("GINFLOW_LOG")
    os.environ["GINFLOW_LOG"] = "1"
    try:
        import ginflow_trace.decorator as decorator

        writes = []

        def failing_append(root, filename, record):
            writes.append((root.name, record["status"]))
            if root.name == "logs":
                raise OSError("disk full")

        @trace
        def function():
            return "result"

        with TemporaryDirectory() as directory:
            config = {"ginflow": {"workspace": directory}}
            with patch.object(decorator, "_project_config", return_value=config):
                with patch.object(decorator, "append_record", failing_append):
                    assert function() == "result"
        assert writes == [("logs", "success"), ("errors", "trace_error")]
    finally:
        if old is None:
            os.environ.pop("GINFLOW_LOG", None)
        else:
            os.environ["GINFLOW_LOG"] = old


def test_config_trace_enablement():
    """_enabled() obeys ginflow.trace in .ginflow.yaml when the env var is absent."""
    import ginflow_trace.decorator as decorator

    old = os.environ.get("GINFLOW_LOG")
    os.environ.pop("GINFLOW_LOG", None)
    try:
        with patch.object(decorator, "_find_config", return_value={"ginflow": {"trace": True}}):
            assert decorator._enabled() is True
        with patch.object(decorator, "_find_config", return_value={"ginflow": {"trace": False}}):
            assert decorator._enabled() is False
        with patch.object(decorator, "_find_config", return_value={"ginflow": {}}):
            assert decorator._enabled() is False
        with patch.object(decorator, "_find_config", return_value=None):
            assert decorator._enabled() is False
    finally:
        if old is None:
            os.environ.pop("GINFLOW_LOG", None)
        else:
            os.environ["GINFLOW_LOG"] = old


def test_env_overrides_config_enablement():
    """Explicit GINFLOW_LOG env wins over ginflow.trace config."""
    import ginflow_trace.decorator as decorator

    old = os.environ.get("GINFLOW_LOG")
    try:
        os.environ["GINFLOW_LOG"] = "0"
        with patch.object(decorator, "_find_config", return_value={"ginflow": {"trace": True}}):
            assert decorator._enabled() is False
        os.environ["GINFLOW_LOG"] = "1"
        with patch.object(decorator, "_find_config", return_value={"ginflow": {"trace": False}}):
            assert decorator._enabled() is True
    finally:
        if old is None:
            os.environ.pop("GINFLOW_LOG", None)
        else:
            os.environ["GINFLOW_LOG"] = old


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    print("PASS: ginflow trace")
