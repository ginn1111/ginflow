#!/usr/bin/env python3
"""STACK-1: kanban_task_completed hook stacks child worktree branches on parent branches (live temp board + repo)."""
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
BOARD = "ginflow-stacking"
BODY = "Objective: x\nScope:\n- x\nAcceptance:\n- x\nLinks:\n- docs/specs/X-1.md"


class Ctx:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, callback):
        self.hooks[name] = callback


def run(cmd, cwd=None, check=True):
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    assert not check or result.returncode == 0, f"{cmd}\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


def main():
    if not shutil.which("hermes"):
        print("SKIP: stacking hook (hermes CLI not installed)")
        return
    ctx = Ctx()
    importlib.import_module("ginflow-gate").register(ctx)
    hook = ctx.hooks["kanban_task_completed"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()
        env = os.environ | {"HERMES_HOME": str(tmp / "home/profiles/test"), "HERMES_KANBAN_HOME": str(tmp / "kh"),
                            "HERMES_KANBAN_BOARD": BOARD}
        # Isolate from any outer Hermes session (delegated child, kanban worker).
        for key in [k for k in env if k.startswith("HERMES_KANBAN_") and k not in ("HERMES_KANBAN_BOARD", "HERMES_KANBAN_HOME")
                    or k in ("HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_SUPERVISED_CHILD", "HERMES_SINGLE_QUERY_SESSION", "HERMES_PROFILE")]:
            del env[key]
        os.environ.clear()
        os.environ.update(env)
        (tmp / "home/profiles/test").mkdir(parents=True)
        run(["hermes", "kanban", "init"])
        run(["hermes", "kanban", "boards", "create", BOARD])
        repo = tmp / "repo"
        repo.mkdir()
        git = lambda *a, cwd=repo, **k: run(["git", *a], cwd=cwd, **k)
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (repo / ".ginflow.yaml").write_text(f"ginflow:\n  board: {BOARD}\n  workspace: {repo}\n")
        (repo / "base.txt").write_text("base\n")
        git("add", ".")
        git("commit", "-qm", "base")
        git("config", "user.email", "t@t", cwd=repo)

        def kb(*a):
            return run(["hermes", "kanban", "--board", BOARD, *a])

        def show(tid):
            return json.loads(kb("show", tid, "--json"))

        def card(title, *parents, worktree=True):
            ws = f"worktree:{repo / '.worktrees' / title}" if worktree else f"dir:{repo}"
            args = ["create", title, "--body", BODY, "--assignee", "ginb", "--workspace", ws, "--json"]
            for p in parents:
                args += ["--parent", p]
            return json.loads(kb(*args))["id"]

        def parent(name, fname, content):
            """Done-able parent: real worktree + commit on wt/<id>."""
            tid = card(name)
            git("worktree", "add", "-q", "-b", f"wt/{tid}", str(repo / ".worktrees" / name), "main")
            wt = repo / ".worktrees" / name
            (wt / fname).write_text(content)
            git("add", ".", cwd=wt)
            git("commit", "-qm", name, cwd=wt)
            kb("claim", tid)
            return tid

        def done(tid):
            kb("complete", tid, "--summary", "ok")

        def comments(tid):
            return [c["body"] for c in show(tid)["comments"] if c["body"].startswith("[ginflow-stack]")]

        # single parent: wt/B at wt/A head, worktree on it, base comment
        a = parent("A", "a.txt", "a\n")
        b = card("B", a)
        done(a)
        hook(task_id=a, board=BOARD, assignee="ginb", run_id=1, summary="ok")
        head_a = git("rev-parse", f"wt/{a}")
        assert git("rev-parse", f"wt/{b}") == head_a
        assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo / ".worktrees" / b) == f"wt/{b}"
        got = comments(b)
        assert len(got) == 1 and got[0].startswith(f"[ginflow-stack] base=wt/{a} head="), got
        hook(task_id=a, board=BOARD)  # replay: branch exists, status not live -> no second comment, no error
        assert len(comments(b)) == 1

        # two parents, non-conflicting: both heads in wt/C
        p1, p2 = parent("P1", "p1.txt", "1\n"), parent("P2", "p2.txt", "2\n")
        c = card("C", p1, p2)
        done(p1)
        hook(task_id=p1, board=BOARD)
        assert not git("branch", "--list", f"wt/{c}"), "acts only once all parents done"
        done(p2)
        hook(task_id=p2, board=BOARD)
        for p in (p1, p2):
            git("merge-base", "--is-ancestor", f"wt/{p}", f"wt/{c}")
        assert comments(c) and all(f"wt/{p}" in comments(c)[0] for p in (p1, p2)), comments(c)

        # conflict: blocked needs_input, comment, merge aborted, clean status
        q1, q2 = parent("Q1", "same.txt", "x\n"), parent("Q2", "same.txt", "y\n")
        d = card("D", q1, q2)
        done(q1)
        done(q2)
        hook(task_id=q2, board=BOARD)
        task = show(d)
        assert task["task"]["status"] == "blocked", task["task"]
        assert any(e.get("kind") == "blocked" and (e.get("payload") or {}).get("kind") == "needs_input" for e in task["events"])
        assert any(x.startswith("[ginflow-stack] conflict") for x in comments(d)), comments(d)
        assert git("status", "--porcelain", cwd=repo / ".worktrees" / d) == ""
        assert not (repo / ".worktrees" / d / ".git").is_dir()
        assert not Path(git("rev-parse", "--git-path", "MERGE_HEAD", cwd=repo / ".worktrees" / d)).exists()

        # running child with existing branch lacking parent head: no git change, stale-base comment (once)
        r = parent("R", "r.txt", "r\n")
        e = card("E", r)
        git("branch", f"wt/{e}", "main")
        done(r)
        kb("claim", e)
        before = git("worktree", "list")
        hook(task_id=r, board=BOARD)
        hook(task_id=r, board=BOARD)
        assert git("rev-parse", f"wt/{e}") == git("rev-parse", "main")
        assert git("worktree", "list") == before
        got = [x for x in comments(e) if "stale-base" in x]
        assert len(got) == 1, comments(e)

        # dir parent: skipped
        dp = card("DP", worktree=False)
        dc = card("DC", dp)
        kb("claim", dp)
        done(dp)
        hook(task_id=dp, board=BOARD)
        assert not git("branch", "--list", f"wt/{dc}") and comments(dc) == []

        # failure never raises
        os.environ["PATH"] = "/nonexistent"
        hook(task_id="t_missing", board=BOARD)
    print("PASS: stacking")


if __name__ == "__main__":
    main()
