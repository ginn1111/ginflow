"""Framework-agnostic Ginflow card routing policy."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def workspace(task: dict[str, Any]) -> Path | None:
    value = task.get("workspace_path") or task.get("workspace")
    if not value:
        return None
    if isinstance(value, str) and value.startswith("dir:"):
        value = value[4:]
    try:
        return Path(value).expanduser().resolve()
    except (OSError, TypeError, ValueError):
        return None


def route(tasks: list[dict[str, Any]], current: Path, explicit_id: str | None = None) -> dict[str, Any]:
    current = current.resolve()
    matching = [task for task in tasks if workspace(task) == current]
    if explicit_id:
        selected = next((task for task in tasks if task.get("id") == explicit_id), None)
        if selected is None:
            return {"route": "no_card", "action": "work_shaping"}
        if workspace(selected) != current:
            return {"route": "workspace_mismatch", "action": "block"}
        matching = [selected]
    if not matching:
        return {"route": "no_card", "action": "work_shaping"}
    if len(matching) > 1 and not explicit_id:
        candidates = sorted(
            ({"id": task.get("id"), "title": task.get("title", "?")} for task in matching),
            key=lambda item: (str(item["id"]), str(item["title"])),
        )
        return {"route": "needs_card_selection", "action": "orchestrator", "candidates": candidates}
    selected = matching[0]
    status = {"todo": "next", "ready": "next", "running": "in_progress"}.get(
        str(selected.get("status")), selected.get("status")
    )
    if status == "blocked":
        metadata = selected.get("metadata")
        return {"route": "blocked_card", "action": "orchestrator", "id": selected.get("id"),
                "blocker_metadata": selected.get("blocker_metadata") or (
                    metadata.get("blocker") if isinstance(metadata, dict) else None)}
    if status == "next":
        return {"route": "validate_card_docs", "action": "validate", "id": selected.get("id")}
    if status == "in_progress":
        return {"route": "ready_to_start", "action": "execute", "id": selected.get("id")}
    if status in {"done", "cancelled", "archived"}:
        return {"route": "terminal_card", "action": "block", "id": selected.get("id")}
    return {"route": "invalid_status", "action": "block", "id": selected.get("id")}


# Contract alias for adapters retaining existing private seam.
def _route(tasks: list[dict[str, Any]], current: Path, explicit_id: str | None = None) -> dict[str, Any]:
    return route(tasks, current, explicit_id)


__all__ = ["route", "workspace"]
