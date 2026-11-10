#!/usr/bin/env python3
"""Tests for the pure Ginflow feedback event contract."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugins/ginflow-gate/feedback.py"
spec = importlib.util.spec_from_file_location("ginflow_feedback", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

build_feedback_event = module.build_feedback_event


def valid_kwargs():
    return {
        "event_id": "evt-1",
        "task_id": "t_abc123",
        "work_mode": "implementation",
        "signal": "verification_failed",
        "result": "blocked",
        "reason": "focused verification failed",
        "evidence": ["test-output:failure-1"],
        "occurred_at": "2026-08-22T10:00:00Z",
    }


def expect_value_error(**changes):
    values = valid_kwargs()
    values.update(changes)
    try:
        build_feedback_event(**values)
    except ValueError:
        return
    raise AssertionError(f"expected ValueError for {changes}")


def test_valid_event_is_normalized_and_pure():
    values = valid_kwargs()
    original = values.copy()
    event = build_feedback_event(**values)
    assert event == {
        "event_type": "work_feedback",
        "event_id": "evt-1",
        "task_id": "t_abc123",
        "work_mode": "implementation",
        "signal": "verification_failed",
        "result": "blocked",
        "reason": "focused verification failed",
        "evidence": ["test-output:failure-1"],
        "next_action": "investigate",
        "occurred_at": "2026-08-22T10:00:00Z",
    }
    assert values == original
    event["evidence"].append("local-only")
    assert values["evidence"] == ["test-output:failure-1"]


def test_rejects_invalid_fields():
    expect_value_error(signal="not-supported")
    expect_value_error(task_id="../outside")
    expect_value_error(event_id="")
    expect_value_error(reason="line one\nline two")
    expect_value_error(work_mode="direct-no-card")
    expect_value_error(result="unknown-result")
    expect_value_error(occurred_at="2026-08-22T10:00:00+00:00")
    expect_value_error(occurred_at="2026-08-22T10:00:00Z\nunsafe")
    expect_value_error(evidence=["safe", "bad\nreference"])


def test_signal_next_action_mapping():
    expected = {
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
    for signal, next_action in expected.items():
        values = valid_kwargs()
        values["signal"] = signal
        event = build_feedback_event(**values)
        assert event["next_action"] == next_action, signal


if __name__ == "__main__":
    test_valid_event_is_normalized_and_pure()
    test_rejects_invalid_fields()
    test_signal_next_action_mapping()
    print("feedback contract tests passed")
