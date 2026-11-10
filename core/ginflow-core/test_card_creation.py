"""Tests for blocked execution-card creation."""
from card_creation import create_execution_cards


def test_creates_blocked_unit_and_integration_cards():
    calls = []

    def create(args):
        calls.append(args)
        return {"id": f"T-{len(calls)}", "status": args["initial_status"]}

    package = {
        "workflow_version": 2,
        "initiative_key": "INIT-1",
        "contract": {
            "key": "INIT-1-CONTRACT", "state": "approved", "objective": "ship",
            "boundaries": ["core"], "exclusions": ["deploy"], "acceptance": ["passes"],
            "verification": ["make test"], "owner": "ginb",
            "approval": {"approver": "gin", "approved_at": "2026-10-06T06:00:00Z"},
        },
        "spec": {"key": "INIT-1-SPEC", "state": "approved", "behavior": ["works"],
                  "interfaces": ["API"], "rules": ["safe"], "edge_cases": ["empty"],
                  "constraints": ["local"]},
        "units": [{
            "key": "UNIT-1", "plan_key": "PLAN-1", "owner": "worker", "scope": ["core"],
            "acceptance": ["works"], "workspace": "/repo/unit", "dependencies": [],
        }],
        "plans": [{"key": "PLAN-1", "unit_key": "UNIT-1", "state": "approved", "steps": ["code"], "verification": ["make test"]}],
        "baseline": {"commit": "abc", "verification": {"command": "make test", "result": "passed"}},
    }
    result = create_execution_cards(package, create)
    assert len(result["unit_cards"]) == 1
    assert len(calls) == 2
    assert all(call["initial_status"] == "blocked" for call in calls)
    assert calls[0]["goal_mode"] is True
    assert calls[1]["parents"] == ["T-1"]
    assert result["baseline"] == "abc"


def test_rejects_unapproved_package_without_dispatch():
    calls = []
    package = {"workflow_version": 2, "contract": {"state": "draft"}}

    def create(args):
        calls.append(args)
        return {"id": "unexpected"}

    try:
        create_execution_cards(package, create)
    except ValueError as error:
        assert "approved" in str(error)
    else:
        raise AssertionError("draft package dispatched")
    assert calls == []


def test_document_card_is_concise_and_links_document():
    calls = []

    def create(args):
        calls.append(args)
        return {"id": f"T-{len(calls)}"}

    package = {
        "workflow_version": 2, "initiative_key": "INIT-1",
        "contract": {"key": "C", "state": "approved", "objective": "ship", "boundaries": ["core"],
                     "exclusions": ["x"], "acceptance": ["ok"], "verification": ["make test"], "owner": "ginb",
                     "approval": {"approver": "gin", "approved_at": "2026-10-06T06:00:00Z"}},
        "spec": {"key": "S", "state": "approved", "behavior": ["SPEC-BEHAVIOR-TEXT"], "interfaces": ["a"],
                 "rules": ["r"], "edge_cases": ["e"], "constraints": ["c"]},
        "units": [{"key": "UNIT-1", "plan_key": "P", "owner": "worker", "scope": ["core"], "acceptance": ["works"],
                   "workspace": "/repo", "dependencies": [],
                   "document": {"provider": "local", "id": "UNIT-1", "path_or_url": "docs/work-units/UNIT-1.md"}}],
        "plans": [{"key": "P", "unit_key": "UNIT-1", "state": "approved", "steps": ["PLAN-STEP-TEXT"],
                   "verification": ["make test"]}],
        "baseline": {"commit": "abc", "verification": {"command": "make test", "result": "passed"}},
        "links": {"contract": "docs/contracts/C.md", "spec": "docs/specs/S.md"},
    }
    create_execution_cards(package, create)
    unit = calls[0]
    assert "- docs/work-units/UNIT-1.md" in unit["body"]
    assert "SPEC-BEHAVIOR-TEXT" not in unit["body"] and "PLAN-STEP-TEXT" not in unit["body"]
    assert "docs/specs/S.md" not in unit["body"]
    assert unit["initial_status"] == "blocked"
    assert unit["metadata"]["document"]["id"] == "UNIT-1"


if __name__ == "__main__":
    test_document_card_is_concise_and_links_document()
    test_creates_blocked_unit_and_integration_cards()
    test_rejects_unapproved_package_without_dispatch()
    print("card creation tests passed")
