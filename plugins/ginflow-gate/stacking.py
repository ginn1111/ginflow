"""Stack a child card's worktree branch on its parent branch(es) (STACK-1).

Observer-only `kanban_task_completed` hook. Hermes kwargs (hermes_cli/kanban_db.py `_fire_task_hook`):
task_id, board, assignee, run_id, profile_name, summary. Never raises; never touches the completion.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from . import block_routing, skill_lib

_core = skill_lib.load("harness_core")
_config = skill_lib.load("project_config")
logger = logging.getLogger(__name__)
LIVE = ("running", "done", "archived")


def _git(repo: str | Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, timeout=60)


def _show(task_id: str, board: str | None) -> dict:
    data = _core.kanban_json(board, "show", task_id, "--json")
    return data["task"] | {"parents": data.get("parents") or [], "children": data.get("children") or [],
                           "comments": data.get("comments") or []}


def _branch(task: dict) -> str:
    return (task.get("branch_name") or "").strip() or f"wt/{task['id']}"


def _repo(task: dict) -> Path | None:
    """Main checkout of the repo a worktree card belongs to; None for non-git/dir workspaces."""
    path = str(task.get("workspace_path") or "")
    if task.get("workspace_kind") != "worktree" or not path or not Path(path).is_dir():
        return None
    out = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(out.stdout.strip()).parent if not out.returncode else None


def _has(repo: Path, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}").returncode == 0


def _comment(task_id: str, board: str | None, text: str) -> None:
    _core.kanban_run(board, "comment", task_id, text)


def _stale(repo: Path, child: dict, parents: list[str], board: str | None) -> None:
    branch = _branch(child)
    missing = [p for p in parents if _git(repo, "merge-base", "--is-ancestor", p, branch).returncode]
    if not missing or any(str(c.get("body") or "").startswith("[ginflow-stack] stale-base") for c in child["comments"]):
        return
    message = f"[ginflow-stack] stale-base {branch} lacks {','.join(missing)}"
    _comment(child["id"], board, message)
    target = _config.configured_notify_target(repo)
    destination = target or block_routing._native_destination(child["id"], board)
    if destination:
        block_routing._push(destination, f"Ginflow: card {child['id']} {message}", _config.configured_reviewer(repo))


def _stack(repo: Path, child: dict, parents: list[str], board: str | None) -> None:
    branch, target = _branch(child), repo / ".worktrees" / child["id"]
    added = _git(repo, "worktree", "add", "-b", branch, str(target), parents[0])
    if added.returncode:
        raise RuntimeError(added.stderr.strip())
    if not _git(target, "config", "user.email").stdout.strip():  # merge commits need an identity
        _git(target, "config", "user.email", "ginflow@localhost")
        _git(target, "config", "user.name", "ginflow")
    for other in parents[1:]:
        if _git(target, "merge", "--no-ff", "--no-edit", other).returncode:
            _git(target, "merge", "--abort")
            _comment(child["id"], board, f"[ginflow-stack] conflict {','.join(parents)}")
            _core.kanban_run(board, "block", child["id"], "--kind", "needs_input",
                             f"required_action: resolve merge of {','.join(parents)}")
            return
    head = _git(target, "rev-parse", "--short", "HEAD").stdout.strip()
    _comment(child["id"], board, f"[ginflow-stack] base={','.join(parents)} head={head}")


def stack_child(done_id: str, child_id: str, board: str | None) -> None:
    child = _show(child_id, board)
    if child.get("workspace_kind") != "worktree" or not child["parents"]:
        return
    parents = []
    for pid in child["parents"]:
        parent = _show(pid, board)
        if pid != done_id and parent.get("status") != "done":
            return  # a later parent completion acts
        if parent.get("workspace_kind") != "worktree":
            return
        parents.append((parent, _branch(parent)))
    repo = _repo(parents[0][0]) or _repo(child)
    if not repo or not (repo / ".ginflow.yaml").is_file() or not all(_has(repo, b) for _, b in parents):
        return
    names = [b for _, b in parents]
    if _has(repo, _branch(child)):
        if child.get("status") in LIVE:
            _stale(repo, child, names, board)
        return
    if child.get("status") not in LIVE:
        _stack(repo, child, names, board)


def on_task_completed(task_id: str = "", board: str | None = None, **_: object) -> None:
    try:
        for child_id in _show(task_id, board)["children"]:
            try:
                stack_child(task_id, child_id, board)
            except Exception as exc:
                logger.warning("ginflow stacking %s failed: %s", child_id, exc)
    except Exception as exc:  # observer-only
        logger.warning("ginflow stacking failed: %s", exc)


def register(ctx) -> None:
    ctx.register_hook("kanban_task_completed", on_task_completed)


__all__ = ["on_task_completed", "stack_child", "register"]
