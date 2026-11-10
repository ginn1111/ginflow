#!/usr/bin/env python3
"""A git worktree of the configured workspace shares its Ginflow context."""
import importlib.util
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("pc", ROOT / "skills/ginflow/lib/project_config.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def main():
    base = Path(tempfile.mkdtemp(prefix="ginflow-worktree-")).resolve()
    main_tree, worktree, other = base / "main", base / "wt", base / "other"
    for repo in (main_tree, other):
        repo.mkdir()
        git(repo, "init", "-q")
        (repo / ".ginflow.yaml").write_text(f"version: 1\nginflow:\n  board: b\n  workspace: {main_tree}\n")
        git(repo, "add", ".")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    git(main_tree, "worktree", "add", "-q", "-b", "wt", str(worktree))

    assert pc.context_error(main_tree) is None
    assert pc.context_error(worktree) is None, pc.context_error(worktree)
    assert pc.resolve_board(worktree) == "b"
    # A different repository naming this workspace is still a mismatch.
    assert "does not match" in (pc.context_error(other) or "")
    # A plain directory (no git) is still a mismatch.
    plain = base / "plain"
    plain.mkdir()
    (plain / ".ginflow.yaml").write_text((main_tree / ".ginflow.yaml").read_text())
    assert "does not match" in (pc.context_error(plain) or "")
    print("PASS: worktree shares ginflow context")


if __name__ == "__main__":
    main()
