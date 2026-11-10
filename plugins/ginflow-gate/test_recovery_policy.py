#!/usr/bin/env python3
"""Focused recovery policy tests."""
from copy import deepcopy
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load(name: str):
    return importlib.import_module(f"ginflow-gate.{name}")


reporting = load("blocker_reporting")
policy = load("recovery_policy")


def event(kind: str = "transient", status: str = "blocked", recurrences: int = 1):
    return reporting.build_blocker_event(
        event_id="7:1",
        card_id="card-1",
        workspace="/tmp/project",
        previous_assignee="ginb",
        blocker_kind=kind,
        error_summary="safe summary",
        evidence=["test failed"],
        attempted_commands=["make test"],
        occurred_at="2026-08-16T10:00:00Z",
        recurrences=recurrences,
        status=status,
    )


def evaluate(candidate, **overrides):
    values = {
        "current_card_id": "card-1",
        "current_workspace": "/tmp/project",
        "current_assignee": "ginb",
        "current_status": "blocked",
        "reviewer": "repairer",
    }
    values.update(overrides)
    return policy.evaluate_recovery(candidate, **values)


def main():
    first = event()
    original = deepcopy(first)
    d = evaluate(first)
    assert (d.action, d.target_assignee, d.recurrences) == ("reassign", "repairer", 1)
    assert first == original

    d = evaluate(event(status="triage", recurrences=2), current_status="triage")
    assert (d.action, d.reason, d.target_assignee) == ("notify_human", "retry_exhausted", None)
    d = evaluate(first, reviewer=None)
    assert (d.action, d.reason) == ("notify_human", "no_reviewer")

    for kind in ("needs_input", "capability"):
        for status in ("blocked", "triage"):
            d = evaluate(event(kind, status), current_status=status)
            assert (d.action, d.reason) == ("notify_human", kind)

    base = event()
    duplicate = evaluate(base, processed_keys={base["idempotency_key"]})
    assert (duplicate.action, duplicate.reason) == ("skip", "already_processed")
    assert evaluate(base, current_card_id="other").reason == "card_mismatch"
    assert evaluate(base, current_workspace="/tmp/other").reason == "workspace_mismatch"
    assert evaluate(base, current_assignee=None).reason == "missing_worker"
    assert evaluate(base, current_assignee="other").reason == "worker_mismatch"
    assert evaluate(base, current_status="ready").reason == "invalid_state"
    for status in ("done", "cancelled", "archived"):
        assert evaluate(base, current_status=status).reason == "terminal_card"

    malformed_cases = [
        {},
        {**base, "event_type": "other"},
        {**base, "recurrences": 0},
        {**base, "limit": 3},
        {**base, "status": "ready"},
        {**base, "decision": "retry"},
        {**base, "idempotency_key": "wrong"},
        {**base, "blocker_kind": "worker_error"},
        {**base, "recovery_candidate": False},
    ]
    for malformed in malformed_cases:
        d = evaluate(malformed)
        assert (d.action, d.reason) == ("stay_blocked", "malformed_safety_state")

    print("recovery policy passed")


if __name__ == "__main__":
    main()
