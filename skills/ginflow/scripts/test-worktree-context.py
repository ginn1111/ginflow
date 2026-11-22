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
        (repo / ".ginflow.yaml").write_text(f"ginflow:\n  board: b\n  workspace: {main_tree}\n")
        git(repo, "add", ".")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    git(main_tree, "worktree", "add", "-q", "-b", "wt", str(worktree))

    assert pc.context_error(main_tree) is None
    assert pc.context_error(worktree) is None, pc.context_error(worktree)
    # Empty env: Kanban workers export HERMES_KANBAN_BOARD, which outranks project config.
    assert pc.resolve_board(worktree, env={}) == "b"
    # A different repository naming this workspace is still a mismatch.
    assert "does not match" in (pc.context_error(other) or "")
    # A plain directory (no git) is still a mismatch.
    plain = base / "plain"
    plain.mkdir()
    (plain / ".ginflow.yaml").write_text((main_tree / ".ginflow.yaml").read_text())
    assert "does not match" in (pc.context_error(plain) or "")
    print("PASS: worktree shares ginflow context")
    untracked_main_checkout(base)


def untracked_main_checkout(base):
    """CLOUD-1.1: untracked config in the main checkout serves its worktrees."""
    main_tree, worktree, own = base / "m2", base / "m2-wt", base / "m2-own"
    main_tree.mkdir()
    git(main_tree, "init", "-q")
    git(main_tree, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
    git(main_tree, "worktree", "add", "-q", "-b", "wt2", str(worktree))
    git(main_tree, "worktree", "add", "-q", "-b", "wt3", str(own))
    cfg = main_tree / ".ginflow.yaml"
    cfg.write_text(f"ginflow:\n  board: mb\n  workspace: {main_tree}\n")
    assert not (worktree / ".ginflow.yaml").exists()
    assert pc.config_exists(worktree) and pc.config_path(worktree) == cfg
    assert pc.context_error(worktree) is None, pc.context_error(worktree)
    assert pc.configured_context(worktree) == pc.configured_context(main_tree) == {"board": "mb", "workspace": str(main_tree)}
    assert pc.resolve_board(worktree, env={}) == "mb"
    assert pc.persist_worker_defaults(worktree, profile="p", provider="q", model="m") == cfg
    assert pc.configured_worker(main_tree) == {"profile": "p", "provider": "q", "model": "m"}
    assert not (worktree / ".ginflow.yaml").exists()
    # legacy: a worktree's own file wins
    (own / ".ginflow.yaml").write_text(f"ginflow:\n  board: own\n  workspace: {main_tree}\n")
    assert pc.config_path(own) == own / ".ginflow.yaml" and pc.resolve_board(own, env={}) == "own"
    # not a git repo: only W/.ginflow.yaml
    plain = base / "plain2"
    plain.mkdir()
    assert not pc.config_exists(plain) and pc.config_path(plain) == plain / ".ginflow.yaml"
    print("PASS: untracked main-checkout config resolves in worktrees")


if __name__ == "__main__":
    main()
