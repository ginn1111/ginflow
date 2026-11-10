"""Build and render safe append-only worker blocker evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Mirrors hermes_cli.kanban_db (pinned by test); `dependency` never reaches recovery.
BLOCK_RECURRENCE_LIMIT = 2
BLOCKER_KINDS = frozenset({"transient", "needs_input", "capability"})
HUMAN_KINDS = frozenset({"needs_input", "capability"})
STATUSES = frozenset({"blocked", "triage"})


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


def _recurrences(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("recurrences must be a positive integer")
    return value


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
    recurrences: int = 1,
    status: str = "blocked",
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
    recurrences = _recurrences(recurrences)
    if status not in STATUSES:
        raise ValueError("status must be blocked or triage")
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
        "recurrences": recurrences,
        "limit": BLOCK_RECURRENCE_LIMIT,
        "status": status,
        "recovery_candidate": blocker_kind == "transient" and status == "blocked",
        "decision": "pending",
        "decision_owner": "worker",
        "idempotency_key": f"{card_id}:{event_id}",
    }


def blocker_comment(event: dict[str, Any], *, decision: str | None = None, reason: str | None = None) -> str:
    """Render the safe one-line comment contract without raw evidence."""
    event_id = _required_text("event_id", event.get("event_id"), single_line=True)
    blocker_kind = _required_text("blocker_kind", event.get("blocker_kind"), single_line=True)
    if blocker_kind not in BLOCKER_KINDS:
        raise ValueError("blocker_kind is unsupported")
    recurrences = _recurrences(event.get("recurrences"))
    if event.get("limit") != BLOCK_RECURRENCE_LIMIT:
        raise ValueError(f"limit must equal {BLOCK_RECURRENCE_LIMIT}")
    decision = _required_text("decision", decision or event.get("decision"), single_line=True)
    owner = _required_text("decision_owner", event.get("decision_owner"), single_line=True)
    reason = _required_text("reason", reason or f"worker_reported_{blocker_kind}", single_line=True)
    return (
        f"[ginflow-recovery] event={event_id} kind={blocker_kind} "
        f"recurrences={recurrences}/{BLOCK_RECURRENCE_LIMIT} decision={decision} owner={owner} "
        f"reason={reason}"
    )


__all__ = [
    "BLOCKER_KINDS",
    "BLOCK_RECURRENCE_LIMIT",
    "HUMAN_KINDS",
    "STATUSES",
    "blocker_comment",
    "build_blocker_event",
]
