#!/usr/bin/env python3
"""`ginflow cards create`: graph, links, statuses, body round-trip, idempotence, preflight failures."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "skills/ginflow/scripts/ginflow.py"
REAL_HERMES = shutil.which("hermes")
if not REAL_HERMES:
    print("SKIP: ginflow cards (hermes CLI not installed)")
    sys.exit(0)

_s = importlib.util.spec_from_file_location("hc", ROOT / "skills/ginflow/lib/harness_core.py")
hc = importlib.util.module_from_spec(_s)
_s.loader.exec_module(hc)

TMP = Path(tempfile.mkdtemp(prefix="ginflow-cards-")).resolve()
HOME, KANBAN = TMP / "hermes", TMP / "kanban"
for d in (HOME / "profiles" / "ginb", KANBAN):
    d.mkdir(parents=True, exist_ok=True)
ENV = {k: v for k, v in os.environ.items()
       if not k.startswith("HERMES_KANBAN") and k not in ("HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_SUPERVISED_CHILD")}
ENV.update(HERMES_HOME=str(HOME), HERMES_KANBAN_HOME=str(KANBAN), HERMES_PROFILES_ROOT=str(HOME / "profiles"),
           GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def sh(*argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, env=ENV, text=True, capture_output=True)


def git(*args, repo):
    r = sh("git", "-C", str(repo), *args)
    assert r.returncode == 0, r.stderr
    return r


def spec(key, assignee="ginb", blocked=(), plan=True, card=True):
    front = (f"card: {key}\n" if card else "") + f"assignee: {assignee}\nblocked_by: [{', '.join(blocked)}]\nscope: src/{key}\nowner: ginb\n"
    (repo / "docs/specs").mkdir(parents=True, exist_ok=True)
    (repo / "docs/plans").mkdir(parents=True, exist_ok=True)
    path = repo / f"docs/specs/{key}.md"
    path.write_text(f"---\n{front}---\n\n# Spec \u2014 {key}: Do {key}\n\n## Problem\n\nProblem of {key}. More.\n\n"
                    f"## Desired behavior\n\nDo {key} well. Then more.\n\n## Acceptance criteria\n\n- [ ] {key} works\n- [ ] {key} tested\n")
    if plan:
        (repo / f"docs/plans/{key}.md").write_text(f"---\ncard: {key}\n---\n\n# Plan\n")
    return str(path)


def cards(*args):
    r = sh(sys.executable, str(CLI), "cards", "create", "--project", str(repo), "--board", "bd", *args)
    return r.returncode, r.stdout, r.stderr


def board():
    return json.loads(sh("hermes", "kanban", "--board", "bd", "list", "--json").stdout)


assert sh("hermes", "kanban", "init").returncode == 0
origin, repo = TMP / "origin.git", TMP / "proj"
git("init", "-q", "--bare", "-b", "main", str(origin), repo=TMP)
git("init", "-q", "-b", "main", str(repo), repo=TMP)
git("remote", "add", "origin", str(origin), repo=repo)
(repo / ".ginflow.yaml").write_text('ginflow:\n  board: "bd"\n  workspace: "%s"\n' % repo)
(repo / "AGENTS.md").write_text("# T\n\n## Rules\n\n- Boundaries: none. Canonical verification command: `true`\n- Work come from `ginflow`.\n")
git("add", "-A", repo=repo)
git("commit", "-q", "-m", "init", repo=repo)
git("push", "-q", "origin", "main", repo=repo)

# no board workdir: fail before any create
assert sh("hermes", "kanban", "boards", "create", "bd").returncode == 0
A = spec("T-1")
code, out, _ = cards(A)
assert code == 1 and "default_workdir" in out and board() == [], out
assert sh("hermes", "kanban", "boards", "set-default-workdir", "bd", str(repo)).returncode == 0

# preflight failures leave board unchanged
bad = {
    "cycle": [spec("C-1", blocked=["C-2"]), spec("C-2", blocked=["C-1"])],
    "unknown key": [spec("U-1", blocked=["NOPE-9"])],
    "missing plan": [spec("P-1", plan=False)],
    "bad assignee": [spec("S-1", assignee="nobody")],
    "no card key": [spec("K-1", card=False)],
}
for name, paths in bad.items():
    git("add", "-A", repo=repo)
    git("commit", "-q", "--allow-empty", "-m", name, repo=repo)
    code, out, _ = cards(*paths)
    assert code == 1 and out.startswith("fail"), (name, out)
    assert board() == [], (name, board())

# 3-spec graph
for p in repo.glob("docs/*/*.md"):
    if not p.name.startswith("T-"):
        p.unlink()
B, C = spec("T-2", blocked=["T-1"]), spec("T-3", blocked=["T-1", "T-2"])
git("add", "-A", repo=repo)
git("commit", "-q", "-m", "specs", repo=repo)
code, out, err = cards(C, B, A)
assert code == 0, (out, err)
res = {r["key"]: r for r in json.loads(out)}
assert [r["created"] for r in res.values()] == [True] * 3, res
assert {k: r["status"] for k, r in res.items()} == {"T-1": "ready", "T-2": "todo", "T-3": "todo"}, res
assert res["T-3"]["parents"] == ["T-1", "T-2"]
for key, r in res.items():
    shown = json.loads(sh("hermes", "kanban", "--board", "bd", "show", r["id"], "--json").stdout)
    task = shown.get("task", shown)
    body = hc.parse_card_body(task["body"])
    assert body["objective"] and body["scope"] == [f"src/{key}"] and len(body["acceptance"]) == 2 and len(body["links"]) == 2, body
    assert task["title"] == f"{key} \u2014 Do {key}" and task["workspace_kind"] == "worktree" and task["assignee"] == "ginb", task
    want = {"T-1": [], "T-2": ["T-1"], "T-3": ["T-1", "T-2"]}[key]
    assert sorted(shown.get("parents", [])) == sorted(res[k]["id"] for k in want), (key, shown.get("parents"))

# rerun: nothing new
before = json.loads(sh("hermes", "kanban", "--board", "bd", "list", "--json").stdout)
code, out, err = cards(A, B, C)
assert code == 0 and [r["created"] for r in json.loads(out)] == [False] * 3, out
assert board() == before

# blocked_by an existing board card links to it
D = spec("T-4", blocked=["T-3"])
git("add", "-A", repo=repo)
git("commit", "-q", "-m", "d", repo=repo)
code, out, err = cards(D)
assert code == 0, (out, err)
(row,) = json.loads(out)
shown = json.loads(sh("hermes", "kanban", "--board", "bd", "show", row["id"], "--json").stdout)
assert shown.get("parents") == [res["T-3"]["id"]] and row["status"] == "todo", (shown.get("parents"), row)

shutil.rmtree(TMP, ignore_errors=True)
print("PASS: ginflow cards create")
