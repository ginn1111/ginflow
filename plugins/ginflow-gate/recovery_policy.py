"""Pure, fail-closed bounded recovery decisions for blocked cards."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_ATTEMPTS = 3
RECOVERABLE_KINDS = frozenset({"transient", "unknown"})
NON_RECOVERABLE_KINDS = frozenset({"config_error", "persist_error", "human_input"})
TERMINAL_STATUSES = frozenset({"done", "cancelled", "archived"})
_REQUIRED_EVENT_FIELDS = (
    "event_id",
    "event_type",
    "card_id",
    "workspace",
    "previous_assignee",
    "blocker_kind",
    "attempt",
    "max_attempts",
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
    attempt: int
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
    attempt = event.get("attempt")
    return (
        isinstance(attempt, int)
        and not isinstance(attempt, bool)
        and attempt >= 0
        and event.get("max_attempts") == MAX_ATTEMPTS
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
    processed_keys: set[str] | frozenset[str] | None = None,
) -> RecoveryDecision:
    """Evaluate one event without mutating the event or card state."""
    if not _valid_event(event):
        return RecoveryDecision("stay_blocked", "malformed_safety_state", 0)

    key = event["idempotency_key"]
    attempt = event["attempt"]
    if key in (processed_keys or set()):
        return RecoveryDecision("skip", "already_processed", attempt, key)
    if event["card_id"] != current_card_id:
        return RecoveryDecision("stay_blocked", "card_mismatch", attempt, key)

    expected_workspace = str(Path(current_workspace).expanduser().resolve())
    event_workspace = str(Path(event["workspace"]).expanduser().resolve())
    if event_workspace != expected_workspace:
        return RecoveryDecision("stay_blocked", "workspace_mismatch", attempt, key)
    if current_status in TERMINAL_STATUSES:
        return RecoveryDecision("stay_blocked", "terminal_card", attempt, key)
    if current_status != "blocked":
        return RecoveryDecision("stay_blocked", "invalid_state", attempt, key)
    if not current_assignee:
        return RecoveryDecision("stay_blocked", "missing_worker", attempt, key)
    if current_assignee != event["previous_assignee"]:
        return RecoveryDecision("stay_blocked", "worker_mismatch", attempt, key)

    kind = event["blocker_kind"]
    expected_candidate = kind in RECOVERABLE_KINDS
    if kind not in RECOVERABLE_KINDS | NON_RECOVERABLE_KINDS:
        return RecoveryDecision("stay_blocked", "malformed_safety_state", attempt, key)
    if event["recovery_candidate"] is not expected_candidate:
        return RecoveryDecision("stay_blocked", "malformed_safety_state", attempt, key)
    if kind in NON_RECOVERABLE_KINDS:
        return RecoveryDecision("stay_blocked", kind, attempt, key)
    if attempt >= MAX_ATTEMPTS:
        return RecoveryDecision("notify_human", "retry_exhausted", attempt, key)

    return RecoveryDecision(
        "reassign",
        "recoverable_blocker",
        attempt + 1,
        key,
        event["previous_assignee"],
    )


__all__ = [
    "MAX_ATTEMPTS",
    "NON_RECOVERABLE_KINDS",
    "RECOVERABLE_KINDS",
    "RecoveryDecision",
    "TERMINAL_STATUSES",
    "evaluate_recovery",
]
