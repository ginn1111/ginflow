#!/usr/bin/env python3
"""GINFLOW-MR-1: reviewer kanban_complete auto-publish, with fake gh/glab/hermes on PATH and a real git remote."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "plugins/ginflow-gate/__init__.py"
spec = importlib.util.spec_from_file_location("ginflow_gate_publish_pkg", path, submodule_search_locations=[str(path.parent)])
mod = importlib.util.module_from_spec(spec)
sys.modules["ginflow_gate_publish_pkg"] = mod
spec.loader.exec_module(mod)
gate = sys.modules["ginflow_gate_publish_pkg.gate"]
pub = sys.modules["ginflow_gate_publish_pkg.publish"]
routing = sys.modules["ginflow_gate_publish_pkg.routing"]

FAKE = r'''#!/bin/sh
echo "$(basename "$0") $*" >> "$FAKE_LOG"
case "$(basename "$0") $1 $2" in
  "gh auth status"|"glab auth status") exit "${FAKE_AUTH:-0}" ;;
  "gh pr list"|"glab mr list") echo "${FAKE_EXISTING:-[]}" ;;
  "gh pr create"|"glab mr create") [ -n "$FAKE_CREATE_FAIL" ] && { echo boom >&2; exit 1; }; echo "https://example.test/mr/1" ;;
  "hermes kanban "*) case "$*" in *" show "*) echo "{\"task\": {\"branch_name\": \"$FAKE_BRANCH\"}}" ;; esac ;;
esac
'''


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    for name in ("gh", "glab", "hermes"):
        (bin_dir / name).write_text(FAKE)
        (bin_dir / name).chmod(0o755)
    log = tmp / "calls.log"
    remote = tmp / "remote.git"
    git("init", "-q", "--bare", str(remote), cwd=tmp)
    repo = tmp / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "t@t", cwd=repo)
    git("config", "user.name", "t", cwd=repo)
    git("remote", "add", "origin", str(remote), cwd=repo)
    (repo / "docs/specs").mkdir(parents=True)
    (repo / "docs/specs/P-1.md").write_text("---\nstatus: completed\n---\n# P\n")
    (repo / ".ginflow.yaml").write_text(
        f"version: 1\nginflow:\n  board: b\n  workspace: {repo}\n  reviewer:\n    profile: gintary\n"
        "  publish:\n    provider: github\n    target: main\n")
    git("add", ".", cwd=repo)
    git("commit", "-qm", "base", cwd=repo)
    worktree = tmp / "wt"
    git("worktree", "add", "-q", "-b", "wt/p-1", str(worktree), cwd=repo)
    commit = git("rev-parse", "HEAD", cwd=worktree)

    os.environ.update(PATH=f"{bin_dir}:{os.environ['PATH']}", FAKE_LOG=str(log), FAKE_BRANCH="wt/p-1",
                      HERMES_HOME=str(tmp / "profiles/gintary"))
    card = {"id": "t_p1", "title": "P-1 — publish", "objective": "o", "scope": ["s"], "acceptance": ["a"],
            "workspace": f"worktree:{worktree}", "status": "review", "assignee": "ginb", "links": ["docs/specs/P-1.md"]}
    gate.load_card = lambda task_id, board=None: card
    metadata = {"verification_result": {"commit": commit, "command": "make test", "result": "passed"},
                "artifact_baseline": {"commit": commit, "paths": ["docs/specs/P-1.md"]}}
    args = {"task_id": "t_p1", "metadata": metadata}

    def calls():
        text = log.read_text() if log.exists() else ""
        log.write_text("")
        return text

    # worktree workspace passes completion validation
    assert gate.validate_completion(card, metadata) is None

    # auth failure blocks reviewer completion; nothing pending
    os.environ["FAKE_AUTH"] = "1"
    blocked = gate.pre_tool_call("kanban_complete", args)
    assert blocked and blocked["action"] == "block" and "unauthenticated" in blocked["message"], blocked
    assert "t_p1" not in pub._PENDING
    # startup routing reports the same blocker
    route = routing._project_config_route(repo)
    assert route and route[0] == "publish_unavailable", route
    os.environ["FAKE_AUTH"] = "0"
    assert routing._project_config_route(repo) is None
    calls()

    # non-reviewer profile: no publish
    os.environ["HERMES_HOME"] = str(tmp / "profiles/ginb")
    assert gate.pre_tool_call("kanban_complete", args) is None and "t_p1" not in pub._PENDING
    os.environ["HERMES_HOME"] = str(tmp / "profiles/gintary")

    # missing branch blocks
    os.environ["FAKE_BRANCH"] = ""
    blocked = gate.pre_tool_call("kanban_complete", args)
    assert blocked and "branch_name" in blocked["message"], blocked
    os.environ["FAKE_BRANCH"] = "wt/p-1"

    # happy path: push exact commit, create PR, comment URL
    assert gate.pre_tool_call("kanban_complete", args) is None and "t_p1" in pub._PENDING
    calls()
    gate.post_tool_call("kanban_complete", json.dumps({"ok": True}), args)
    seen = calls()
    assert git("rev-parse", "refs/heads/wt/p-1", cwd=remote) == commit
    assert "gh pr create -H wt/p-1 -B main -t P-1 — publish" in seen, seen
    assert "comment t_p1 ginflow-publish: https://example.test/mr/1" in seen, seen
    assert "t_p1" not in pub._PENDING

    # existing PR reused, create skipped
    os.environ["FAKE_EXISTING"] = '[{"url": "https://example.test/mr/9"}]'
    gate.pre_tool_call("kanban_complete", args)
    gate.post_tool_call("kanban_complete", json.dumps({"ok": True}), args)
    seen = calls()
    assert "pr create" not in seen and "ginflow-publish: https://example.test/mr/9" in seen, seen
    del os.environ["FAKE_EXISTING"]

    # failed tool result: no publish
    gate.pre_tool_call("kanban_complete", args)
    gate.post_tool_call("kanban_complete", json.dumps({"ok": False, "error": "x"}), args)
    assert "pr create" not in calls()

    # create failure: comment error, never raise
    os.environ["FAKE_CREATE_FAIL"] = "1"
    gate.pre_tool_call("kanban_complete", args)
    gate.post_tool_call("kanban_complete", json.dumps({"ok": True}), args)
    seen = calls()
    assert "ginflow-publish failed: gh pr create: boom" in seen, seen
    del os.environ["FAKE_CREATE_FAIL"]

    # dir: workspace with publish configured: untouched
    dir_card = card | {"workspace": f"dir:{repo}"}
    gate.load_card = lambda task_id, board=None: dir_card
    assert gate.pre_tool_call("kanban_complete", args) is None and "t_p1" not in pub._PENDING

print("PASS: publish hook")
