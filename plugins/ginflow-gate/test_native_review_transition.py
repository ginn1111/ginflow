#!/usr/bin/env python3
"""Integration test for gate approval plus native Kanban review mutation."""

import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Isolate from an outer Kanban worker: its pinned board DB and write fence would leak into live fixtures.
for _key in [k for k in os.environ if k.startswith(("HERMES_KANBAN_", "HERMES_DELEGATED_"))]:
    del os.environ[_key]


ROOT = Path(__file__).resolve().parents[2]
BOARD = "ginflow-review-testing"
BODY = (
    "Objective: Native review transition\n"
    "Scope:\n- transition\n"
    "Acceptance:\n- running becomes review\n"
    "Links:\n- docs/specs/HARNESS-REVIEW-1.md"
)
SPEC = "---\nstatus: completed\n---\n# Review transition\n"


def load_gate():
    if str(ROOT / "plugins") not in sys.path:
        sys.path.insert(0, str(ROOT / "plugins"))
    return importlib.import_module("ginflow-gate.gate")


def run_hermes(env, *args):
    command = ["hermes", *args]
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    assert result.returncode == 0, (
        f"command failed ({result.returncode}): {' '.join(command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return result


def claim_as_worker(env, task_id):
    run_hermes(env, "kanban", "--board", BOARD, "claim", task_id)
    snapshot = json.loads(
        run_hermes(env, "kanban", "--board", BOARD, "show", task_id, "--json").stdout
    )
    run = next(run for run in snapshot["runs"] if run["status"] == "running")
    scoped = dict(env)
    scoped.update({"HERMES_KANBAN_TASK": task_id, "HERMES_KANBAN_RUN_ID": str(run["id"])})
    return scoped


def test_native_review_transition():
    with tempfile.TemporaryDirectory(prefix="ginflow-review-project-") as project, tempfile.TemporaryDirectory(prefix="ginflow-review-home-") as home:
        target = Path(project)
        (target / "docs/specs").mkdir(parents=True)
        (target / "docs/specs/HARNESS-REVIEW-1.md").write_text(SPEC)
        (target / ".ginflow.yaml").write_text("version: 1\nginflow:\n  board: x\n  workspace: " + str(target) + "\n  reviewer:\n    profile: gintary\n")
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.name", "Ginflow Test"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.email", "ginflow@example.test"], cwd=target, check=True)
        subprocess.run(["git", "add", "."], cwd=target, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=target, check=True)
        baseline = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target, text=True, capture_output=True, check=True).stdout.strip()
        home_path = Path(home) / "profiles" / "test"
        home_path.mkdir(parents=True, exist_ok=True)
        profile_home = str(home_path)
        env = os.environ | {"HERMES_HOME": profile_home, "HERMES_KANBAN_HOME": str(Path(home) / "kanban-home"), "HERMES_KANBAN_BOARD": BOARD}
        (home_path / "config.yaml").write_text("kanban:\n  review_dispatch: true\n")
        run_hermes(env, "kanban", "init")
        run_hermes(env, "kanban", "boards", "create", BOARD)
        created = run_hermes(env, "kanban", "--board", BOARD, "create", "HARNESS-REVIEW-1 — transition", "--body", BODY, "--assignee", "ginb", "--workspace", f"dir:{target}", "--initial-status", "blocked", "--json")
        task_id = json.loads(created.stdout)["id"]
        run_hermes(env, "kanban", "--board", BOARD, "unblock", task_id)
        worker_env = claim_as_worker(env, task_id)
        old_home = os.environ.get("HERMES_HOME")
        old_board = os.environ.get("HERMES_KANBAN_BOARD")
        os.environ["HERMES_HOME"] = profile_home
        os.environ["HERMES_KANBAN_HOME"] = env["HERMES_KANBAN_HOME"]
        os.environ["HERMES_KANBAN_BOARD"] = BOARD
        os.environ["HERMES_KANBAN_TASK"] = task_id
        os.environ["HERMES_KANBAN_RUN_ID"] = worker_env["HERMES_KANBAN_RUN_ID"]
        metadata = {"verification_result": {"commit": baseline, "command": "make test", "result": "passed"}, "artifact_baseline": {"commit": baseline, "paths": ["docs/specs/HARNESS-REVIEW-1.md"]}}
        gate = load_gate()
        card = gate.load_card(task_id, board=BOARD)
        directive = gate.pre_tool_call("kanban_request_review", {"task_id": task_id, "metadata": metadata}, "", board=BOARD)
        assert directive == {"action": "modify", "args": {"reviewer": "gintary"}}, directive
        run_hermes(worker_env, "kanban", "--board", BOARD, "request-review", task_id, "--summary", "transition verified", "--reviewer", directive["args"]["reviewer"], "--metadata", json.dumps(metadata))
        reviewed = json.loads(run_hermes(env, "kanban", "--board", BOARD, "show", task_id, "--json").stdout)["task"]
        assert reviewed["status"] == "review"
        assert reviewed["assignee"] == "gintary"
        show = json.loads(run_hermes(env, "kanban", "--board", BOARD, "show", task_id, "--json").stdout)
        assert show["task"]["status"] == "review"
        review_runs = [run for run in show.get("runs", []) if run.get("summary") == "transition verified"]
        assert review_runs, show
        assert review_runs[0]["metadata"]["verification_result"]["command"] == "make test"

        # Review dispatch is owned by dispatcher; this fixture stops at queued review.

        rejected = run_hermes(env, "kanban", "--board", BOARD, "create", "HARNESS-REVIEW-1-rejected", "--body", BODY, "--assignee", "ginb", "--workspace", f"dir:{target}", "--initial-status", "blocked", "--json")
        rejected_id = json.loads(rejected.stdout)["id"]
        run_hermes(env, "kanban", "--board", BOARD, "unblock", rejected_id)
        rejected_worker = claim_as_worker(env, rejected_id)
        os.environ["HERMES_KANBAN_TASK"] = rejected_id
        os.environ["HERMES_KANBAN_RUN_ID"] = rejected_worker["HERMES_KANBAN_RUN_ID"]
        blocked = gate.pre_tool_call("kanban_request_review", {"task_id": rejected_id, "metadata": {}}, "", board=BOARD)
        assert blocked["action"] == "block"
        rejected_card = json.loads(run_hermes(env, "kanban", "--board", BOARD, "show", rejected_id, "--json").stdout)["task"]
        assert rejected_card["status"] == "running", rejected_card


if __name__ == "__main__":
    test_native_review_transition()
    print("PASS: native running -> review transition")
