"""Immutable routing for human Decision follow-up work."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

_ROUTES = {"implementation": "Execution", "correction": "Execution", "contract": "Shaping", "behavior": "Shaping", "acceptance": "Shaping", "dependency": "Shaping", "problem": "Discovery", "vocabulary": "Discovery", "goal": "Discovery", "boundary": "Discovery"}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def route_followup(request: Mapping[str, Any]) -> dict[str, Any]:
    """Route one bounded follow-up without reopening prior records."""
    if not isinstance(request, Mapping):
        raise ValueError("follow-up request must be a mapping")
    required = ("delta_class", "initiative_key", "review_key", "delta", "scope", "exclusions", "acceptance", "verification", "risk", "ticket_mapping")
    text_fields = {"delta_class", "initiative_key", "review_key", "delta", "risk"}
    missing = [field for field in required if field not in request or (field in text_fields and not _text(request[field])) or (field not in text_fields and (not isinstance(request[field], Sequence) or isinstance(request[field], (str, bytes))))]
    if missing:
        raise ValueError("follow-up packet missing: " + ", ".join(missing))
    route = _ROUTES.get(request["delta_class"])
    needs_mapping = route == "Execution"
    empty = [field for field in ("scope", "exclusions", "acceptance") + (("ticket_mapping",) if needs_mapping else ()) if not request[field]]
    if empty:
        raise ValueError("follow-up packet empty: " + ", ".join(empty))
    prior = request.get("prior_batch_attempt", 1)
    if not isinstance(prior, int) or isinstance(prior, bool) or prior < 1:
        raise ValueError("prior_batch_attempt must be a positive integer")
    if not route:
        raise ValueError("unsupported follow-up delta class")
    packet = deepcopy(dict(request))
    packet["schema"] = "execution_packet"
    packet["batch_attempt"] = prior + 1 if route == "Execution" else None
    packet["immutable"] = True
    return {"route": route, "packet": packet, "policy_proposals": []}


__all__ = ["route_followup"]
