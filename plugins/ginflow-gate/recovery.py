"""Fail-closed blocked-card recovery policy for gintary orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from threading import Lock
from time import monotonic
from typing import Any, Callable

MAX_ATTEMPTS = 3
MAX_NOTIFICATION_ATTEMPTS = 3
NON_RECOVERABLE = {"config_error", "persist_error", "human_input", "human-input"}
RECOVERABLE = {"transient", "worker_error", "interrupted"}
ACTIVE_STATUSES = {"blocked", "running", "ready", "todo", "in_progress"}


# ponytail: policy stays pure; gintary owns lease, append-only events, and mutation.


@dataclass
class PendingNotification:
    """Durable notification state; caller persists this dict append-only."""
    key: str
    card_id: str
    event_id: str
    message: str
    attempts: int = 0
    delivered: bool = False
    last_error: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {
            "notification_key": self.key,
            "card_id": self.card_id,
            "event_id": self.event_id,
            "message": self.message,
            "attempts": self.attempts,
            "delivered": self.delivered,
            "last_error": self.last_error,
        }


@dataclass(frozen=True)
class NotificationResult:
    delivered: bool
    pending: bool
    attempts: int
    reason: str


def queue_notification(*, card_id: str, event_id: str, message: str,
                       existing: dict[str, Any] | None = None) -> PendingNotification:
    """Create one idempotent pending report, or return existing state."""
    if existing and existing.get("notification_key") == notification_key(card_id, event_id):
        return PendingNotification(key=existing["notification_key"], card_id=card_id,
                                   event_id=event_id, message=existing.get("message", message),
                                   attempts=existing.get("attempts", 0),
                                   delivered=existing.get("delivered", False),
                                   last_error=existing.get("last_error"))
    return PendingNotification(notification_key(card_id, event_id), card_id, event_id, message)


def deliver_notification(notification: PendingNotification, sender: Callable[[str], None],
                         *, max_attempts: int = MAX_NOTIFICATION_ATTEMPTS) -> NotificationResult:
    """Attempt delivery once; retry policy is bounded across cron runs."""
    if notification.delivered:
        return NotificationResult(True, False, notification.attempts, "already_delivered")
    if notification.attempts >= max_attempts:
        return NotificationResult(False, True, notification.attempts, "delivery_exhausted")
    notification.attempts += 1
    try:
        sender(notification.message)
    except Exception as exc:  # sender boundary must not unblock card
        notification.last_error = str(exc)
        return NotificationResult(False, True, notification.attempts, "delivery_failed")
    notification.delivered = True
    notification.last_error = None
    return NotificationResult(True, False, notification.attempts, "delivered")


NON_RECOVERABLE = {"config_error", "persist_error", "human_input"}


@dataclass(frozen=True)
class RecoveryLease:
    key: str
    owner: str
    expires_at: float


class RecoveryLeaseStore:
    """Process-local atomic lease store; expired claims can be replaced safely."""

    def __init__(self, clock=monotonic):
        self._clock = clock
        self._leases: dict[str, RecoveryLease] = {}
        self._lock = Lock()

    def claim(self, key: str, owner: str, ttl: float) -> bool:
        if not key or not owner or ttl <= 0:
            return False
        now = self._clock()
        with self._lock:
            lease = self._leases.get(key)
            if lease and lease.expires_at > now and lease.owner != owner:
                return False
            self._leases[key] = RecoveryLease(key, owner, now + ttl)
            return True

    def release(self, key: str, owner: str) -> bool:
        with self._lock:
            lease = self._leases.get(key)
            if not lease or lease.owner != owner:
                return False
            del self._leases[key]
            return True

    def active(self, key: str) -> bool:
        with self._lock:
            lease = self._leases.get(key)
            return bool(lease and lease.expires_at > self._clock())


def blocker_event(*, card_id: str, workspace: str, previous_assignee: str,
                  blocker_kind: str, error: str, worker: str,
                  evidence: Any, event_id: str, timestamp: str | None = None,
                  attempted_commands: list[str] | None = None,
                  attempt: int = 0) -> dict[str, Any]:
    """Build one append-only blocker event; never mutates card state."""
    return {
        "card_id": card_id,
        "workspace": workspace,
        "previous_assignee": previous_assignee,
        "blocker_kind": blocker_kind,
        "error": error,
        "worker": worker,
        "evidence": evidence,
        "attempted_commands": attempted_commands or [],
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
        "attempt": attempt,
    }


def blocker_comment(event: dict[str, Any]) -> str:
    """Render durable, human-readable evidence without dropping fields."""
    return ("Blocked card evidence\n"
            f"- kind: {event.get('blocker_kind', 'unknown')}\n"
            f"- error: {event.get('error', '')}\n"
            f"- worker: {event.get('worker', '')}\n"
            f"- workspace: {event.get('workspace', '')}\n"
            f"- timestamp: {event.get('timestamp', '')}\n"
            f"- evidence: {json.dumps(event.get('evidence'), sort_keys=True)}")


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str
    attempt: int
    idempotency_key: str | None = None


def _valid(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    required = ("card_id", "workspace", "previous_assignee", "blocker_kind", "event_id")
    return all(isinstance(metadata.get(key), str) and metadata[key] for key in required)


def evaluate(metadata: dict[str, Any], *, current_workspace: str, current_assignee: str | None,
             status: str, seen_keys: set[str] | None = None) -> RecoveryDecision:
    """Evaluate one blocker. Never mutates Kanban; caller owns lease and mutation."""
    if not _valid(metadata):
        return RecoveryDecision("stay_blocked", "malformed_safety_state", 0)
    if metadata["workspace"] != current_workspace:
        return RecoveryDecision("stay_blocked", "workspace_mismatch", 0)
    if status not in ACTIVE_STATUSES:
        return RecoveryDecision("stay_blocked", "invalid_state", 0)
    if not current_assignee:
        return RecoveryDecision("stay_blocked", "missing_worker", 0)
    if current_assignee != metadata["previous_assignee"]:
        return RecoveryDecision("stay_blocked", "worker_mismatch", 0)
    key = f"{metadata['card_id']}:{metadata['event_id']}"
    if seen_keys and key in seen_keys:
        return RecoveryDecision("skip", "already_processed", 0, key)
    kind = metadata["blocker_kind"]
    attempt = metadata.get("attempt", 0)
    if not isinstance(attempt, int) or attempt < 0:
        return RecoveryDecision("stay_blocked", "malformed_safety_state", 0)
    if kind in NON_RECOVERABLE:
        return RecoveryDecision("stay_blocked", kind, attempt, key)
    if attempt >= MAX_ATTEMPTS:
        return RecoveryDecision("notify_human", "retry_exhausted", attempt, key)
    return RecoveryDecision("reassign", "recoverable_blocker", attempt + 1, key)


def notification_key(card_id: str, event_id: str) -> str:
    return f"telegram:{card_id}:{event_id}"


__all__ = [
    "MAX_ATTEMPTS", "MAX_NOTIFICATION_ATTEMPTS", "PendingNotification",
    "NotificationResult", "RecoveryDecision", "deliver_notification",
    "evaluate", "notification_key", "queue_notification",
]
