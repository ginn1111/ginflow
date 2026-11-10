#!/usr/bin/env python3
"""Focused blocker-reporting contract tests."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins"))
reporting = importlib.import_module("ginflow-gate.blocker_reporting")


def event(kind: str = "transient", **kw):
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
        **kw,
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
    assert reporting.BLOCKER_KINDS == {"transient", "needs_input", "capability"}
    assert reporting.BLOCK_RECURRENCE_LIMIT == 2
    assert not hasattr(reporting, "MAX_ATTEMPTS")
    try:
        from hermes_cli import kanban_db
    except Exception:
        kanban_db = None
    if kanban_db:
        assert reporting.BLOCK_RECURRENCE_LIMIT == kanban_db.BLOCK_RECURRENCE_LIMIT
        assert reporting.BLOCKER_KINDS | {"dependency"} == set(kanban_db.VALID_BLOCK_KINDS)

    transient = event()
    required = {
        "event_id", "event_type", "card_id", "workspace", "previous_assignee",
        "blocker_kind", "error_summary", "evidence", "attempted_commands",
        "occurred_at", "recurrences", "limit", "status", "recovery_candidate",
        "decision", "decision_owner", "idempotency_key",
    }
    assert set(transient) == required
    assert transient["workspace"] == str(Path("/tmp/project").resolve())
    assert transient["recovery_candidate"] is True
    assert event("transient", status="triage")["recovery_candidate"] is False
    for kind in ("needs_input", "capability"):
        assert event(kind)["recovery_candidate"] is False

    comment = reporting.blocker_comment(transient)
    assert comment == (
        "[ginflow-recovery] event=evt-1 kind=transient "
        "recurrences=1/2 decision=pending owner=worker reason=worker_reported_transient"
    )
    for unsafe in ("safe failure summary", "make test exited 2", "make test"):
        assert unsafe not in comment
    assert "decision=reassign" in reporting.blocker_comment(transient, decision="reassign")

    for kind in ("other", "unknown", "config_error", "persist_error", "human_input", "dependency"):
        expect_value_error(blocker_kind=kind)
    expect_value_error(error_summary="two\nlines")
    expect_value_error(evidence=[])
    expect_value_error(recurrences=0)
    expect_value_error(status="ready")
    expect_value_error(occurred_at="2026-08-16T10:00:00+00:00")
    print("blocker reporting contract passed")


if __name__ == "__main__":
    main()
