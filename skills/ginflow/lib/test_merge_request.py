from merge_request import build_mr_intent


def review(**changes):
    value = {"initiative_key": "APP-42", "review_key": "APP-42/review-1", "revision_digest": "digest", "source_ref": "refs/heads/feature", "source_commit": "result", "target_ref": "refs/heads/main", "target_commit": "target", "merge_evidence": {"commit": "result", "target": "target", "conflicts": False}, "verification": {"commit": "result", "result": "passed"}, "changed_paths_covered": True, "blocking_findings": 0, "high_findings": 0, "dirty": False, "secret_exposure": False}
    value.update(changes)
    return value


def test_approved_review_creates_provider_neutral_intent():
    intent = build_mr_intent(review(), title="Ship context recovery", body="Summary")
    assert intent["schema"] == "merge_request_intent"
    assert intent["publication_status"] == "not_published"
    assert intent["source_commit"] == "result"


def test_stale_or_unsafe_review_cannot_prepare_intent():
    for changes, expected in [({"verification": {"commit": "other", "result": "passed"}}, "verification"), ({"dirty": True}, "dirty"), ({"secret_exposure": True}, "secret"), ({"merge_evidence": {"conflicts": True}}, "merge")]:
        try:
            build_mr_intent(review(**changes), title="T", body="B")
        except ValueError as error:
            assert expected in str(error)
        else:
            raise AssertionError("unsafe MR intent prepared")


def test_findings_and_metadata_are_copied_into_intent():
    candidate = review(change_groups=[{"key": "CORE"}], risks=["migration"])
    intent = build_mr_intent(candidate, title="T", body="B", reviewers=["gin"], labels=["safe"], draft=False)
    assert intent["change_groups"] == [{"key": "CORE"}]
    assert intent["risks"] == ["migration"]
    assert intent["reviewers"] == ["gin"]
    assert intent["draft"] is False


if __name__ == "__main__":
    test_approved_review_creates_provider_neutral_intent()
    test_stale_or_unsafe_review_cannot_prepare_intent()
    test_findings_and_metadata_are_copied_into_intent()
    print("merge request tests passed")
