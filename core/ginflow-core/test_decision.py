from decision import build_notification, build_projection, decision_blocked, decision_ready


def evidence(**changes):
    value = {"id": "ev-1", "kind": "verification", "producer": "pytest", "commit": "result", "source": "make test", "result": "passed", "timestamp": "2026-10-09T12:00:00Z", "digest": "abc"}
    value.update(changes)
    return value


def base(**changes):
    value = {"initiative_key": "APP-42", "batch_key": "APP-42/run-1", "review_key": "APP-42/review-1", "baseline_commit": "base", "result_commit": "result", "target_commit": "target", "result_clean": True, "tickets": [{"key": "U", "state": "completed", "change_group": "CORE", "acceptance": ["A"], "paths": ["core/a.py"]}], "changed_paths": [{"path": "core/a.py", "change_group": "CORE"}], "evidence": [evidence()], "verification": {"commit": "result", "result": "passed"}, "findings": [], "claims": [{"text": "tests pass", "evidence_ids": ["ev-1"]}]}
    value.update(changes)
    return value


def test_successful_integration_opens_redacted_decision():
    assert decision_ready(base())["outcome"] == "decision_ready"
    projection = build_projection(base(), summary="safe summary")
    assert projection["schema"] == "decision_projection"
    assert projection["behavior_delta"][0]["path"] == "core/a.py"
    assert "raw_log" not in projection


def test_projection_redacts_sensitive_scalar_values_recursively():
    record = base(
        changed_paths=[{"path": "core/a.py", "change_group": "CORE", "note": "Bearer " + "x" * 12}],
        findings=[{"title": "safe title", "details": "pass" + "word=redactme", "paths": ["core/a.py"]}],
        verification={"commit": "result", "result": "passed", "log": "to" + "ken: redactme"},
    )
    projection = build_projection(record, summary="safe summary")
    assert projection["behavior_delta"][0]["note"] == "[REDACTED]"
    assert projection["risks_findings"][0]["details"] == "[REDACTED]"
    assert projection["verification"]["log"] == "[REDACTED]"


def test_projection_keeps_benign_text_mentioning_sensitive_words():
    record = base(changed_paths=[{"path": "core/a.py", "change_group": "CORE", "note": "Token expiry check uses < not <="}])
    assert build_projection(record, summary="safe summary")["behavior_delta"][0]["note"] == "Token expiry check uses < not <="

def test_projection_redacts_prefixed_keys_and_token_shapes():
    secrets = [
        *(f"{key}{sep}{'x' * 8}" for key, sep in (("access_token", "="), ("GITHUB_TOKEN", "="), ("db_password", ": "), ("client_secret", "="))),
        "gh" + "p_" + "a" * 24, "Authorization: Ba" + "sic " + "dXNlcjpwYXNz", "AK" + "IA" + "A" * 16,
    ]
    record = base(changed_paths=[{"path": "core/a.py", "change_group": "CORE", "note": text} for text in secrets])
    notes = [item["note"] for item in build_projection(record, summary="safe summary")["behavior_delta"]]
    assert notes == ["[REDACTED]"] * len(secrets), notes

def test_readiness_rejects_running_or_unassigned_paths():
    for changes, expected in [({"tickets": [{"key": "U", "state": "running", "change_group": "CORE", "acceptance": [], "paths": []}]}, "running"), ({"changed_paths": [{"path": "x", "change_group": None}]}, "unassigned")]:
        try:
            decision_ready(base(**changes))
        except ValueError as error:
            assert expected in str(error)
        else:
            raise AssertionError("unsafe decision accepted")


def blocked(**changes):
    value = base(
        tickets=[
            {"key": "U", "state": "completed", "change_group": "CORE", "acceptance": ["A"], "paths": ["core/a.py"]}
        ],
        blocker={"class": "retry_exhausted", "summary": "worker stopped", "evidence_ids": ["ev-1"]},
        attempted_recovery=[{"attempt": 1, "action": "reassign", "result": "failed"}],
        recovery_options=[{"id": "resume", "label": "resume execution"}],
    )
    value.update(changes)
    return value


def test_notification_has_idempotency_and_delivery_state():
    notification = build_notification(base(), message="review ready")
    assert notification["schema"] == "notification"
    assert notification["idempotency_key"] == "APP-42/run-1:APP-42/review-1:decision_ready"
    assert notification["delivery"] == {"attempts": 0, "acknowledged": False, "replay_key": notification["idempotency_key"]}


def test_blocked_integration_opens_recovery_decision():
    record = blocked()
    assert decision_blocked(record)["outcome"] == "decision_blocked"
    notification = build_notification(record, message="recovery required", outcome="decision_blocked")
    assert notification["outcome"] == "decision_blocked"
    assert notification["blocker_class"] == "retry_exhausted"
    projection = build_projection(record, summary="recovery summary")
    assert projection["recovery"]["options"][0]["id"] == "resume"


def test_success_notification_rejects_blocked_outcome():
    try:
        build_notification(base(), message="wrong outcome", outcome="decision_blocked")
    except ValueError as error:
        assert "outcome" in str(error)
    else:
        raise AssertionError("success record emitted blocked notification")


def test_malformed_ticket_fails_as_validation_error():
    try:
        decision_ready(base(tickets=["not a ticket"]))
    except ValueError as error:
        assert "ticket" in str(error)
    else:
        raise AssertionError("malformed ticket accepted")


def test_blocked_decision_rejects_mutable_or_missing_context():
    record = blocked()
    record["result_clean"] = False
    try:
        decision_blocked(record)
    except ValueError as error:
        assert "mutable" in str(error)
    else:
        raise AssertionError("mutable blocked result accepted")
    record = blocked()
    del record["recovery_options"]
    try:
        decision_blocked(record)
    except ValueError as error:
        assert "recovery" in str(error)
    else:
        raise AssertionError("blocked Decision without options accepted")
    record = blocked()
    record["blocker"]["evidence_ids"] = ["missing"]
    try:
        decision_blocked(record)
    except ValueError as error:
        assert "evidence" in str(error)
    else:
        raise AssertionError("unsupported blocker evidence accepted")
    record = blocked()
    record["attempted_recovery"] = [{"action": "reassign"}]
    try:
        decision_blocked(record)
    except ValueError as error:
        assert "recovery" in str(error)
    else:
        raise AssertionError("malformed recovery attempt accepted")


def test_blocked_notification_requires_blocker_context():
    record = base()
    try:
        build_notification(record, message="blocked", outcome="decision_blocked")
    except ValueError as error:
        assert "outcome" in str(error)
    else:
        raise AssertionError("ready record emitted blocked notification")


if __name__ == "__main__":
    test_successful_integration_opens_redacted_decision()
    test_projection_redacts_sensitive_scalar_values_recursively()
    test_projection_keeps_benign_text_mentioning_sensitive_words()
    test_projection_redacts_prefixed_keys_and_token_shapes()
    test_readiness_rejects_running_or_unassigned_paths()
    test_notification_has_idempotency_and_delivery_state()
    test_blocked_integration_opens_recovery_decision()
    test_success_notification_rejects_blocked_outcome()
    test_malformed_ticket_fails_as_validation_error()
    test_blocked_decision_rejects_mutable_or_missing_context()
    test_blocked_notification_requires_blocker_context()
    print("decision tests passed")
