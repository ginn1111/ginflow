#!/usr/bin/env python3
"""Focused bounded recovery policy tests."""
from copy import deepcopy
import importlib.util
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent
sys.path.insert(0, str(PLUGIN_DIR))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, PLUGIN_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reporting = load("blocker_reporting")
policy = load("recovery_policy")


def event(kind: str = "transient", attempt: int = 0):
    return reporting.build_blocker_event(
        event_id="evt-1",
        card_id="card-1",
        workspace="/tmp/project",
        previous_assignee="ginb",
        blocker_kind=kind,
        error_summary="safe summary",
        evidence=["test failed"],
        attempted_commands=["make test"],
        occurred_at="2026-08-16T10:00:00Z",
        attempt=attempt,
    )


def evaluate(candidate, **overrides):
    values = {
        "current_card_id": "card-1",
        "current_workspace": "/tmp/project",
        "current_assignee": "ginb",
        "current_status": "blocked",
    }
    values.update(overrides)
    return policy.evaluate_recovery(candidate, **values)


def main():
    for kind in ("transient", "unknown"):
        for attempt in range(3):
            candidate = event(kind, attempt)
            original = deepcopy(candidate)
            decision = evaluate(candidate)
            assert decision.action == "reassign"
            assert decision.attempt == attempt + 1
            assert decision.target_assignee == "ginb"
            assert candidate == original
        exhausted = evaluate(event(kind, 3))
        assert exhausted.action == "notify_human"
        assert exhausted.reason == "retry_exhausted"
        assert exhausted.attempt == 3
        assert exhausted.target_assignee is None

    for kind in ("config_error", "persist_error", "human_input"):
        decision = evaluate(event(kind))
        assert decision.action == "stay_blocked"
        assert decision.reason == kind

    base = event()
    duplicate = evaluate(base, processed_keys={base["idempotency_key"]})
    assert duplicate.action == "skip"
    assert duplicate.reason == "already_processed"
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
        {**base, "attempt": -1},
        {**base, "max_attempts": 4},
        {**base, "decision": "retry"},
        {**base, "idempotency_key": "wrong"},
        {**base, "blocker_kind": "worker_error"},
        {**base, "recovery_candidate": False},
    ]
    for malformed in malformed_cases:
        decision = evaluate(malformed)
        assert decision.action == "stay_blocked"
        assert decision.reason == "malformed_safety_state"

    print("bounded recovery policy passed")


if __name__ == "__main__":
    main()
