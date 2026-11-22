#!/usr/bin/env python3
"""CLOUD-1.4: `ginflow cards create` against a live temp board and a temp repo."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "skills/ginflow/scripts/ginflow.py"
sys.path.insert(0, str(ROOT / "skills/ginflow/lib"))
import harness_core  # noqa: E402

if not shutil.which("hermes"):
    print("SKIP: ginflow cards (hermes CLI not installed)")
    sys.exit(0)

TMP = Path(tempfile.mkdtemp(prefix="ginflow-cards-")).resolve()
HOME, REPO = TMP / "hermes", TMP / "repo"
for d in (HOME / "profiles/ginb", REPO / "docs/specs", REPO / "docs/plans"):
    d.mkdir(parents=True)
ENV = {k: v for k, v in os.environ.items()
       if not k.startswith("HERMES_KANBAN") and k not in ("HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_SUPERVISED_CHILD", "HERMES_PROFILE")}
ENV.update(HERMES_HOME=str(HOME), HERMES_KANBAN_HOME=str(TMP / "kh"), HERMES_PROFILES_ROOT=str(HOME / "profiles"),
           GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")

SPEC = """---
status: approved
card: {key}
assignee: {assignee}
blocked_by: [{blocked}]
{issue}scope: src/{key}, docs (a, b), tests
owner: ginb
---

# Spec — {key}: Thing {key}

## Problem
Problem for {key}. More text.

## Desired behavior
Do the thing for {key}. Then more.

## Acceptance criteria
- [ ] first check for {key}
- [ ] second check
"""
PLAN = "---\nstatus: approved\ncard: {key}\nscope: x\nowner: ginb\n---\n\n# Plan — {key}\n"


def sh(*argv, cwd=REPO):
    return subprocess.run(argv, cwd=cwd, env=ENV, text=True, capture_output=True)


def ok(*argv):
    r = sh(*argv)
    assert r.returncode == 0, f"{argv}\n{r.stdout}\n{r.stderr}"
    return r.stdout.strip()


def kb(board, *a):
    return ok("hermes", "kanban", "--board", board, *a)


def cards(board):
    return json.loads(kb(board, "list", "--json", "--archived"))


def show(board, tid):
    return json.loads(kb(board, "show", tid, "--json"))


def write(key, blocked="", issue="", assignee="ginb", plan=True):
    (REPO / f"docs/specs/{key}.md").write_text(SPEC.format(key=key, blocked=blocked, assignee=assignee,
                                                           issue=f"issue: {issue}\n" if issue else ""))
    if plan:
        (REPO / f"docs/plans/{key}.md").write_text(PLAN.format(key=key))
    return f"docs/specs/{key}.md"


def commit(msg="specs"):
    ok("git", "add", "docs")
    sh("git", "commit", "-q", "-m", msg)


def create(board, *specs):
    return sh(sys.executable, str(CLI), "cards", "create", "--project", str(REPO), "--board", board, *specs)


def new_board(name, workdir=True):
    args = ["hermes", "kanban", "boards", "create", name]
    ok(*(args + ["--default-workdir", str(REPO)] if workdir else args))
    (REPO / ".ginflow.yaml").write_text(f"ginflow:\n  board: {name}\n  workspace: {REPO}\n")


def refuses(board, specs, needle, before=None):
    before = before if before is not None else cards(board)
    r = create(board, *specs)
    assert r.returncode == 1 and needle in r.stdout, f"{needle!r}: {r.returncode}\n{r.stdout}\n{r.stderr}"
    assert cards(board) == before, "board changed after a failed preflight"


def main():
    ok("hermes", "kanban", "init")
    ok("git", "init", "-q", "-b", "main")
    (REPO / ".hermes.md").write_text("# Rules\nCanonical verification command: `make test`\n"
                                     "Boundaries: shared workflow rules come from `ginflow`; forbidden: secrets.\n")
    (REPO / ".git/info/exclude").write_text(".hermes.md\n.ginflow.yaml\n")
    ok("git", "commit", "-q", "--allow-empty", "-m", "init")

    # graph A, B(A), C(A,B): 3 cards, edges, statuses, parseable bodies
    new_board("bd")
    specs = [write("SHOP-1"), write("SHOP-2", "SHOP-1"), write("SHOP-3", "SHOP-1, SHOP-2")]
    commit()
    r = create("bd", *reversed(specs))
    assert r.returncode == 0, r.stdout + r.stderr
    rows = {x["key"]: x for x in json.loads(r.stdout)}
    assert [x["created"] for x in rows.values()] == [True] * 3, rows
    a, b, c = (rows[k] for k in ("SHOP-1", "SHOP-2", "SHOP-3"))
    assert a["status"] == "ready" and b["status"] == c["status"] == "todo", rows
    assert a["parents"] == [] and b["parents"] == [a["id"]] and sorted(c["parents"]) == sorted([a["id"], b["id"]]), rows
    for row in rows.values():
        task = show("bd", row["id"])["task"]
        f = harness_core.parse_card_body(task["body"])
        assert f["objective"] and f["scope"] and f["acceptance"] and f["links"], task["body"]
        assert task["assignee"] == "ginb" and task["workspace_kind"] == "worktree", task
    f = harness_core.parse_card_body(show("bd", a["id"])["task"]["body"])
    assert f["objective"] == "Do the thing for SHOP-1." and f["scope"] == ["src/SHOP-1", "docs (a, b)", "tests"], f
    assert f["links"] == ["docs/specs/SHOP-1.md", "docs/plans/SHOP-1.md"], f
    assert show("bd", a["id"])["task"]["title"] == "SHOP-1 — Thing SHOP-1", show("bd", a["id"])["task"]["title"]

    # rerun: nothing created, no new cards or edges
    before = cards("bd")
    r = create("bd", *specs)
    assert r.returncode == 0, r.stdout + r.stderr
    again = json.loads(r.stdout)
    assert [x["created"] for x in again] == [False] * 3 and {x["id"] for x in again} == {x["id"] for x in rows.values()}, again
    assert cards("bd") == before
    assert sorted(next(x for x in again if x["key"] == "SHOP-3")["parents"]) == sorted(c["parents"])

    # Issue link + idempotency key; dotted keys
    write("DOT-42.1", issue="o/r#7")
    write("DOT-42.2", "DOT-42.1", issue="o/r#7")
    commit("dots")
    r = create("bd", "docs/specs/DOT-42.2.md", "docs/specs/DOT-42.1.md")
    assert r.returncode == 0, r.stdout + r.stderr
    rows = {x["key"]: x for x in json.loads(r.stdout)}
    assert rows["DOT-42.1"]["status"] == "ready" and rows["DOT-42.2"]["parents"] == [rows["DOT-42.1"]["id"]], rows
    task = show("bd", rows["DOT-42.1"]["id"])["task"]
    assert "https://github.com/o/r/issues/7" in harness_core.parse_card_body(task["body"])["links"], task["body"]
    # the key is not in `show`; creating again with it must return the same card
    dup = sh("hermes", "kanban", "--board", "bd", "create", "x", "--idempotency-key", "gh:o/r#7:DOT-42.1", "--json")
    assert json.loads(dup.stdout)["id"] == rows["DOT-42.1"]["id"], dup.stdout

    # blocked_by naming an existing board card links to it
    write("SHOP-4", "SHOP-3")
    commit("four")
    r = create("bd", "docs/specs/SHOP-4.md")
    assert r.returncode == 0, r.stdout + r.stderr
    row = json.loads(r.stdout)[0]
    assert row["created"] and row["parents"] == [c["id"]], row

    # preflight failures leave the board unchanged
    write("BAD-1", "BAD-2")
    write("BAD-2", "BAD-1")
    commit("cycle")
    refuses("bd", ["docs/specs/BAD-1.md", "docs/specs/BAD-2.md"], "cycle")
    write("BAD-3", "NOPE-9")
    commit("unknown")
    refuses("bd", ["docs/specs/BAD-3.md"], "NOPE-9")
    write("BAD-4", plan=False)
    commit("noplan")
    refuses("bd", ["docs/specs/BAD-4.md"], "missing plan")
    write("BAD-5", assignee="nobody")
    commit("assignee")
    refuses("bd", ["docs/specs/BAD-5.md"], "not an installed Hermes profile")
    write("BAD-6", issue="not-an-issue")
    commit("issue")
    refuses("bd", ["docs/specs/BAD-6.md"], "owner/repo#n")
    write("BAD-7")  # uncommitted
    refuses("bd", ["docs/specs/BAD-7.md"], "not committed")
    commit("seven")
    (REPO / "docs/specs/BAD-7.md").write_text((REPO / "docs/specs/BAD-7.md").read_text() + "\nmore\n")
    refuses("bd", ["docs/specs/BAD-7.md"], "not committed")
    ok("git", "checkout", "docs/specs/BAD-7.md")
    good = write("GOOD-1")
    commit("good")
    refuses("bd", [good, "docs/specs/BAD-4.md"], "BAD-4.md")  # one bad spec blocks the good one too

    # board without default_workdir: exit 1 before any create
    new_board("nodir", workdir=False)
    refuses("nodir", [good], "default_workdir")

    shutil.rmtree(TMP, ignore_errors=True)
    print("PASS: ginflow cards create")


main()
