#!/usr/bin/env python3
"""Block routing test: kanban_task_blocked hook -> one `hermes send` (stub on PATH)."""
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins"))
BOARD = "ginflow-block-routing"
BODY = "Objective: x\nScope:\n- x\nAcceptance:\n- x\nLinks:\n- docs/specs/X-1.md"
REAL_HERMES = shutil.which("hermes")
STUB = f"""#!/bin/sh
if [ "$1" = "send" ]; then
  [ -f "$STUB_FAIL" ] && exit 1
  printf '%s\\n' "$*" >> "$STUB_LOG"
  exit 0
fi
exec {REAL_HERMES} "$@"
"""


def load_plugin():
    return importlib.import_module("ginflow-gate")


class Ctx:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, callback):
        self.hooks[name] = callback


def hermes(env, *args):
    result = subprocess.run(["hermes", *args], env=env, text=True, capture_output=True)
    assert result.returncode == 0, f"{args}\n{result.stdout}\n{result.stderr}"
    return result.stdout


def main():
    ctx = Ctx()
    load_plugin().register(ctx)
    hook = ctx.hooks["kanban_task_blocked"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "bin").mkdir()
        stub = tmp / "bin/hermes"
        stub.write_text(STUB)
        stub.chmod(0o755)
        log = tmp / "send.log"
        home = tmp / "home/profiles/test"
        home.mkdir(parents=True)
        env = os.environ | {
            "PATH": f"{tmp / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "HERMES_HOME": str(home), "HERMES_KANBAN_HOME": str(tmp / "kanban-home"), "HERMES_KANBAN_BOARD": BOARD, "STUB_LOG": str(log), "STUB_FAIL": str(tmp / "fail"),
        }
        env.pop("GINFLOW_LOG", None)
        # Isolate from any outer Hermes session (delegated child, kanban worker).
        for key in [k for k in env if k.startswith("HERMES_KANBAN_") or k in (
            "HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_SUPERVISED_CHILD", "HERMES_SINGLE_QUERY_SESSION", "HERMES_PROFILE")]:
            if key != "HERMES_KANBAN_BOARD":
                del env[key]
        os.environ.clear()
        os.environ.update(env)
        project = tmp / "project"
        project.mkdir()
        project = project.resolve()
        hermes(env, "kanban", "init")
        hermes(env, "kanban", "boards", "create", BOARD)

        def write_config(extra):
            (project / ".ginflow.yaml").write_text(
                f"ginflow:\n  board: {BOARD}\n  workspace: {project}\n{extra}"
            )

        def block(kind, reason):
            created = json.loads(hermes(env, "kanban", "--board", BOARD, "create", f"t-{kind}", "--body", BODY,
                                        "--assignee", "ginb", "--workspace", f"dir:{project}", "--json"))
            tid = created["id"]
            hermes(env, "kanban", "--board", BOARD, "claim", tid)
            hermes(env, "kanban", "--board", BOARD, "block", tid, reason, *(["--kind", kind] if kind else []))
            return tid

        def fire(tid, reason):
            hook(task_id=tid, board=BOARD, assignee="ginb", run_id=7, reason=reason)
            return log.read_text().splitlines() if log.exists() else []

        def status(tid):
            return json.loads(hermes(env, "kanban", "--board", BOARD, "show", tid, "--json"))["task"]["status"]

        # trace off: no send
        write_config("  notify:\n    target: telegram:123\n")
        tid = block("needs_input", "need api key")
        assert fire(tid, "need api key") == []

        # trace on, valid target, critical kinds: one send each, stays blocked
        write_config("  trace: true\n  notify:\n    target: telegram:123\n")
        calls = fire(tid, "need api key\nsecret\x07")
        assert len(calls) == 1, calls
        assert calls[0].startswith("send --to telegram:123 -q "), calls[0]
        assert tid in calls[0] and "need api key" in calls[0] and "ginb" in calls[0] and "Run: 7" in calls[0]
        assert "\x07" not in calls[0]
        assert status(tid) == "blocked"
        cap = block("capability", "x" * 5000)
        calls = fire(cap, "x" * 5000)
        assert len(calls) == 2 and len(calls[1]) < 1000, len(calls[1])
        assert status(cap) == "blocked"

        # dependency + untyped + transient: untouched
        before = len(calls)
        # dependency block: Hermes only waits in todo with an open parent, which cannot be
        # linked to a running child, so drive the hook with a dependency-kind task directly.
        br = importlib.import_module("ginflow-gate.block_routing")
        real_load = br._load_task
        br._load_task = lambda task_id, board: real_load(task_id, board) | {"block_kind": "dependency"}
        got = fire(tid, "r")
        br._load_task = real_load
        assert len(got) == before, got[before:]
        t = block(None, "r")
        assert len(fire(t, "r")) == before and status(t) == "blocked"

        # transient: origin comment, assigned to configured reviewer, unblocked, no send
        def show(tid):
            return json.loads(hermes(env, "kanban", "--board", BOARD, "show", tid, "--json"))

        reviewer = "  reviewer:\n    profile: repairer\n"
        write_config("  trace: true\n  notify:\n    target: telegram:123\n" + reviewer)
        t = block("transient", "flaky net\nretry")
        assert len(fire(t, "flaky net\nretry")) == before
        data = show(t)
        note = [c["body"] for c in data["comments"] if c["body"].startswith("[ginflow]")]
        assert len(note) == 1 and all(x in note[0] for x in (
            "origin=worker", "profile=ginb", "run=7", "kind=transient", "flaky net retry")), note
        assert data["task"]["assignee"] == "repairer" and data["task"]["status"] in ("ready", "todo"), data["task"]
        # trace on, no reviewer configured: no reassign, escalated like a critical block
        write_config("  trace: true\n  notify:\n    target: telegram:123\n")
        t = block("transient", "r")
        got = fire(t, "r")
        assert len(got) == before + 1 and got[-1].startswith("send --to telegram:123 -q "), got[before:]
        assert show(t)["task"]["assignee"] == "ginb" and status(t) == "blocked"
        before = len(got)
        # trace off: native, no assignment
        write_config("")
        t = block("transient", "r")
        fire(t, "r")
        assert show(t)["task"]["assignee"] == "ginb" and status(t) == "blocked"
        write_config("  trace: true\n  notify:\n    target: telegram:123\n")

        # invalid notify.target: no send
        for bad in ("  notify:\n    target: ''\n", "  notify:\n    target: 5\n", "  notify:\n    other: 1\n"):
            write_config("  trace: true\n" + bad)
            t = block("needs_input", "r")
            assert len(fire(t, "r")) == before, bad
            assert status(t) == "blocked"
        sys.path.insert(0, str(ROOT / "skills/ginflow/lib"))
        import project_config
        assert "notify" in project_config.context_error(project), project_config.context_error(project)
        write_config("  trace: true\n")  # missing notify valid
        assert project_config.context_error(project) is None

        def comments(tid):
            data = json.loads(hermes(env, "kanban", "--board", BOARD, "show", tid, "--json"))
            return [c["body"] for c in data["comments"] if c["body"].startswith("[ginflow]")]

        # no target: native subscription destination used
        write_config("  trace: true\n")
        n = len(log.read_text().splitlines())
        t = block("needs_input", "need key")
        hermes(env, "kanban", "--board", BOARD, "notify-subscribe", t, "--platform", "telegram", "--chat-id", "99")
        got = fire(t, "need key")
        assert len(got) == n + 1 and got[-1].startswith("send --to telegram:99 -q "), got[n:]
        assert comments(t) == [] and status(t) == "blocked", (comments(t), status(t))

        # no target, no subscription: card comment, stays blocked
        t = block("capability", "need access")
        assert len(fire(t, "need access")) == n + 1
        got = comments(t)
        assert len(got) == 1 and t in got[0] and "no notify destination" in got[0], got
        assert status(t) == "blocked"

        # push failure: card comment, stays blocked
        write_config("  trace: true\n  notify:\n    target: telegram:1\n")
        (tmp / "fail").write_text("")
        t = block("needs_input", "need key")
        fire(t, "need key")
        got = comments(t)
        assert len(got) == 1 and "push failed" in got[0], got
        assert status(t) == "blocked"
        (tmp / "fail").unlink()

        # second transient block on same task: critical push, no reassign, still blocked
        write_config("  trace: true\n  notify:\n    target: telegram:1\n" + reviewer)
        t = block("transient", "flaky")
        n = len(fire(t, "flaky"))  # first: auto-repair, no send
        assert show(t)["task"]["assignee"] == "repairer"
        hermes(env, "kanban", "--board", BOARD, "claim", t)
        hermes(env, "kanban", "--board", BOARD, "block", t, "flaky again", "--kind", "transient")
        got = fire(t, "flaky again")
        assert len(got) == n + 1 and got[-1].startswith("send --to telegram:1 -q ") and "flaky again" in got[-1], got[n:]
        data = show(t)
        # hook never unblocks/reassigns; Hermes core may itself escalate a re-blocked task to triage
        assert data["task"]["assignee"] == "repairer" and data["task"]["status"] in ("blocked", "triage"), data["task"]
        assert len([c for c in data["comments"] if c["body"].startswith("[ginflow] origin=worker")]) == 1

        # hook failure (hermes send missing/erroring) never raises
        write_config("  trace: true\n  notify:\n    target: telegram:1\n")
        os.environ["PATH"] = "/nonexistent"
        hook(task_id="t_missing", board=BOARD, assignee="ginb", run_id=1, reason="r")
    print("PASS: critical block routing")


if __name__ == "__main__":
    main()
