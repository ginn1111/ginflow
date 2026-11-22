"""Single source of truth for which Kanban card a gate hook acts on."""
from __future__ import annotations

import os


def selected_task_id(args: dict | None, task_id: str = "") -> str:
    """args.task_id, then HERMES_KANBAN_TASK, then the Hermes hook task_id kwarg.

    The hook kwarg is Hermes' per-call agent id (not a card id) for dispatched workers,
    so it ranks last.
    """
    for value in ((args or {}).get("task_id"), os.environ.get("HERMES_KANBAN_TASK"), task_id):
        text = str(value or "").strip()
        if text:
            return text
    return ""
