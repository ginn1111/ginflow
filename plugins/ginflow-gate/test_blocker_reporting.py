#!/usr/bin/env python3
"""Focused blocker-reporting contract tests."""
import importlib.util
import sys
from pathlib import Path

MODULE = Path(__file__).with_name("blocker_reporting.py")
spec = importlib.util.spec_from_file_location("blocker_reporting", MODULE)
assert spec and spec.loader
reporting = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reporting
spec.loader.exec_module(reporting)


def event(kind: str = "transient"):
    return reporting.build_blocker_event(
        event_id="evt-1",
        card_id="card-1",
        workspace="/tmp/../tmp/project",
        previous_assignee="ginb",
        blocker_kind=kind,
        error_summary="safe failure summary",
        evidence=["make test exited 2"],
        attempted_commands=["make test"],
        occurred_at="2026-08-16T10:00:00Z",
    )


def expect_value_error(**overrides):
    values = {
        "event_id": "evt-1",
        "card_id": "card-1",
        "workspace": "/tmp/project",
        "previous_assignee": "ginb",
        "blocker_kind": "transient",
        "error_summary": "safe summary",
        "evidence": ["evidence"],
        "attempted_commands": ["make test"],
        "occurred_at": "2026-08-16T10:00:00Z",
    }
    values.update(overrides)
    try:
        reporting.build_blocker_event(**values)
    except ValueError:
        return
    raise AssertionError(f"expected ValueError for {overrides}")


def main():
    transient = event()
    required = {
        "event_id", "event_type", "card_id", "workspace", "previous_assignee",
        "blocker_kind", "error_summary", "evidence", "attempted_commands",
        "occurred_at", "attempt", "max_attempts", "recovery_candidate",
        "decision", "decision_owner", "idempotency_key",
    }
    assert set(transient) == required
    assert transient["workspace"] == str(Path("/tmp/project").resolve())
    assert transient["recovery_candidate"] is True
    assert event("unknown")["recovery_candidate"] is True
    for kind in ("config_error", "persist_error", "human_input"):
        assert event(kind)["recovery_candidate"] is False

    comment = reporting.blocker_comment(transient)
    assert comment == (
        "[ginflow-recovery] event=evt-1 type=blocked kind=transient "
        "attempt=0/3 decision=pending owner=worker reason=worker_reported_transient"
    )
    for unsafe in ("safe failure summary", "make test exited 2", "make test"):
        assert unsafe not in comment

    expect_value_error(blocker_kind="other")
    expect_value_error(error_summary="two\nlines")
    expect_value_error(evidence=[])
    expect_value_error(attempt=-1)
    expect_value_error(occurred_at="2026-08-16T10:00:00+00:00")
    print("blocker reporting contract passed")


if __name__ == "__main__":
    main()
