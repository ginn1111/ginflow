from initiative import approve_discovery, transition, validate_initiative


def discovery():
    return {
        "schema": "initiative",
        "initiative_key": "APP-42",
        "phase": "Discovery",
        "phase_state": "draft",
        "actor": {"id": "gin", "profile": "operator", "claim": "initiative:approve"},
        "problem": "recover context",
        "desired_outcome": "reviewable result",
        "constraints": ["read-only decision"],
        "non_goals": ["provider publication"],
        "prototype_evidence": [{"id": "proto-1", "summary": "tested idea", "promoted": False}],
        "vocabulary": {"Decision": "human review boundary"},
        "open_questions": [{"question": "which provider?", "owner": "gin", "decision_point": "publication", "blocking": False}],
        "shaping_handoff": {"objective": "shape execution", "approved": False},
    }


def test_discovery_approval_records_handoff_and_identity():
    result = approve_discovery(discovery(), approved_at="2026-10-09T12:00:00Z")
    assert result["phase"] == "Shaping"
    assert result["phase_state"] == "ready"
    assert result["shaping_handoff"]["approved"] is True
    assert result["approval"]["actor_id"] == "gin"
    assert validate_initiative(result)["valid"] is True


def test_invalid_transition_fails_without_mutating_input():
    original = discovery()
    try:
        transition(original, "Execution")
    except ValueError as error:
        assert "transition" in str(error)
    else:
        raise AssertionError("invalid transition accepted")
    assert original["phase"] == "Discovery"


def test_prototype_requires_explicit_promotion_contract():
    candidate = discovery()
    candidate["prototype_evidence"][0]["promoted"] = True
    result = validate_initiative(candidate)
    assert result["valid"] is False
    assert any("promotion" in error for error in result["errors"])


def test_transition_validates_record_before_moving_phase():
    candidate = discovery()
    del candidate["shaping_handoff"]
    try:
        transition(candidate, "Shaping")
    except ValueError as error:
        assert "invalid initiative" in str(error)
    else:
        raise AssertionError("invalid Initiative transitioned")


if __name__ == "__main__":
    test_discovery_approval_records_handoff_and_identity()
    test_invalid_transition_fails_without_mutating_input()
    test_prototype_requires_explicit_promotion_contract()
    test_transition_validates_record_before_moving_phase()
    print("initiative tests passed")
