#!/usr/bin/env python3
"""Test ginflow-gate routing and registration behavior."""

import importlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/ginflow-gate/routing.py"
TEST_BOARD = "ginflow-testing"

import sys

# Isolate from an outer Kanban worker: its pinned board DB and write fence would leak into live fixtures.
for _key in [k for k in os.environ if k.startswith(("HERMES_KANBAN_", "HERMES_DELEGATED_"))]:
    del os.environ[_key]

sys.path.insert(0, str(ROOT / "plugins"))
module = importlib.import_module("ginflow-gate.routing")

_ginflow_loaded = module._ginflow_loaded
_routing_context = module._routing_context
_route = module._route
_project_config_route = module._project_config_route


def test_workspace_and_status_routes():
    workspace = str(Path.cwd().resolve())
    assert _route([{"id": "other", "workspace_path": "/tmp/other", "status": "in_progress"}])["route"] == "no_card"
    assert _route([
        {"id": "one", "title": "First", "workspace_path": workspace, "status": "next"},
        {"id": "two", "title": "Second", "workspace_path": workspace, "status": "in_progress"},
    ])["route"] == "needs_card_selection"
    ambiguous = _route([
        {"id": "one", "title": "First", "workspace_path": workspace, "status": "next"},
        {"id": "two", "title": "Second", "workspace_path": workspace, "status": "next"},
    ])
    assert ambiguous["action"] == "orchestrator"
    assert ambiguous["candidates"] == [{"id": "one", "title": "First"}, {"id": "two", "title": "Second"}]
    assert _route([{"id": "blocked", "workspace_path": workspace, "status": "blocked"}])["route"] == "blocked_card"
    next_route = _route([{"id": "next", "workspace_path": "dir:" + workspace, "status": "next"}])
    assert next_route["route"] == "validate_card_docs"
    assert next_route["action"] == "validate"
    assert _route([{"id": "ready", "workspace_path": workspace, "status": "in_progress"}])["route"] == "ready_to_start"
    assert _route([{"id": "running", "workspace_path": workspace, "status": "running"}])["route"] == "ready_to_start"
    assert _route([{"id": "todo", "workspace_path": workspace, "status": "todo"}])["route"] == "validate_card_docs"
    assert _route([{"id": "ready-state", "workspace_path": workspace, "status": "ready"}])["route"] == "validate_card_docs"
    assert _route([{"id": "other", "workspace_path": "/tmp/other", "status": "in_progress"}], "other")["route"] == "workspace_mismatch"
    assert _route([{"id": "done", "workspace_path": workspace, "status": "done"}], "done")["route"] == "terminal_card"
    assert _route([{"id": "archived", "workspace_path": workspace, "status": "archived"}], "archived")["route"] == "terminal_card"
    print("PASS: workspace/status routes")



def test_no_ginflow_skill():
    """Routing is no-op when ginflow skill absent from session."""
    old_skills = os.environ.get("HERMES_TUI_SKILLS")
    os.environ["HERMES_TUI_SKILLS"] = ""
    try:
        assert _ginflow_loaded() is False, \
            "_ginflow_loaded() should be False with no active ginflow session skill"
        result = _routing_context()
        assert result is None, \
            "_routing_context() should return None when ginflow not loaded"
    finally:
        if old_skills is not None:
            os.environ["HERMES_TUI_SKILLS"] = old_skills
        else:
            os.environ.pop("HERMES_TUI_SKILLS", None)

    print("PASS: no ginflow → routing not called")


def test_project_config_routes_fail_closed():
    with tempfile.TemporaryDirectory(prefix="ginflow-config-routing-") as directory:
        target = Path(directory)
        old_cwd = Path.cwd()
        old_skills = os.environ.get("HERMES_TUI_SKILLS")
        try:
            os.chdir(target)
            os.environ["HERMES_TUI_SKILLS"] = "ginflow"
            missing = _routing_context()
            assert "route=project_config_missing" in missing["context"]
            assert "Run `/ginflow` to initialize" in missing["context"]
            assert "mutation_allowed=False" in missing["context"]

            (target / ".ginflow.yaml").write_text(
                "version: 1\nginflow:\n  board: test\n  workspace: relative\n"
            )
            invalid = _routing_context()
            assert "route=project_config_invalid" in invalid["context"]
            assert any(message in invalid["context"] for message in (
                "must be an absolute path", "requires PyYAML",
            ))
            assert "Repair `.ginflow.yaml`" in invalid["context"]
            assert "mutation_allowed=False" in invalid["context"]

            (target / ".ginflow.yaml").write_text(
                "version: 1\nginflow:\n  board: test\n"
                f"  workspace: {target.resolve()}\n"
            )
            if "requires PyYAML" not in invalid["context"]:
                assert _project_config_route(target) is None
                old_loader = module._load_tasks
                module._load_tasks = lambda: []
                try:
                    no_cards = _routing_context()
                finally:
                    module._load_tasks = old_loader
                assert "route=no_cards_for_workspace" in no_cards["context"]
                assert "Discovery → Shaping → Execution → Decision" in no_cards["context"]
                assert "legacy" not in no_cards["context"].lower()
        finally:
            os.chdir(old_cwd)
            if old_skills is None:
                os.environ.pop("HERMES_TUI_SKILLS", None)
            else:
                os.environ["HERMES_TUI_SKILLS"] = old_skills
    print("PASS: project config routing diagnostics")


def test_ginflow_skill_active():
    """Routing injects context when ginflow skill active in session."""
    old_skills = os.environ.get("HERMES_TUI_SKILLS")
    old_task = os.environ.pop("HERMES_KANBAN_TASK", None)
    os.environ["HERMES_TUI_SKILLS"] = "other, ginflow, plan"
    try:
        assert _ginflow_loaded() is True, \
            "_ginflow_loaded() should be True with active ginflow session skill"

        result = _routing_context()
        assert result is not None, \
            "_routing_context() should return dict when ginflow loaded"
        assert "context" in result, \
            "result should have 'context' key"
        assert "ginflow-gate routing" in result["context"], \
            "context should contain plugin marker '[ginflow-gate routing:'"
        assert "route=" in result["context"] and "mutation_allowed=" in result["context"], \
            "context should expose structured deterministic route"
        assert any(marker in result["context"] for marker in (
            "Report", "Validate", "Resume", "Do not implement",
            "Run `/ginflow` to initialize", "Repair `.ginflow.yaml`",
        )), "context should provide route action"
        if "no_cards_for_workspace" in result["context"]:
            assert "initiative" in result["context"]
            assert "Discovery → Shaping → Execution → Decision" in result["context"]
            assert "Choose work mode" not in result["context"]
            assert "legacy" not in result["context"].lower()
            assert "mutation_allowed=False" in result["context"]
    finally:
        if old_skills is not None:
            os.environ["HERMES_TUI_SKILLS"] = old_skills
        else:
            os.environ.pop("HERMES_TUI_SKILLS", None)
        if old_task is not None:
            os.environ["HERMES_KANBAN_TASK"] = old_task
        else:
            os.environ.pop("HERMES_KANBAN_TASK", None)

    print("PASS: ginflow active → routing called")


def test_old_version_metadata_does_not_change_guidance():
    old_loader = module._load_tasks
    old_context_error = module._context_error
    old_config_exists = module._config_exists
    old_skills = os.environ.get("HERMES_TUI_SKILLS")
    old_task = os.environ.get("HERMES_KANBAN_TASK")
    old_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory(prefix="ginflow-version-routing-") as directory:
            target = Path(directory)
            target.joinpath(".ginflow.yaml").write_text(
                "version: 1\nginflow:\n  board: test\n"
                f"  workspace: {target.resolve()}\n"
            )
            os.chdir(target)
            os.environ["HERMES_TUI_SKILLS"] = "ginflow"
            os.environ.pop("HERMES_KANBAN_TASK", None)
            module._context_error = lambda _workspace: None
            module._config_exists = lambda _workspace: True
            task = {"id": "selected", "workspace_path": str(target), "status": "in_progress"}
            module._load_tasks = lambda: [task]
            ordinary = module._routing_context()["context"]
            task["metadata"] = {"workflow_version": 1, "ginflow_version": 1, "legacy_v1": True}
            versioned = module._routing_context()["context"]
            assert versioned == ordinary
            assert "legacy" not in versioned.lower()
    finally:
        module._load_tasks = old_loader
        module._context_error = old_context_error
        module._config_exists = old_config_exists
        os.chdir(old_cwd)
        for key, value in (("HERMES_TUI_SKILLS", old_skills), ("HERMES_KANBAN_TASK", old_task)):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print("PASS: version metadata does not change routing guidance")


def test_live_tmp_project_card():
    """Create a real temporary Kanban card and route it from its workspace."""
    body = (
        "Objective: Route temporary card\n"
        "Scope:\n- routing\n"
        "Acceptance:\n- route blocked card\n"
        "Links:\n- docs/specs/TMP-1.md"
    )
    with tempfile.TemporaryDirectory(prefix="ginflow-gate-project-") as project, tempfile.TemporaryDirectory(prefix="ginflow-gate-home-") as home:
        target = Path(project)
        (target / "docs/specs").mkdir(parents=True)
        (target / "docs/specs/TMP-1.md").write_text("# Temporary brief\n")
        profile_home = Path(home) / "profiles" / "test"
        profile_home.mkdir(parents=True)
        env = os.environ | {"HERMES_HOME": str(profile_home), "HERMES_KANBAN_HOME": str(Path(home) / "kanban-home"), "HERMES_TUI_SKILLS": "ginflow", "HERMES_KANBAN_BOARD": TEST_BOARD}
        subprocess.run(["hermes", "kanban", "init"], env=env, check=True, capture_output=True, text=True)
        subprocess.run(
            ["hermes", "kanban", "boards", "create", TEST_BOARD],
            env=env, check=True, capture_output=True, text=True,
        )
        created = subprocess.run(
            ["hermes", "kanban", "--board", TEST_BOARD, "create", "TMP-1 — temporary routing card", "--body", body,
             "--assignee", "ginb", "--workspace", f"dir:{target}",
             "--initial-status", "blocked", "--json"],
            env=env, check=True, capture_output=True, text=True,
        )
        task = json.loads(created.stdout)
        task_id = task["id"]
        old_cwd = Path.cwd()
        try:
            os.chdir(target)
            result = _route([task], task_id)
            assert result["route"] == "blocked_card", result
            assert result["action"] == "orchestrator"
        finally:
            os.chdir(old_cwd)
    print("PASS: live temporary project/card routing")


def test_live_tmp_next_card_docs():
    """Route a real temporary card through startup document validation."""
    body = (
        "Objective: Start temporary card\n"
        "Scope:\n- routing\n"
        "Acceptance:\n- validate docs\n"
        "Links:\n- docs/specs/TMP-2.md"
    )
    with tempfile.TemporaryDirectory(prefix="ginflow-gate-project-") as project, tempfile.TemporaryDirectory(prefix="ginflow-gate-home-") as home:
        target = Path(project)
        (target / "docs/specs").mkdir(parents=True)
        (target / "docs/specs/TMP-2.md").write_text("# Temporary brief\n")
        (target / ".ginflow.yaml").write_text(
            "version: 1\nginflow:\n  board: " + TEST_BOARD + "\n"
            f"  workspace: {target.resolve()}\n"
        )
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.name", "Ginflow Test"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.email", "ginflow@example.test"], cwd=target, check=True)
        subprocess.run(["git", "add", "docs/specs/TMP-2.md"], cwd=target, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=target, check=True)
        profile_home = Path(home) / "profiles" / "test"
        profile_home.mkdir(parents=True)
        env = os.environ | {"HERMES_HOME": str(profile_home), "HERMES_KANBAN_HOME": str(Path(home) / "kanban-home"), "HERMES_KANBAN_BOARD": TEST_BOARD}
        subprocess.run(["hermes", "kanban", "init"], env=env, check=True, capture_output=True, text=True)
        subprocess.run(
            ["hermes", "kanban", "boards", "create", TEST_BOARD],
            env=env, check=True, capture_output=True, text=True,
        )
        created = subprocess.run(
            ["hermes", "kanban", "--board", TEST_BOARD, "create", "TMP-2 — temporary startup card", "--body", body,
             "--assignee", "ginb", "--workspace", f"dir:{target}",
             "--initial-status", "blocked", "--json"],
            env=env, check=True, capture_output=True, text=True,
        )
        task = json.loads(created.stdout)
        task["status"] = "next"
        task["body"] = body
        old_cwd = Path.cwd()
        old_loader = module._load_tasks
        try:
            os.chdir(target)
            module._load_tasks = lambda: [task]
            os.environ["HERMES_TUI_SKILLS"] = "ginflow"
            os.environ["HERMES_KANBAN_TASK"] = task["id"]
            result = _routing_context()
            if "requires PyYAML" in result["context"]:
                print("SKIP: live temporary next-card docs requires PyYAML")
                return
            assert result and "route=ready_to_start" in result["context"], result
            assert "mutation_allowed=False" in result["context"], result
            # startup validation reserves review for completed work only: no premature
            # kanban_request_review call and no worker-direct kanban_complete guidance.
            assert "kanban_request_review" in result["context"], result
            assert "kanban_complete" in result["context"], result
            # worker must not complete directly: review submission plus reviewer completion
            assert "do not call kanban_complete directly" in result["context"], result
            assert f"kanban_request_review(task_id='{task['id']}'" not in result["context"], result
            assert "metadata={'route': 'validate_card_docs'" not in result["context"], result
            assert task["status"] == "next"
            assert (target / "docs/specs/TMP-2.md").read_text() == "# Temporary brief\n"

            brief = target / "docs/specs/TMP-2.md"
            brief.write_text("no heading\n")
            result = _routing_context()
            assert result and "route=docs_invalid" in result["context"], result
            assert brief.read_text() == "no heading\n"

            brief.write_text("# Temporary brief\nchanged\n")
            result = _routing_context()
            assert result and "route=docs_changed" in result["context"], result
            assert brief.read_text() == "# Temporary brief\nchanged\n"

            outside_body = body.replace("docs/specs/TMP-2.md", "../outside.md")
            task["body"] = outside_body
            result = _routing_context()
            assert result and "route=docs_invalid" in result["context"], result
        finally:
            module._load_tasks = old_loader
            os.chdir(old_cwd)
            os.environ.pop("HERMES_TUI_SKILLS", None)
            os.environ.pop("HERMES_KANBAN_TASK", None)
    print("PASS: live temporary next-card doc validation")


def test_blocked_route_context_reports_metadata_without_execution():
    with tempfile.TemporaryDirectory(prefix="ginflow-gate-blocked-") as project:
        target = Path(project)
        (target / ".ginflow.yaml").write_text(
            "version: 1\nginflow:\n  board: test\n"
            f"  workspace: {target.resolve()}\n"
        )
        workspace = str(target.resolve())
        task = {
            "id": "blocked-with-evidence",
            "title": "Blocked with evidence",
            "workspace_path": workspace,
            "status": "blocked",
            "blocker_metadata": {
                "event_id": "evt-1",
                "event_type": "blocked",
                "blocker_kind": "transient",
                "decision": "pending",
            },
        }
        old_loader = module._load_tasks
        old_skills = os.environ.get("HERMES_TUI_SKILLS")
        old_task = os.environ.get("HERMES_KANBAN_TASK")
        old_cwd = Path.cwd()
        try:
            os.chdir(target)
            setattr(module, "_load_tasks", lambda: [task])
            os.environ["HERMES_TUI_SKILLS"] = "ginflow"
            os.environ["HERMES_KANBAN_TASK"] = task["id"]
            result = _routing_context()
            if "requires PyYAML" in result["context"]:
                print("SKIP: blocked route context requires PyYAML")
                return
            assert result and "route=blocked_card" in result["context"], result
            assert "Report blocker to orchestrator; do not implement." in result["context"]
            assert '"event_id": "evt-1"' in result["context"]
            assert "Resume implementation" not in result["context"]
        finally:
            os.chdir(old_cwd)
            setattr(module, "_load_tasks", old_loader)
            if old_skills is None:
                os.environ.pop("HERMES_TUI_SKILLS", None)
            else:
                os.environ["HERMES_TUI_SKILLS"] = old_skills
            if old_task is None:
                os.environ.pop("HERMES_KANBAN_TASK", None)
            else:
                os.environ["HERMES_KANBAN_TASK"] = old_task
    print("PASS: blocked route reports metadata without execution")


if __name__ == "__main__":
    test_workspace_and_status_routes()
    test_no_ginflow_skill()
    test_project_config_routes_fail_closed()
    test_ginflow_skill_active()
    test_old_version_metadata_does_not_change_guidance()
    if shutil.which("hermes"):
        test_live_tmp_project_card()
        test_live_tmp_next_card_docs()
    else:
        print("SKIP: live Kanban card tests (hermes CLI not installed)")
    test_blocked_route_context_reports_metadata_without_execution()
    print("ginflow routing test passed")


# Completion gate integration coverage
routing_module = module
#!/usr/bin/env python3
import importlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/ginflow-gate/gate.py"

module = importlib.import_module("ginflow-gate.gate")
validate_completion = module.validate_completion


def test_linked_frontmatter_without_pyyaml():
    old_yaml = module.yaml
    module.yaml = None
    try:
        with tempfile.TemporaryDirectory(prefix="ginflow-frontmatter-") as directory:
            target = Path(directory)
            brief = target / "docs/specs/GATE-1.md"
            brief.parent.mkdir(parents=True)
            card = {"links": ["docs/specs/GATE-1.md"]}
            brief.write_text("---\nstatus: completed\n---\n# Gate\n")
            assert module.linked_documents_missing_completion(card, target) == []
            brief.write_text("---\nstatus: draft\n---\n# Gate\n")
            assert module.linked_documents_missing_completion(card, target) == ["docs/specs/GATE-1.md"]
    finally:
        module.yaml = old_yaml
    print("PASS: linked frontmatter works without PyYAML")


test_linked_frontmatter_without_pyyaml()


card = {
    "id": "GATE-1",
    "title": "Gate",
    "objective": "Enforce completion",
    "scope": ["plugin"],
    "acceptance": ["bad completion rejected"],
    "workspace": "dir:/tmp/target",
    "status": "running",
    "assignee": "worker",
    "links": ["docs/specs/GATE-1.md"],
}
setattr(module, "load_card", lambda task_id, board=None: card)

for tool_name in ("kanban_request_review", "kanban_complete"):
    blocked = module.pre_tool_call(tool_name, {"task_id": "GATE-1", "metadata": {}}, "", profile="worker")
    assert blocked["action"] == "block"
    assert blocked["message"].startswith("ginflow-gate: ")

    setattr(module, "validate_completion", lambda card, metadata: None)
    allowed = module.pre_tool_call(
        tool_name,
        {
            "task_id": "GATE-1",
            "metadata": {
                "verification_result": {"commit": "abc", "command": "make test", "result": "passed"},
                "artifact_baseline": {"commit": "abc", "paths": ["docs/specs/GATE-1.md"]},
            },
        },
        "",
        profile="worker",
    )
    assert allowed is None

    setattr(module, "validate_completion", lambda card, metadata: "linked artifact drift: docs/specs/GATE-1.md")
    blocked = module.pre_tool_call(
        tool_name,
        {
            "task_id": "GATE-1",
            "metadata": {
                "verification_result": {"commit": "abc", "command": "make test", "result": "passed"},
                "artifact_baseline": {"commit": "abc", "paths": ["docs/specs/GATE-1.md"]},
            },
        },
        "",
    )
    assert blocked["action"] == "block"
    assert "drift" in blocked["message"]

setattr(module, "load_card", lambda task_id, board=None: (_ for _ in ()).throw(RuntimeError("DB unavailable")))
failed_closed = module.pre_tool_call("kanban_request_review", {"task_id": "GATE-1", "metadata": {}}, "")
assert failed_closed["action"] == "block"
assert "validation failed closed" in failed_closed["message"]

with tempfile.TemporaryDirectory(prefix="ginflow-gate-") as directory:
    target = Path(directory)
    brief = target / "docs/specs/GATE-1.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("---\nstatus: completed\n---\n# Gate\n")
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "Ginflow Test"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "ginflow@example.test"], cwd=target, check=True)
    subprocess.run(["git", "add", "docs/specs/GATE-1.md"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=target, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=target, text=True, capture_output=True, check=True
    ).stdout.strip()
    committed_card = card | {"workspace": f"dir:{target}"}
    metadata = {
        "verification_result": {"commit": commit, "command": "make test", "result": "passed"},
        "artifact_baseline": {"commit": commit, "paths": ["docs/specs/GATE-1.md"]},
    }
    assert validate_completion(committed_card, metadata) is None
    brief.write_text("# Gate\n\n**Status: completed**\n")
    incomplete_error = validate_completion(committed_card, metadata)
    assert "status: completed" in incomplete_error
    setattr(module, "load_card", lambda task_id, board=None: committed_card)
    setattr(module, "validate_completion", validate_completion)
    blocked = module.pre_tool_call("kanban_request_review", {"task_id": "GATE-1", "metadata": metadata}, "")
    assert blocked["action"] == "block"
    assert "docs/specs/GATE-1.md" in blocked["message"]
    assert "retry" in blocked["message"]
    assert brief.read_text() == "# Gate\n\n**Status: completed**\n"
    brief.write_text("---\nstatus: completed\n---\n# Gate\n\n**Status: in_progress**\n")
    assert module.linked_documents_missing_completion(committed_card, target) == []
    metadata["verification_result"]["commit"] = "mismatch"
    assert "must match" in validate_completion(committed_card, metadata)

    for contents in ("---\nstatus: draft\n---\n# Gate\n", "---\nstatus: [\n---\n# Gate\n", "# Gate\n"):
        brief.write_text(contents)
        error = validate_completion(committed_card, metadata | {
            "verification_result": {"commit": commit, "command": "make test", "result": "passed"}
        })
        assert "status: completed" in error

class Hooks:
    def __init__(self):
        self.names = []

    def register_hook(self, name, callback):
        self.names.append(name)


package = importlib.import_module("ginflow-gate")
hooks = Hooks()
package.register(hooks)
assert hooks.names == ["pre_llm_call", "pre_tool_call", "kanban_task_blocked", "pre_tool_call", "post_tool_call"]

print("ginflow gate rejection test passed")
