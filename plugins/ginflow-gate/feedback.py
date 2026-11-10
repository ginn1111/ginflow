"""Pure, validated lifecycle feedback events for Governed Work.

This module normalizes existing lifecycle signals only. It does not persist,
notify, mutate Kanban state, or infer additional work.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

WORK_MODES = frozenset({"investigation", "implementation", "verification", "recovery"})
SIGNALS = frozenset(
    {
        "verification_passed",
        "verification_failed",
        "gate_rejected",
        "artifact_drift",
        "blocked",
        "recovered",
        "retry_exhausted",
        "human_corrected",
        "completed",
    }
)
RESULTS = frozenset({"passed", "failed", "blocked", "recovered", "corrected", "completed"})
SIGNAL_NEXT_ACTIONS = {
    "verification_passed": "none",
    "verification_failed": "investigate",
    "gate_rejected": "repair_artifacts",
    "artifact_drift": "stop_and_inspect",
    "blocked": "investigate",
    "recovered": "resume",
    "retry_exhausted": "notify_human",
    "human_corrected": "resume",
    "completed": "none",
}

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RFC3339_UTC = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_MAX_REASON_LENGTH = 500
_MAX_EVIDENCE_LENGTH = 500


def _safe_identifier(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be a safe non-empty identifier")
    return value


def _single_line(name: str, value: Any, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    result = value.strip()
    if len(result) > max_length or any(char in result for char in "\r\n"):
        raise ValueError(f"{name} must be a bounded single line")
    if any(ord(char) < 32 and char != "\t" for char in result):
        raise ValueError(f"{name} contains unsafe control characters")
    return result


def _timestamp(value: str | None) -> str:
    result = value or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    result = _single_line("occurred_at", result, max_length=40)
    if not _RFC3339_UTC.fullmatch(result):
        raise ValueError("occurred_at must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(result[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("occurred_at must be a valid RFC3339 UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError("occurred_at must be UTC")
    return result


def _evidence(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("evidence must be a non-empty list")
    return [_single_line("evidence item", item, max_length=_MAX_EVIDENCE_LENGTH) for item in value]


def build_feedback_event(
    *,
    event_id: str,
    task_id: str,
    work_mode: str,
    signal: str,
    result: str,
    reason: str,
    evidence: list[str],
    occurred_at: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    """Build one fresh Governed Work feedback event without side effects."""
    event_id = _safe_identifier("event_id", event_id)
    task_id = _safe_identifier("task_id", task_id)
    if task_id.startswith("direct-"):
        raise ValueError("task_id must identify Governed Work; Direct Work is outside feedback v1")
    if work_mode not in WORK_MODES:
        raise ValueError("work_mode is unsupported")
    if signal not in SIGNALS:
        raise ValueError("signal is unsupported")
    if result not in RESULTS:
        raise ValueError("result is unsupported")
    reason = _single_line("reason", reason, max_length=_MAX_REASON_LENGTH)
    safe_evidence = _evidence(evidence)
    expected_action = SIGNAL_NEXT_ACTIONS[signal]
    if next_action is not None and next_action != expected_action:
        raise ValueError("next_action does not match signal")

    return {
        "event_type": "work_feedback",
        "event_id": event_id,
        "task_id": task_id,
        "work_mode": work_mode,
        "signal": signal,
        "result": result,
        "reason": reason,
        "evidence": list(safe_evidence),
        "next_action": expected_action,
        "occurred_at": _timestamp(occurred_at),
    }


__all__ = [
    "RESULTS",
    "SIGNALS",
    "SIGNAL_NEXT_ACTIONS",
    "WORK_MODES",
    "build_feedback_event",
]
