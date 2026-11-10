from copy import deepcopy

from execution_batch import authorize_batch, canonical_digest, create_batch


ACTOR = {"id": "gin", "profile": "operator", "claim": "execution:authorize"}


def authorize(package_value, **changes):
    values = {
        "actor": ACTOR,
        "budget": {"max_turns": 10},
        "stop_conditions": ["stop"],
        "workspaces": ["/repo/u"],
        "baseline_commit": "base",
    }
    values.update(changes)
    return authorize_batch(package_value, **values)


def package():
    return {
        "workflow_version": 2,
        "initiative_key": "APP-42",
        "package_revision": "APP-42/pkg-1",
        "contract": {"key": "C", "state": "approved", "objective": "ship", "boundaries": ["core"], "exclusions": ["deploy"], "acceptance": ["works"], "verification": ["make test"], "approval": {"approver": "gin", "approved_at": "2026-10-09T00:00:00Z"}},
        "spec": {"state": "approved", "key": "S", "behavior": ["works"], "interfaces": ["API"], "rules": ["safe"], "edge_cases": ["empty"], "constraints": ["local"]},
        "units": [{"key": "U", "plan_key": "P", "owner": "worker", "objective": "ship core", "scope": ["core"], "exclusions": ["deploy"], "acceptance": ["works"], "workspace": "/repo/u", "dependencies": [], "verification": ["make test"], "change_group": "CORE", "risk": "low", "escalation": "stop on failure"}],
        "plans": [{"key": "P", "unit_key": "U", "state": "approved", "steps": ["code"], "verification": ["make test"]}],
        "baseline": {"commit": "base", "verification": {"command": "make test", "result": "passed"}},
    }


def test_digest_is_canonical_and_authorization_binds_inputs():
    p = package()
    first = canonical_digest(p)
    assert first == canonical_digest({key: p[key] for key in reversed(p)})
    result = authorize_batch(p, actor=ACTOR, budget={"max_turns": 10}, stop_conditions=["verification failure"], workspaces=["/repo/u"], baseline_commit="base")
    assert result["schema"] == "execution_batch"
    assert result["batch_key"] == "APP-42/run-1"
    assert result["package_digest"] == first
    assert result["immutable"] is True


def test_changed_package_and_incomplete_ticket_rejected():
    p = package()
    try:
        authorize_batch(p, actor=ACTOR, budget={"max_turns": 10}, stop_conditions=["stop"], workspaces=["/repo/u"], baseline_commit="wrong")
    except ValueError as error:
        assert "baseline" in str(error)
    else:
        raise AssertionError("changed baseline authorized")
    p["units"][0].pop("change_group")
    try:
        authorize_batch(p, actor=ACTOR, budget={"max_turns": 10}, stop_conditions=["stop"], workspaces=["/repo/u"], baseline_commit="base")
    except ValueError as error:
        assert "change_group" in str(error)
    else:
        raise AssertionError("incomplete Ticket authorized")


def test_create_batch_delegates_legacy_card_creator():
    calls = []
    result = create_batch(package(), actor=ACTOR, budget={"max_turns": 10}, stop_conditions=["stop"], workspaces=["/repo/u"], baseline_commit="base", create_card=lambda args: calls.append(args) or {"id": str(len(calls))})
    assert result["cards"]["integration_card"]["id"] == "2"
    assert calls[0]["metadata"]["initiative_key"] == "APP-42"


def test_shared_mutable_workspace_requires_isolation_proof():
    candidate = package()
    second = deepcopy(candidate["units"][0])
    second.update({"key": "V", "plan_key": "Q", "objective": "ship docs"})
    candidate["units"].append(second)
    candidate["plans"].append({"key": "Q", "unit_key": "V", "state": "approved", "steps": ["code"], "verification": ["make test"]})
    try:
        authorize(candidate)
    except ValueError as error:
        assert "shared mutable workspace" in str(error)
    else:
        raise AssertionError("shared mutable workspace authorized")


def test_isolated_worktree_proof_allows_parallel_units():
    candidate = package()
    second = deepcopy(candidate["units"][0])
    second.update({"key": "V", "plan_key": "Q", "objective": "ship docs", "workspace_isolation": {"kind": "worktree", "path": "/tmp/worktree-v"}})
    candidate["units"][0]["workspace_isolation"] = {"kind": "worktree", "path": "/tmp/worktree-u"}
    candidate["units"].append(second)
    candidate["plans"].append({"key": "Q", "unit_key": "V", "state": "approved", "steps": ["code"], "verification": ["make test"]})
    result = authorize(candidate)
    assert result["ticket_keys"] == ["U", "V"]


def test_duplicate_workspace_declarations_rejected():
    try:
        authorize(package(), workspaces=["/repo/u", "/repo/u"])
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("duplicate workspace declarations authorized")


def _two_units(path_u, path_v):
    candidate = package()
    second = deepcopy(candidate["units"][0])
    second.update({"key": "V", "plan_key": "Q", "objective": "ship docs", "workspace_isolation": {"kind": "worktree", "path": path_v}})
    candidate["units"][0]["workspace_isolation"] = {"kind": "worktree", "path": path_u}
    candidate["units"].append(second)
    candidate["plans"].append({"key": "Q", "unit_key": "V", "state": "approved", "steps": ["code"], "verification": ["make test"]})
    return candidate


def test_nested_worktrees_are_valid_isolation():
    authorize(_two_units("/repo/u/.claude/worktrees/u", "/repo/u/.claude/worktrees/v"))


def test_isolation_path_equal_to_shared_or_to_each_other_is_rejected():
    for u, v, expected in [("/repo/u", "/repo/u/worktree-v", "isolation proof"), ("/repo/u/wt", "/repo/u/wt", "distinct isolation paths")]:
        try:
            authorize(_two_units(u, v))
        except ValueError as error:
            assert expected in str(error)
        else:
            raise AssertionError("shared mutable path authorized")


def test_collection_fields_reject_strings_and_stop_conditions_reject_blanks():
    candidate = package()
    candidate["units"][0]["scope"] = "core"
    try:
        authorize(candidate)
    except ValueError as error:
        assert "scope" in str(error)
    else:
        raise AssertionError("string scope authorized")
    try:
        authorize(package(), stop_conditions=[" "])
    except ValueError as error:
        assert "stop_conditions" in str(error)
    else:
        raise AssertionError("blank stop condition authorized")


if __name__ == "__main__":
    test_digest_is_canonical_and_authorization_binds_inputs()
    test_changed_package_and_incomplete_ticket_rejected()
    test_create_batch_delegates_legacy_card_creator()
    test_shared_mutable_workspace_requires_isolation_proof()
    test_isolated_worktree_proof_allows_parallel_units()
    test_duplicate_workspace_declarations_rejected()
    test_nested_worktrees_are_valid_isolation()
    test_isolation_path_equal_to_shared_or_to_each_other_is_rejected()
    test_collection_fields_reject_strings_and_stop_conditions_reject_blanks()
    print("execution batch tests passed")
