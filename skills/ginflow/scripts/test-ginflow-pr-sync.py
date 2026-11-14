#!/usr/bin/env python3
"""PRFB-1: `ginflow pr sync` against a live temp board, a temp repo and a stub `gh`."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "skills/ginflow/scripts/ginflow.py"
if not shutil.which("hermes"):
    print("SKIP: ginflow pr sync (hermes CLI not installed)")
    sys.exit(0)

BOARD = "ginflow-prsync"
URL = "https://example.test/o/r/pull/7"
BODY = "Objective: parent\nScope:\n- src/x\nAcceptance:\n- done\nLinks:\n- docs/specs/X-1.md"
STUB = r'''#!/bin/sh
echo "gh $*" >> "$FAKE_DIR/calls.log"
case "$1 $2" in
  "pr view") cat "$FAKE_DIR/pr.json" ;;
  "api repos/o/r/pulls/7/comments") cat "$FAKE_DIR/inline.json" ;;
  *) exit 1 ;;
esac
'''


def iso(offset=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="ginflow-prsync-")).resolve()
    fake, bin_dir, repo = tmp / "fake", tmp / "bin", tmp / "repo"
    for d in (fake, bin_dir, repo, tmp / "home/profiles/test"):
        d.mkdir(parents=True)
    (bin_dir / "gh").write_text(STUB)
    (bin_dir / "gh").chmod(0o755)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HERMES_KANBAN") and k not in ("HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_SUPERVISED_CHILD", "HERMES_PROFILE")}
    env.update(HERMES_HOME=str(tmp / "home/profiles/test"), HERMES_KANBAN_HOME=str(tmp / "kh"), HERMES_KANBAN_BOARD=BOARD,
               PATH=f"{bin_dir}:{env['PATH']}", FAKE_DIR=str(fake))

    def sh(*argv, cwd=repo):
        return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)

    def ok(*argv):
        r = sh(*argv)
        assert r.returncode == 0, f"{argv}\n{r.stdout}\n{r.stderr}"
        return r.stdout.strip()

    def kb(*a):
        return ok("hermes", "kanban", "--board", BOARD, *a)

    def show(tid):
        return json.loads(kb("show", tid, "--json"))

    def sync():
        r = sh(sys.executable, str(CLI), "pr", "sync", "--board", BOARD)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout

    def stub(reviews=(), comments=(), inline=(), state="OPEN"):
        (fake / "pr.json").write_text(json.dumps({"state": state, "headRefName": "wt/t_parent", "reviews": list(reviews),
                                                  "comments": list(comments)}))
        (fake / "inline.json").write_text(json.dumps(list(inline)))

    def fb_cards():
        return [t for t in json.loads(kb("list", "--json", "--archived")) if "-fb" in t["title"]]

    ok("hermes", "kanban", "init")
    kb_boards = ok("hermes", "kanban", "boards", "create", BOARD)
    ok("git", "init", "-q", "-b", "main")
    parent = json.loads(kb("create", "P-1 — parent", "--body", BODY, "--assignee", "ginb", "--workspace", f"dir:{repo}", "--json"))["id"]
    kb("claim", parent)
    kb("complete", parent, "--summary", "ok")
    kb("comment", parent, f"ginflow-publish: {URL}")
    time.sleep(2)

    review = {"author": {"login": "gin"}, "body": "please rename", "state": "CHANGES_REQUESTED", "submittedAt": iso(-1)}
    inline = {"user": {"login": "gin"}, "path": "src/x.py", "line": 12, "body": "use stdlib", "created_at": iso(-1)}
    own = {"author": {"login": "gin"}, "body": "[ginflow] updated abc1234 by P-1", "createdAt": iso(-1)}

    # review + inline (+ ignored [ginflow] comment): one fb card, ready, linked, branch = PR head, marker on parent
    stub(reviews=[review], comments=[own], inline=[inline])
    sync()
    cards = fb_cards()
    assert len(cards) == 1, cards
    fb = show(cards[0]["id"])
    assert fb["task"]["title"] == "P-1-fb1 — PR #7 feedback", fb["task"]["title"]
    assert fb["task"]["branch_name"] == "wt/t_parent" and fb["task"]["status"] == "ready", fb["task"]
    assert fb["parents"] == [parent], fb["parents"]
    body = fb["task"]["body"]
    assert "gin review: please rename" in body and "gin src/x.py:12: use stdlib" in body and "[ginflow] updated" not in body, body
    assert "- src/x" in body and "- docs/specs/X-1.md" in body and "`make lint test` passes" in body, body
    markers = [c["body"] for c in show(parent)["comments"] if c["body"].startswith("[ginflow-pr] synced=")]
    assert len(markers) == 1 and markers[0].endswith("items=2"), markers
    fid = cards[0]["id"]

    # rerun, nothing new: no card, no marker
    sync()
    assert len(fb_cards()) == 1
    assert len([c for c in show(parent)["comments"] if c["body"].startswith("[ginflow-pr] synced=")]) == 1

    # new comment while fb card open: appended, no second card
    time.sleep(2)
    stub(reviews=[review], comments=[{"author": {"login": "gin"}, "body": "one more thing", "createdAt": iso(-1)}, own], inline=[inline])
    sync()
    assert len(fb_cards()) == 1
    appended = [c["body"] for c in show(fid)["comments"] if c["body"].startswith("[ginflow-pr] new feedback")]
    assert len(appended) == 1 and "one more thing" in appended[0] and "use stdlib" not in appended[0], appended
    assert len([c for c in show(parent)["comments"] if c["body"].startswith("[ginflow-pr] synced=")]) == 2

    # gh failure: reported, exit 1
    (fake / "pr.json").write_text("not json")
    r = sh(sys.executable, str(CLI), "pr", "sync", "--board", BOARD)
    assert r.returncode == 1 and f"fail {parent}" in r.stdout, r.stdout

    # merged PR: marker, then no more gh calls for it
    stub(state="MERGED")
    sync()
    assert any(c["body"] == "[ginflow-pr] merged" for c in show(parent)["comments"])
    calls = (fake / "calls.log").read_text()
    sync()
    assert (fake / "calls.log").read_text() == calls
    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: ginflow pr sync")


main()
