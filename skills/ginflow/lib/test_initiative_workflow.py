"""End-to-end four-phase Initiative contract seam."""
from decision import build_notification, decision_blocked, decision_ready
from execution_batch import authorize_batch, create_batch
from execution_package import approve_package
from initiative import approve_discovery, transition
from merge_request import build_mr_intent
from review_cycle import append_revision

from test_execution_batch import package as batch_package
from test_initiative import discovery


def package():
    value = batch_package()
    value["contract"]["approval"] = {"approver": "gin", "approved_at": "2026-10-09T00:00:00Z"}
    return value


def integration_record(**changes):
    value = {
        "initiative_key": "APP-42",
        "batch_key": "APP-42/run-1",
        "review_key": "APP-42/review-1",
        "baseline_commit": "base",
        "result_commit": "result",
        "target_commit": "target",
        "result_clean": True,
        "tickets": [{"key": "U", "state": "completed"}],
        "changed_paths": [{"path": "core/a.py", "change_group": "CORE"}],
        "verification": {"commit": "result", "result": "passed"},
        "evidence": [{
            "id": "ev-1", "kind": "verification", "producer": "pytest", "commit": "result",
            "source": "make test", "result": "passed", "timestamp": "2026-10-09T12:00:00Z", "digest": "abc",
        }],
        "claims": [{"text": "tests pass", "evidence_ids": ["ev-1"]}],
    }
    value.update(changes)
    return value


def review():
    return {
        "schema": "review_cycle",
        "review_key": "APP-42/review-1",
        "initiative_key": "APP-42",
        "batch_key": "APP-42/run-1",
        "actor": {"id": "gin", "profile": "operator", "claim": "review:decide"},
        "commits": {"baseline": "base", "result": "result", "target": "target"},
        "ticket_outcomes": [{"key": "U", "state": "completed"}],
        "change_groups": [{"key": "CORE", "paths": ["core/a.py"], "tickets": ["U"]}],
        "evidence": [{"id": "ev-1", "kind": "verification"}],
        "findings": [],
        "deviations": [],
        "risks": [],
        "dispositions": [{"change_group": "CORE", "disposition": "accept"}],
        "aggregate_decision": "approved_for_mr",
        "revision": 1,
    }


def test_successful_initiative_reaches_approved_mr_intent():
    shaped = approve_discovery(discovery(), approved_at="2026-10-09T12:00:00Z")
    shaped = transition(shaped, "Execution")
    approved = approve_package(package(), "gin", approved_at="2026-10-09T12:00:00Z")
    batch = authorize_batch(
        approved,
        actor={"id": "gin", "profile": "operator", "claim": "execution:authorize"},
        budget={"max_turns": 10}, stop_conditions=["verification failure"],
        workspaces=["/repo/u"], baseline_commit="base",
    )
    calls = []
    created = create_batch(
        approved,
        actor={"id": "gin", "profile": "operator", "claim": "execution:authorize"},
        budget={"max_turns": 10}, stop_conditions=["verification failure"],
        workspaces=["/repo/u"], baseline_commit="base",
        create_card=lambda args: calls.append(args) or {"id": str(len(calls))},
    )
    assert shaped["phase"] == "Execution"
    assert batch["batch_key"] == "APP-42/run-1"
    assert created["cards"]["integration_card"]["id"] == "2"
    assert calls[0]["initial_status"] == "blocked"
    assert calls[0]["metadata"]["batch_key"] == batch["batch_key"]
    assert decision_ready(integration_record())["outcome"] == "decision_ready"
    revision = append_revision(review(), actor=review()["actor"])
    intent = build_mr_intent({
        "initiative_key": "APP-42", "review_key": "APP-42/review-1", "revision_digest": revision["revision_digest"],
        "source_ref": "refs/heads/feature", "source_commit": "result", "target_ref": "refs/heads/main", "target_commit": "target",
        "merge_evidence": {"commit": "result", "target": "target", "conflicts": False},
        "verification": {"commit": "result", "result": "passed"}, "changed_paths_covered": True,
        "blocking_findings": 0, "high_findings": 0, "dirty": False, "secret_exposure": False,
    }, title="Ship context recovery", body="Summary")
    assert intent["publication_status"] == "not_published"


def test_blocked_execution_reaches_recovery_decision():
    record = integration_record(
        blocker={"class": "retry_exhausted", "summary": "worker stopped", "evidence_ids": ["ev-1"]},
        attempted_recovery=[{"attempt": 1, "action": "reassign", "result": "failed"}],
        recovery_options=[{"id": "resume", "label": "resume execution"}],
    )
    assert decision_blocked(record)["outcome"] == "decision_blocked"
    assert build_notification(record, message="recovery required", outcome="decision_blocked")["outcome"] == "decision_blocked"


if __name__ == "__main__":
    test_successful_initiative_reaches_approved_mr_intent()
    test_blocked_execution_reaches_recovery_decision()
    print("initiative workflow tests passed")
