"""Non-blocking function-call tracing decorator."""

from __future__ import annotations

import functools
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

from .identity import resolve_identity
from .sanitize import sanitize
from .storage import append_record

F = TypeVar("F", bound=Callable[..., Any])
CONFIG_START = Path.cwd


def _enabled() -> bool:
    """Tracing is on when GINFLOW_LOG=1 or the project config enables ginflow.trace."""
    if os.environ.get("GINFLOW_LOG") == "1":
        return True
    if os.environ.get("GINFLOW_LOG") is not None:
        return False
    return _config_trace_enabled()


def _project_config() -> dict | None:
    """Read the nearest project-local Ginflow config."""
    return _find_config(CONFIG_START())


def _config_trace_enabled() -> bool:
    """Read ginflow.trace from the nearest project config."""
    config = _project_config()
    if config is None:
        return False
    context = config.get("ginflow")
    if not isinstance(context, dict):
        return False
    value = context.get("trace")
    return value is True


def _read_config(file: Path) -> dict | None:
    try:
        import yaml
    except ImportError:
        return _read_simple_config(file)
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _read_simple_config(file: Path) -> dict | None:
    """Read flat ginflow config fields needed by tracing without PyYAML."""
    try:
        lines = file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    config: dict[str, object] = {}
    ginflow: dict[str, object] = {}
    in_ginflow = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.strip() == "ginflow:":
            in_ginflow = True
            continue
        if in_ginflow and line[:1].isspace():
            key, separator, value = line.strip().partition(":")
            if not separator:
                continue
            value = value.strip().strip("'\"")
            if key == "trace":
                ginflow[key] = value.lower() == "true"
            else:
                ginflow[key] = value
            continue
        in_ginflow = False
        key, separator, value = line.partition(":")
        if separator:
            config[key.strip()] = value.strip().strip("'\"")
    config["ginflow"] = ginflow
    return config


def _find_config(start: Path) -> dict | None:
    path = Path(start).expanduser().resolve()
    while True:
        candidate = path / ".ginflow.yaml"
        if candidate.is_file():
            data = _read_config(candidate)
            if data is not None:
                return data
        if path.parent == path:
            return None
        path = path.parent


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _trace_root() -> Path | None:
    config = _project_config()
    if config is None:
        return None
    context = config.get("ginflow")
    if not isinstance(context, dict):
        return None
    workspace = context.get("workspace")
    if not isinstance(workspace, str) or not workspace:
        return None
    path = Path(workspace).expanduser()
    if not path.is_absolute() or not path.is_dir():
        return None
    return path.resolve() / ".ginflow"


def _write(directory: str, identity, record: dict[str, Any]) -> None:
    root = _trace_root()
    if root is None:
        try:
            print(f"ginflow-trace: unable to write {directory}: invalid workspace", file=sys.stderr)
        except Exception:
            pass
        return
    try:
        append_record(root / directory, identity.filename, record)
    except Exception as error:  # tracing must never affect the wrapped function
        try:
            if directory != "errors":
                append_record(
                    root / "errors",
                    identity.filename,
                    {
                        "timestamp": _timestamp(),
                        "function": record.get("function", "unknown"),
                        "status": "trace_error",
                        "error_type": type(error).__name__,
                        "message": sanitize(str(error)),
                    },
                )
        except Exception:
            pass
        try:
            print(f"ginflow-trace: unable to write {directory}: {type(error).__name__}", file=sys.stderr)
        except Exception:
            pass


def trace(function: F) -> F:
    """Trace a function when enabled; preserve its behavior if tracing fails."""
    @functools.wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not _enabled():
            return function(*args, **kwargs)
        identity = resolve_identity(args, kwargs)
        base: dict[str, Any] = {"timestamp": _timestamp(), "function": function.__name__}
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            _write("errors", identity, base | {
                "input": sanitize({"args": args, "kwargs": kwargs}),
                "status": "error",
                "error_type": type(error).__name__,
                "message": sanitize(str(error)),
            })
            raise
        _write("logs", identity, base | {
            "input": sanitize({"args": args, "kwargs": kwargs}),
            "output": sanitize(result),
            "status": "success",
        })
        return result
    return cast(F, wrapped)
