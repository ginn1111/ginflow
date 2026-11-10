from review_cycle import append_revision, validate_review


def review(**changes):
    value = {"schema": "review_cycle", "review_key": "APP-42/review-1", "initiative_key": "APP-42", "batch_key": "APP-42/run-1", "actor": {"id": "gin", "profile": "operator", "claim": "review:decide"}, "commits": {"baseline": "base", "result": "result", "target": "target"}, "ticket_outcomes": [{"key": "U", "state": "completed"}], "change_groups": [{"key": "CORE", "paths": ["core/a.py"], "tickets": ["U"]}], "evidence": [{"id": "ev", "kind": "verification"}], "findings": [], "deviations": [], "risks": [], "dispositions": [{"change_group": "CORE", "disposition": "accept"}], "aggregate_decision": "approved_for_mr", "revision": 1}
    value.update(changes)
    return value


def test_review_revision_is_append_only_and_digest_bound():
    result = append_revision(review(), actor=review()["actor"])
    assert result["revision"] == 1
    assert result["revision_digest"]
    assert validate_review(result)["valid"] is True
    try:
        append_revision(result, actor=review()["actor"])
    except ValueError as error:
        assert "append" in str(error)
    else:
        raise AssertionError("review revision overwritten")


def test_blocking_finding_and_accepted_risk_need_resolution_or_reason():
    for finding, expected in [({"producer": "scanner", "title": "issue", "severity": "high", "confidence": "verified", "state": "open", "paths": ["x"], "evidence_ids": ["ev"]}, "finding"), ({"producer": "scanner", "title": "issue", "severity": "medium", "confidence": "verified", "state": "accepted_risk", "paths": [], "evidence_ids": ["ev"]}, "reason")]:
        candidate = review(findings=[finding])
        result = validate_review(candidate)
        assert result["valid"] is False
        assert any(expected in error for error in result["errors"])


def test_finding_requires_producer_title_confidence_and_paths():
    result = validate_review(review(findings=[{"severity": "low", "state": "open", "evidence_ids": ["ev"]}]))
    assert result["valid"] is False
    assert any("finding" in error for error in result["errors"])


def test_verified_high_finding_with_resolution_can_approve():
    finding = {"producer": "scanner", "title": "issue", "severity": "high", "confidence": "verified", "state": "resolved", "paths": ["x"], "evidence_ids": ["ev"]}
    assert validate_review(review(findings=[finding]))["valid"] is True


def test_evidence_and_finding_references_are_structured():
    for changes, expected in [({"evidence": "ev"}, "evidence"), ({"findings": [{"severity": "low", "state": "open", "evidence_ids": "ev"}]}, "finding")]:
        result = validate_review(review(**changes))
        assert result["valid"] is False
        assert any(expected in error for error in result["errors"])


if __name__ == "__main__":
    test_review_revision_is_append_only_and_digest_bound()
    test_blocking_finding_and_accepted_risk_need_resolution_or_reason()
    test_finding_requires_producer_title_confidence_and_paths()
    test_verified_high_finding_with_resolution_can_approve()
    print("review cycle tests passed")
