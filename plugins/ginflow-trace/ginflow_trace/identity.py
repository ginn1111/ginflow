"""Resolve worker identities and safe trace filenames."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from threading import Lock

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")
_UNKNOWN_IDS: dict[tuple[str, str], str] = {}
_LOCK = Lock()


@dataclass(frozen=True)
class Identity:
    session_worker_id: str
    kanban_worker_id: str
    filename: str


def _value(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _task_from_args(args: tuple[object, ...]) -> str:
    for item in args:
        if isinstance(item, dict):
            value = _value(item.get("task_id") or item.get("kanban_worker_id"))
            if value:
                return value
    return ""


def _context_value(context: object, names: tuple[str, ...]) -> str:
    """Read identity fields from mapping- or attribute-style hook context."""
    if isinstance(context, dict):
        for name in names:
            value = _value(context.get(name))
            if value:
                return value
    for name in names:
        value = _value(getattr(context, name, None))
        if value:
            return value
    return ""


def _safe(value: str) -> str:
    return _SAFE.sub("_", value).strip("._") or "unknown"


def resolve_identity(args: tuple[object, ...] = (), kwargs: dict[str, object] | None = None) -> Identity:
    kwargs = kwargs or {}
    contexts = [kwargs.get(name) for name in ("hook_context", "context", "ctx")]
    contexts.extend(item for item in args if isinstance(item, dict) or hasattr(item, "session_worker_id"))
    session = _value(kwargs.get("session_worker_id") or kwargs.get("session_id"))
    kanban = _value(kwargs.get("kanban_worker_id") or kwargs.get("task_id"))
    for context in contexts:
        session = session or _context_value(context, ("session_worker_id", "session_id"))
        kanban = kanban or _context_value(context, ("kanban_worker_id", "task_id"))
    session = session or _value(os.environ.get("HERMES_SESSION_WORKER_ID"))
    kanban = kanban or _task_from_args(args) or _value(os.environ.get("HERMES_KANBAN_TASK"))
    missing = not session or not kanban
    session_name, kanban_name = _safe(session), _safe(kanban)
    if missing:
        key = (session_name, kanban_name)
        with _LOCK:
            suffix = _UNKNOWN_IDS.setdefault(key, uuid.uuid4().hex)
        filename = f"{session_name}__{kanban_name}__{suffix}.json"
    else:
        filename = f"{session_name}__{kanban_name}.json"
    return Identity(session_name, kanban_name, filename)
