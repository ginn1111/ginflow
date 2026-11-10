"""Deterministic Decision readiness, projection, and notification contracts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Any

_SECRET = re.compile(r"(secret|token|cookie|prompt|transcript|raw_log|session_storage)", re.I)
_SENSITIVE_VALUE = re.compile(
    r"(secret|token|cookie|password|passwd|api[_-]?key|session_storage)\s*[=:]\s*\S"
    r"|(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|(?:sk|pk)[_-][A-Za-z0-9_-]{12,}"
    r"|\bgh[pousr]_[A-Za-z0-9]{20,}"
    r"|\bAKIA[0-9A-Z]{16}\b",
    re.I,
)
_REDACTED = "[REDACTED]"


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _required(record: Mapping[str, Any], fields: Sequence[str]) -> None:
    missing = [field for field in fields if not _text(record.get(field))]
    if missing:
        raise ValueError("missing provenance: " + ", ".join(missing))


def _validate_evidence(record: Mapping[str, Any]) -> None:
    evidence = record.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)) or not evidence:
        raise ValueError("evidence is required")
    ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, Mapping) or not all(_text(item.get(field)) for field in ("id", "kind", "producer", "commit", "source", "result", "timestamp", "digest")):
            raise ValueError("evidence has incomplete provenance")
        if item["id"] in ids:
            raise ValueError("duplicate evidence id")
        ids.add(item["id"])
    claims = record.get("claims", [])
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        raise ValueError("claims must be a list")
    for claim in claims:
        refs = claim.get("evidence_ids") if isinstance(claim, Mapping) else None
        if not isinstance(claim, Mapping) or not _text(claim.get("text")) or not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs or any(not _text(ref) for ref in refs) or not set(refs).issubset(ids):
            raise ValueError("unsupported claim must reference evidence")


def _validate_terminal_tickets(tickets: Any) -> list[Mapping[str, Any]]:
    if not isinstance(tickets, Sequence) or isinstance(tickets, (str, bytes)) or not tickets:
        raise ValueError("tickets are required")
    result: list[Mapping[str, Any]] = []
    for ticket in tickets:
        if not isinstance(ticket, Mapping):
            raise ValueError("ticket must be a mapping")
        if ticket.get("state") not in {"completed", "failed", "blocked"}:
            raise ValueError("running ticket blocks Decision")
        result.append(ticket)
    return result


def _validate_changed_paths(paths: Any) -> list[Mapping[str, Any]]:
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)) or not paths:
        raise ValueError("changed paths are required")
    result: list[Mapping[str, Any]] = []
    for path in paths:
        if not isinstance(path, Mapping) or not _text(path.get("path")) or not _text(path.get("change_group")):
            raise ValueError("unassigned changed path blocks Decision")
        result.append(path)
    return result


def _validate_blocked(record: Mapping[str, Any]) -> None:
    blocker = record.get("blocker")
    options = record.get("recovery_options")
    evidence_ids = {item["id"] for item in record["evidence"]}
    blocker_refs = blocker.get("evidence_ids") if isinstance(blocker, Mapping) else None
    if not isinstance(blocker, Mapping) or not _text(blocker.get("class")) or not _text(blocker.get("summary")):
        raise ValueError("blocked Decision requires blocker context")
    if not isinstance(blocker_refs, Sequence) or isinstance(blocker_refs, (str, bytes)) or not blocker_refs or not set(blocker_refs).issubset(evidence_ids):
        raise ValueError("blocked Decision blocker must reference evidence")
    if not isinstance(options, Sequence) or isinstance(options, (str, bytes)) or not options:
        raise ValueError("blocked Decision requires recovery options")
    for option in options:
        if not isinstance(option, Mapping) or not _text(option.get("id")) or not _text(option.get("label")):
            raise ValueError("recovery option is malformed")
    attempts = record.get("attempted_recovery")
    if not isinstance(attempts, Sequence) or isinstance(attempts, (str, bytes)):
        raise ValueError("attempted recovery must be a list")
    for attempt in attempts:
        if not isinstance(attempt, Mapping) or not _text(attempt.get("action")) or not _text(attempt.get("result")):
            raise ValueError("attempted recovery is malformed")


def decision_ready(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate terminal Integration output and return material readiness."""
    if not isinstance(record, Mapping):
        raise ValueError("decision record must be a mapping")
    _required(record, ("initiative_key", "batch_key", "review_key", "baseline_commit", "result_commit", "target_commit"))
    if record.get("result_clean") is not True:
        raise ValueError("mutable result state blocks Decision")
    if record["baseline_commit"] == record["result_commit"]:
        raise ValueError("result commit must differ from baseline")
    _validate_terminal_tickets(record.get("tickets"))
    _validate_changed_paths(record.get("changed_paths"))
    verification = record.get("verification")
    if not isinstance(verification, Mapping) or verification.get("commit") != record["result_commit"]:
        raise ValueError("verification must bind result commit")
    _validate_evidence(record)
    if "blocker" in record:
        raise ValueError("blocked Integration requires decision_blocked")
    return {"outcome": "decision_ready", "initiative_key": record["initiative_key"], "batch_key": record["batch_key"], "review_key": record["review_key"], "result_commit": record["result_commit"]}


def _safe_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _safe_projection(item)
            for key, item in value.items()
            if not _SECRET.search(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [_safe_projection(item) for item in value]
    if isinstance(value, str) and _SENSITIVE_VALUE.search(value):
        return _REDACTED
    return value


def _notification_context(record: Mapping[str, Any]) -> tuple[str, str]:
    if "blocker" in record:
        blocker = record["blocker"]
        if not isinstance(blocker, Mapping) or not _text(blocker.get("class")):
            raise ValueError("blocked Decision requires blocker context")
        return "decision_blocked", blocker["class"]
    return "decision_ready", ""


def build_projection(record: Mapping[str, Any], *, summary: str) -> dict[str, Any]:
    """Build bounded redacted projection ordered for progressive disclosure."""
    if "blocker" in record:
        decision_blocked(record)
    else:
        decision_ready(record)
    if not _text(summary) or len(summary) > 1000:
        raise ValueError("summary must be bounded")
    projection = {
        "schema": "decision_projection",
        "decision_required": "human disposition required",
        "executive_context": {"initiative_key": record["initiative_key"], "summary": summary},
        "behavior_delta": deepcopy(list(record["changed_paths"])),
        "change_groups": sorted({path["change_group"] for path in record["changed_paths"]}),
        "ticket_coverage": deepcopy(list(record["tickets"])),
        "verification": deepcopy(dict(record["verification"])),
        "risks_findings": deepcopy(list(record.get("findings", []))),
        "choices": ["accept", "enhance", "reject", "defer"],
        "exact_commits": {key: record[key] for key in ("baseline_commit", "result_commit", "target_commit")},
    }
    if "blocker" in record:
        projection["recovery"] = {
            "blocker": deepcopy(record["blocker"]),
            "attempted_recovery": deepcopy(list(record.get("attempted_recovery", []))),
            "options": deepcopy(list(record["recovery_options"])),
        }
    result = _safe_projection(projection)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if len(encoded) > 10000:
        raise ValueError("decision projection exceeds bound")
    return result


def decision_blocked(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate blocked Integration output and return material recovery readiness."""
    if not isinstance(record, Mapping):
        raise ValueError("decision record must be a mapping")
    candidate = dict(record)
    candidate["outcome"] = "decision_blocked"
    _required(candidate, ("initiative_key", "batch_key", "review_key", "baseline_commit", "result_commit", "target_commit"))
    if candidate.get("result_clean") is not True:
        raise ValueError("mutable result state blocks Decision")
    _validate_terminal_tickets(candidate.get("tickets"))
    _validate_changed_paths(candidate.get("changed_paths"))
    verification = candidate.get("verification")
    if not isinstance(verification, Mapping) or verification.get("commit") != candidate["result_commit"]:
        raise ValueError("verification must bind result commit")
    _validate_evidence(candidate)
    _validate_blocked(candidate)
    return {"outcome": "decision_blocked", "initiative_key": candidate["initiative_key"], "batch_key": candidate["batch_key"], "review_key": candidate["review_key"], "result_commit": candidate["result_commit"], "blocker_class": candidate["blocker"]["class"]}


def _decision_context(record: Mapping[str, Any]) -> tuple[str, str]:
    """Validate either terminal Decision outcome and return outcome plus blocker class."""
    if "blocker" in record:
        result = decision_blocked(record)
        return result["outcome"], result["blocker_class"]
    result = decision_ready(record)
    return result["outcome"], ""


def build_notification(record: Mapping[str, Any], *, message: str, outcome: str = "decision_ready") -> dict[str, Any]:
    """Build gateway-ready envelope; transport and retries remain adapter-owned."""
    actual_outcome, blocker_class = _decision_context(record)
    if outcome != actual_outcome or not _text(message) or len(message) > 500:
        raise ValueError("invalid notification outcome or message")
    key = f"{record['batch_key']}:{record['review_key']}:{outcome}"
    result = {
        "schema": "notification",
        "event_id": sha256(key.encode()).hexdigest(),
        "initiative_key": record["initiative_key"],
        "batch_key": record["batch_key"],
        "review_key": record["review_key"],
        "outcome": outcome,
        "result_commit": record["result_commit"],
        "message": message,
        "query_key": f"decision:{record['review_key']}",
        "idempotency_key": key,
        "delivery": {"attempts": 0, "acknowledged": False, "replay_key": key},
    }
    if blocker_class:
        result["blocker_class"] = blocker_class
    return result


__all__ = ["build_notification", "build_projection", "decision_blocked", "decision_ready"]
