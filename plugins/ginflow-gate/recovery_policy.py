"""Pure, fail-closed recovery decisions for blocked cards on Hermes block state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .blocker_reporting import BLOCK_RECURRENCE_LIMIT, BLOCKER_KINDS, HUMAN_KINDS, STATUSES

TERMINAL_STATUSES = frozenset({"done", "cancelled", "archived"})
_REQUIRED_EVENT_FIELDS = (
    "event_id",
    "event_type",
    "card_id",
    "workspace",
    "previous_assignee",
    "blocker_kind",
    "recurrences",
    "limit",
    "status",
    "recovery_candidate",
    "decision",
    "decision_owner",
    "idempotency_key",
)


@dataclass(frozen=True)
class RecoveryDecision:
    """A decision for an orchestrator to persist and apply separately."""

    action: str
    reason: str
    recurrences: int
    idempotency_key: str | None = None
    target_assignee: str | None = None


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_event(event: Any) -> bool:
    if not isinstance(event, dict) or not all(field in event for field in _REQUIRED_EVENT_FIELDS):
        return False
    text_fields = (
        "event_id", "event_type", "card_id", "workspace", "previous_assignee",
        "blocker_kind", "decision", "decision_owner", "idempotency_key",
    )
    if not all(_text(event.get(field)) for field in text_fields):
        return False
    recurrences = event.get("recurrences")
    return (
        isinstance(recurrences, int)
        and not isinstance(recurrences, bool)
        and recurrences >= 1
        and event.get("limit") == BLOCK_RECURRENCE_LIMIT
        and event.get("status") in STATUSES
        and isinstance(event.get("recovery_candidate"), bool)
        and event.get("event_type") == "blocked"
        and event.get("decision") == "pending"
        and event.get("decision_owner") == "worker"
        and event.get("idempotency_key") == f"{event['card_id']}:{event['event_id']}"
    )


def evaluate_recovery(
    event: dict[str, Any],
    *,
    current_card_id: str,
    current_workspace: str,
    current_assignee: str | None,
    current_status: str,
    reviewer: str | None = None,
    processed_keys: set[str] | frozenset[str] | None = None,
) -> RecoveryDecision:
    """Evaluate one event without mutating the event or card state."""
    if not _valid_event(event):
        return RecoveryDecision("stay_blocked", "malformed_safety_state", 0)

    key = event["idempotency_key"]
    n = event["recurrences"]
    if key in (processed_keys or set()):
        return RecoveryDecision("skip", "already_processed", n, key)
    if event["card_id"] != current_card_id:
        return RecoveryDecision("stay_blocked", "card_mismatch", n, key)

    expected_workspace = str(Path(current_workspace).expanduser().resolve())
    event_workspace = str(Path(event["workspace"]).expanduser().resolve())
    if event_workspace != expected_workspace:
        return RecoveryDecision("stay_blocked", "workspace_mismatch", n, key)
    if current_status in TERMINAL_STATUSES:
        return RecoveryDecision("stay_blocked", "terminal_card", n, key)
    if current_status not in STATUSES:
        return RecoveryDecision("stay_blocked", "invalid_state", n, key)
    if not current_assignee:
        return RecoveryDecision("stay_blocked", "missing_worker", n, key)
    if current_assignee != event["previous_assignee"]:
        return RecoveryDecision("stay_blocked", "worker_mismatch", n, key)

    kind = event["blocker_kind"]
    if kind not in BLOCKER_KINDS or event["recovery_candidate"] is not (
        kind == "transient" and event["status"] == "blocked"
    ):
        return RecoveryDecision("stay_blocked", "malformed_safety_state", n, key)
    if kind in HUMAN_KINDS:
        return RecoveryDecision("notify_human", kind, n, key)
    if current_status == "triage":
        return RecoveryDecision("notify_human", "retry_exhausted", n, key)
    if not reviewer:
        return RecoveryDecision("notify_human", "no_reviewer", n, key)
    return RecoveryDecision("reassign", "recoverable_blocker", n, key, reviewer)


__all__ = [
    "RecoveryDecision",
    "TERMINAL_STATUSES",
    "evaluate_recovery",
]
