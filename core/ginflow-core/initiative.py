"""Provider-neutral Initiative lifecycle contract."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

PHASES = ("Discovery", "Shaping", "Execution", "Decision")
_TRANSITIONS = {
    "Discovery": {"Shaping"},
    "Shaping": {"Execution"},
    "Execution": {"Decision"},
    "Decision": set(),
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _utc(value: Any) -> bool:
    if not _text(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _errors(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("schema") != "initiative":
        errors.append("schema must be initiative")
    for field in ("initiative_key", "phase", "phase_state", "problem", "desired_outcome"):
        if not _text(record.get(field)):
            errors.append(f"{field} is required")
    if record.get("phase") not in PHASES:
        errors.append("phase is unsupported")
    actor = record.get("actor")
    if not isinstance(actor, Mapping) or not all(_text(actor.get(field)) for field in ("id", "profile", "claim")):
        errors.append("actor requires id, profile, and claim")
    for field in ("constraints", "non_goals", "vocabulary"):
        if not isinstance(record.get(field), (list, dict)):
            errors.append(f"{field} must be a collection")
    handoff = record.get("shaping_handoff")
    if not isinstance(handoff, Mapping) or not _text(handoff.get("objective")):
        errors.append("shaping_handoff.objective is required")
    prototype_evidence = record.get("prototype_evidence")
    if not isinstance(prototype_evidence, list):
        errors.append("prototype_evidence must be a list")
        prototype_evidence = []
    open_questions = record.get("open_questions")
    if not isinstance(open_questions, list):
        errors.append("open_questions must be a list")
        open_questions = []
    for item in open_questions:
        if not isinstance(item, Mapping) or not all(_text(item.get(key)) for key in ("question", "owner", "decision_point")):
            errors.append("open questions require question, owner, and decision_point")
    for item in prototype_evidence:
        if not isinstance(item, Mapping) or not _text(item.get("id")) or not _text(item.get("summary")):
            errors.append("prototype evidence requires id and summary")
        elif item.get("promoted") and not isinstance(item.get("promotion"), Mapping):
            errors.append("prototype promotion requires promotion coverage")
    return errors


def validate_initiative(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic validation result without mutating ``record``."""
    if not isinstance(record, Mapping):
        return {"valid": False, "errors": ["initiative must be a mapping"]}
    errors = _errors(record)
    return {"valid": not errors, "errors": errors}


def approve_discovery(record: Mapping[str, Any], approved_at: str | None = None) -> dict[str, Any]:
    """Approve Discovery and create the durable Shaping handoff."""
    candidate = deepcopy(dict(record))
    result = validate_initiative(candidate)
    if not result["valid"]:
        raise ValueError("invalid initiative: " + "; ".join(result["errors"]))
    if candidate.get("phase") != "Discovery" or candidate.get("phase_state") != "draft":
        raise ValueError("Discovery must be draft before approval")
    timestamp = approved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not _utc(timestamp):
        raise ValueError("approved_at must include timezone")
    actor = candidate["actor"]
    candidate["approval"] = {"actor_id": actor["id"], "claim": actor["claim"], "approved_at": timestamp}
    candidate["shaping_handoff"] = {**candidate["shaping_handoff"], "approved": True}
    candidate["phase"] = "Shaping"
    candidate["phase_state"] = "ready"
    return candidate


def transition(record: Mapping[str, Any], phase: str, *, phase_state: str = "ready") -> dict[str, Any]:
    """Move a valid Initiative through canonical phases, returning a fresh record."""
    if not isinstance(record, Mapping):
        raise ValueError("initiative must be a mapping")
    validation = validate_initiative(record)
    if not validation["valid"]:
        raise ValueError("invalid initiative: " + "; ".join(validation["errors"]))
    if phase not in PHASES or phase not in _TRANSITIONS.get(record.get("phase"), set()):
        raise ValueError(f"invalid initiative transition: {record.get('phase')} -> {phase}")
    if not _text(phase_state):
        raise ValueError("phase_state is required")
    candidate = deepcopy(dict(record))
    candidate["phase"] = phase
    candidate["phase_state"] = phase_state
    return candidate


__all__ = ["PHASES", "approve_discovery", "transition", "validate_initiative"]
