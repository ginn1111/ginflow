"""Build and render safe append-only worker blocker evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_ATTEMPTS = 3
BLOCKER_KINDS = frozenset({"transient", "unknown", "config_error", "persist_error", "human_input"})
NON_RECOVERABLE_KINDS = frozenset({"config_error", "persist_error", "human_input"})


def _required_text(name: str, value: Any, *, single_line: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    result = value.strip()
    if single_line and any(char in result for char in "\r\n"):
        raise ValueError(f"{name} must be a single line")
    return result


def _string_list(name: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    return [_required_text(f"{name} item", item, single_line=True) for item in value]


def build_blocker_event(
    *,
    event_id: str,
    card_id: str,
    workspace: str,
    previous_assignee: str,
    blocker_kind: str,
    error_summary: str,
    evidence: list[str],
    attempted_commands: list[str],
    occurred_at: str | None = None,
    attempt: int = 0,
) -> dict[str, Any]:
    """Return one validated blocked event without mutating Kanban state."""
    event_id = _required_text("event_id", event_id, single_line=True)
    card_id = _required_text("card_id", card_id, single_line=True)
    previous_assignee = _required_text("previous_assignee", previous_assignee, single_line=True)
    blocker_kind = _required_text("blocker_kind", blocker_kind, single_line=True)
    if blocker_kind not in BLOCKER_KINDS:
        raise ValueError("blocker_kind is unsupported")
    error_summary = _required_text("error_summary", error_summary, single_line=True)
    canonical_workspace = str(Path(_required_text("workspace", workspace)).expanduser().resolve())
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 0:
        raise ValueError("attempt must be a non-negative integer")
    timestamp = occurred_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    timestamp = _required_text("occurred_at", timestamp, single_line=True)
    if not timestamp.endswith("Z"):
        raise ValueError("occurred_at must be RFC3339 UTC")

    return {
        "event_id": event_id,
        "event_type": "blocked",
        "card_id": card_id,
        "workspace": canonical_workspace,
        "previous_assignee": previous_assignee,
        "blocker_kind": blocker_kind,
        "error_summary": error_summary,
        "evidence": _string_list("evidence", evidence),
        "attempted_commands": _string_list("attempted_commands", attempted_commands),
        "occurred_at": timestamp,
        "attempt": attempt,
        "max_attempts": MAX_ATTEMPTS,
        "recovery_candidate": blocker_kind not in NON_RECOVERABLE_KINDS,
        "decision": "pending",
        "decision_owner": "worker",
        "idempotency_key": f"{card_id}:{event_id}",
    }


def blocker_comment(event: dict[str, Any]) -> str:
    """Render the safe one-line comment contract without raw evidence."""
    event_id = _required_text("event_id", event.get("event_id"), single_line=True)
    blocker_kind = _required_text("blocker_kind", event.get("blocker_kind"), single_line=True)
    if blocker_kind not in BLOCKER_KINDS:
        raise ValueError("blocker_kind is unsupported")
    attempt = event.get("attempt")
    max_attempts = event.get("max_attempts")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 0:
        raise ValueError("attempt must be a non-negative integer")
    if max_attempts != MAX_ATTEMPTS:
        raise ValueError("max_attempts must equal 3")
    decision = _required_text("decision", event.get("decision"), single_line=True)
    owner = _required_text("decision_owner", event.get("decision_owner"), single_line=True)
    return (
        f"[ginflow-recovery] event={event_id} type=blocked kind={blocker_kind} "
        f"attempt={attempt}/{max_attempts} decision={decision} owner={owner} "
        f"reason=worker_reported_{blocker_kind}"
    )


__all__ = [
    "BLOCKER_KINDS",
    "MAX_ATTEMPTS",
    "NON_RECOVERABLE_KINDS",
    "blocker_comment",
    "build_blocker_event",
]
