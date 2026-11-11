"""Auto-publish a reviewed worktree branch as MR/PR on reviewer kanban_complete (GINFLOW-MR-1).

pre_tool_call -> prepare(): fail closed (auth, branch) and remember what to publish.
post_tool_call -> finish(): push exact commit, reuse or create MR/PR, comment URL. Never raises.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from . import skill_lib
core = skill_lib.load("publish")
_kanban = skill_lib.load("harness_core")

_PENDING: dict[str, dict[str, Any]] = {}
_AUTH_OK: set[tuple[str, str]] = set()


def _run(argv: list[str], cwd: str | Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def active_profile(kwargs: dict | None = None) -> str | None:
    if kwargs and kwargs.get("profile"):
        return str(kwargs["profile"])
    home = Path(os.environ.get("HERMES_HOME", "")).expanduser()
    return home.name if home.parent.name == "profiles" else None


def auth_error(config: dict[str, Any], cwd: str | Path | None = None) -> str | None:
    """None when the configured provider CLI is authenticated; cached on success."""
    key = (config["provider"], config.get("host") or "")
    if key in _AUTH_OK:
        return None
    argv = core.build_auth_argv(config["provider"]) + (["--hostname", config["host"]] if config.get("host") else [])
    try:
        result = _run(argv, cwd=cwd, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        return f"publish CLI unavailable: {' '.join(argv)}: {error}"
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return f"publish CLI unauthenticated: {' '.join(argv)} exited {result.returncode}" + (f": {detail[-1]}" if detail else "")
    _AUTH_OK.add(key)
    return None


def _show(task_id: str, board: str | None) -> dict:
    return _kanban.kanban_json(board, "show", task_id, "--json")["task"]


def _body(card: dict, metadata: dict) -> str:
    verification = metadata.get("verification_result") or {}
    acceptance = card.get("acceptance") or []
    lines = [f"Kanban card: {card.get('id')}", "", f"Objective: {card.get('objective')}", "", "Acceptance:"]
    lines += [f"- {item}" for item in (acceptance if isinstance(acceptance, list) else [acceptance])]
    lines += ["", "Verification:", f"- command: `{verification.get('command')}`",
              f"- result: {verification.get('result')}", f"- commit: {verification.get('commit')}"]
    return "\n".join(lines)


_PUBLISHED = re.compile(r"^ginflow-publish: (https?://\S+)(?: \(updated\))?$")


def _open_parent_prs(parents: list[str], board: str | None, config: dict[str, Any], cwd: Path) -> list[tuple[str, str]]:
    """(branch, url) per parent whose published GitHub PR is still open. Best effort."""
    found = []
    if config["provider"] != "github":
        return found
    for pid in parents:
        data = _kanban.kanban_json(board, "show", pid, "--json")
        urls = [m.group(1) for c in data.get("comments") or [] if (m := _PUBLISHED.match(str(c.get("body") or "")))]
        branch = (data["task"].get("branch_name") or "").strip() or f"wt/{pid}"
        if urls and _run(["gh", "pr", "view", urls[-1], "--json", "state", "-q", ".state"], cwd=cwd, timeout=30).stdout.strip() == "OPEN":
            found.append((branch, urls[-1]))
    return found


def base_and_body(task_id: str, board: str | None, config: dict[str, Any], cwd: Path, body: str) -> tuple[str, str]:
    """Stack the PR on the single open parent PR branch; else target + `Merge after:` list."""
    try:
        parents = _kanban.kanban_json(board, "show", task_id, "--json").get("parents") or []
        open_prs = _open_parent_prs(parents, board, config, cwd) if parents else []
    except Exception:  # ponytail: lookup failure falls back to the configured target
        return config["target"], body
    if len(parents) == 1 and open_prs:
        return open_prs[0][0], body
    if open_prs:
        body += "\n\nMerge after: " + ", ".join(url for _, url in open_prs)
    return config["target"], body


def prepare(task_id: str, card: dict, metadata: dict, board: str | None, project_config: Any, kwargs: dict) -> str | None:
    """Block message when publish is required but impossible; else None (and remember the job)."""
    workspace = str(card.get("workspace") or "")
    if not workspace.startswith("worktree:"):
        return None
    path = Path(workspace.removeprefix("worktree:"))
    error = project_config.publish_error(path)
    if error:
        return error
    config = project_config.configured_publish(path)
    reviewer = project_config.configured_reviewer(path)
    if not config or not reviewer or active_profile(kwargs) != reviewer:
        return None
    branch = _show(task_id, board).get("branch_name")
    if not branch:
        return "publish requires branch_name on the worktree card"
    error = auth_error(config, cwd=path)
    if error:
        return error + "; fix CLI auth, then retry kanban_complete"
    common = _run(["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"], timeout=10)
    if common.returncode:
        return f"publish cannot resolve git dir for {path}"
    commit = metadata["verification_result"]["commit"]
    # Fail closed on bad input before completion, not after.
    core.build_push_argv(str(path), config["remote"], commit, branch)
    core.build_create_argv(config["provider"], branch, config["target"], str(card.get("title")), "x")
    base, body = base_and_body(task_id, board, config, path, _body(card, metadata))
    core.build_create_argv(config["provider"], branch, base, str(card.get("title")), "x")
    _PENDING[task_id] = {"worktree": str(path), "git_dir": common.stdout.strip(), "branch": branch, "commit": commit,
                         "config": config, "board": board, "title": str(card.get("title")),
                         "body": body, "base": base}
    return None


def _failed(result: Any, kwargs: dict) -> bool:
    if kwargs.get("status") == "error":
        return True
    try:
        data = json.loads(result) if isinstance(result, str) else result
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and (data.get("ok") is False or bool(data.get("error")))


def publish(job: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (url, error)."""
    config, worktree = job["config"], Path(job["worktree"])
    # Hermes removes a worktree on completion only once pushed; the shared git dir always has the branch.
    push_dir = str(worktree) if worktree.is_dir() else job["git_dir"]
    cwd = worktree if worktree.is_dir() else Path(job["git_dir"]).parent
    argv = core.build_push_argv(push_dir, config["remote"], job["commit"], job["branch"])
    result = _run(argv, cwd=cwd)
    if result.returncode:
        return None, f"{' '.join(argv)}: {(result.stderr or result.stdout).strip()}"
    existing = _run(core.build_existing_argv(config["provider"], job["branch"]), cwd=cwd)
    url = core.parse_existing_url(config["provider"], existing.stdout) if not existing.returncode else None
    if url:
        job["updated"] = True
        if config["provider"] == "github":  # best effort; the push already landed
            key = job["title"].split(" — ")[0].strip()
            _run(["gh", "pr", "comment", url, "--body", f"[ginflow] updated {job['commit'][:7]} by {key}"], cwd=cwd, timeout=30)
        return url, None
    argv = core.build_create_argv(config["provider"], job["branch"], job["base"], job["title"], job["body"], config["draft"])
    result = _run(argv, cwd=cwd)
    url = core.parse_created_url(result.stdout) if not result.returncode else None
    if not url:
        return None, f"{' '.join(argv[:3])}: {(result.stderr or result.stdout).strip() or 'no MR URL in output'}"
    return url, None


def _comment(task_id: str, board: str | None, text: str) -> None:
    _kanban.kanban_run(board, "comment", task_id, text)


def finish(task_id: str, result: Any, kwargs: dict) -> None:
    job = _PENDING.pop(task_id, None)
    if not job or _failed(result, kwargs):
        return
    try:
        url, error = publish(job)
    except Exception as exc:  # observer: never break the completed transition
        url, error = None, f"unexpected error: {exc}"
    try:
        _comment(task_id, job["board"], f"ginflow-publish: {url}" + (" (updated)" if job.get("updated") else "") if url else f"ginflow-publish failed: {error}")
    except Exception:
        pass


__all__ = ["active_profile", "auth_error", "prepare", "publish", "finish"]
