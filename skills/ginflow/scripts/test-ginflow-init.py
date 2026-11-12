#!/usr/bin/env python3
"""`ginflow init`: fresh setup, idempotence, behind-origin, foreign workdir."""
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
    print("SKIP: ginflow init (hermes CLI not installed)")
    sys.exit(0)

TMP = Path(tempfile.mkdtemp(prefix="ginflow-init-")).resolve()
HOME, KANBAN, SHIM = TMP / "hermes", TMP / "kanban", TMP / "shim"
for d in (HOME, KANBAN, SHIM, HOME / "profiles" / "rev"):
    d.mkdir(parents=True, exist_ok=True)
# Only `gateway status` is faked; everything else reaches the real hermes.
(SHIM / "hermes").write_text(
    f'#!/bin/sh\n[ "$1 $2" = "gateway status" ] && {{ echo "Gateway is running"; exit 0; }}\nexec {REAL_HERMES} "$@"\n')
(SHIM / "hermes").chmod(0o755)
ENV = {k: v for k, v in os.environ.items()
       if not k.startswith("HERMES_KANBAN") and k not in ("HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_SUPERVISED_CHILD")}
ENV.update(HERMES_HOME=str(HOME), HERMES_KANBAN_HOME=str(KANBAN), HERMES_PROFILES_ROOT=str(HOME / "profiles"),
           PATH=f"{SHIM}:{ENV['PATH']}", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def sh(*argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, env=ENV, text=True, capture_output=True)


def git(repo, *args):
    r = sh("git", "-C", str(repo), *args)
    assert r.returncode == 0, r.stderr
    return r


def init(*args):
    r = sh(sys.executable, str(CLI), "init", *args)
    return r.returncode, r.stdout.strip().splitlines()


def make_project(name):
    origin, repo = TMP / f"{name}-origin.git", TMP / name
    git(TMP, "init", "-q", "--bare", "-b", "main", str(origin))
    git(TMP, "init", "-q", "-b", "main", str(repo))
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    git(repo, "push", "-q", "origin", "main")
    return repo, origin


def boards():
    import json
    return {b["slug"]: b for b in json.loads(sh("hermes", "kanban", "boards", "list", "--json").stdout)}


assert sh("hermes", "kanban", "init").returncode == 0
repo, origin = make_project("proj")

# fresh
code, lines = init("--project", str(repo), "--new-board", "bd", "--reviewer", "rev")
assert code == 0, lines
assert boards()["bd"]["default_workdir"] == str(repo), boards()["bd"]
cfg = (repo / ".ginflow.yaml").read_text()
assert "board:" in cfg and "bd" in cfg and "rev" in cfg, cfg
hermes_cfg = (HOME / "config.yaml").read_text()
assert "default_reviewer_profile: rev" in hermes_cfg, hermes_cfg
assert not any(l.startswith("fail") for l in lines), lines

# second run: only ok, nothing rewritten
code, lines = init("--project", str(repo))
assert code == 0 and all(l.startswith("ok ") for l in lines), lines
assert (repo / ".ginflow.yaml").read_text() == cfg and (HOME / "config.yaml").read_text() == hermes_cfg

# behind origin
other = TMP / "other"
git(TMP, "clone", "-q", str(origin), str(other))
git(other, "commit", "-q", "--allow-empty", "-m", "two")
git(other, "push", "-q", "origin", "main")
code, lines = init("--project", str(repo))
assert code == 1 and "fail main: behind origin/main by 1" in lines, lines

# board workdir pointing elsewhere: fail, nothing rewritten
repo2, _ = make_project("proj2")
assert sh("hermes", "kanban", "boards", "create", "foreign", "--default-workdir", str(TMP / "elsewhere")).returncode == 0
code, lines = init("--project", str(repo2), "--board", "foreign", "--reviewer", "rev")
assert code == 1 and any(l.startswith("fail workdir") for l in lines), lines
assert not (repo2 / ".ginflow.yaml").exists()
assert boards()["foreign"]["default_workdir"] == str(TMP / "elsewhere")

# neither --board nor --new-board
repo3, _ = make_project("proj3")
code, lines = init("--project", str(repo3))
assert code == 1 and any(l.startswith("fail context") for l in lines), lines
assert not (repo3 / ".ginflow.yaml").exists()

shutil.rmtree(TMP, ignore_errors=True)
print("PASS: ginflow init")
