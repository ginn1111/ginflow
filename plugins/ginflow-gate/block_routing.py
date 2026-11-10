"""Push critical worker blocks to ginflow.notify.target via `hermes send`.

Observer-only kanban_task_blocked hook. Any failure is swallowed so the block
transition is never affected. Destination chain: notify.target, else the task's
native notify subscription, else (or on push failure) a card comment.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import subprocess
from pathlib import Path

CRITICAL_KINDS = frozenset({"needs_input", "capability"})
VALID_KINDS = ("needs_input", "capability", "transient", "dependency")
_REQUIRED_ACTION = re.compile(r"(?im)^\s*required_action:[ \t]*(\S.*)$")
_REPAIR_MARKER = "[ginflow] origin=worker"
MAX_BODY = 800
logger = logging.getLogger(__name__)

_spec = importlib.util.spec_from_file_location(
    "ginflow_project_config", Path(__file__).resolve().parents[2] / "skills/ginflow/lib/project_config.py"
)
_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_config)


def _sanitize(text: object) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:MAX_BODY]


def _trace_on(workspace: Path) -> bool:
    flag = os.environ.get("GINFLOW_LOG")
    if flag is not None:
        return flag == "1"
    context = _config.load_config(workspace).get("ginflow")
    return isinstance(context, dict) and context.get("trace") is True


def _load_task(task_id: str, board: str | None) -> dict:
    command = ["hermes", "kanban"] + (["--board", board] if board else []) + ["show", task_id, "--json"]
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "unable to read task")
    data = json.loads(result.stdout)
    task = data["task"]
    task["comments"] = data.get("comments") or []
    # `show --json` omits tasks.block_kind; the latest block event carries it.
    if not task.get("block_kind"):
        for event in reversed(data.get("events") or []):
            if event.get("kind") in ("blocked", "dependency_wait"):
                task["block_kind"] = (event.get("payload") or {}).get("kind")
                break
    return task


def _native_destination(task_id: str, board: str | None) -> str | None:
    command = ["hermes", "kanban"] + (["--board", board] if board else []) + ["notify-list", "--json", task_id]
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    if result.returncode:
        return None
    for sub in json.loads(result.stdout or "[]"):
        if sub.get("platform") and sub.get("chat_id"):
            return ":".join(str(sub[k]) for k in ("platform", "chat_id", "thread_id") if sub.get(k))
    return None


def _push(destination: str, message: str) -> bool:
    # Inherits worker HERMES_HOME, so send runs under the worker's profile (B6).
    try:
        return subprocess.run(["hermes", "send", "--to", destination, "-q", message],
                              text=True, capture_output=True, timeout=60).returncode == 0
    except Exception as exc:
        logger.warning("ginflow block push failed: %s", exc)
        return False


def _comment(task_id: str, board: str | None, message: str) -> None:
    command = ["hermes", "kanban"] + (["--board", board] if board else []) + ["comment", task_id, message]
    subprocess.run(command, text=True, capture_output=True, timeout=30)


def _route_repairable(task_id: str, board: str | None, profile: object, run_id: object, reason: object) -> None:
    """Transient block: origin=worker comment, assign gintary, unblock."""
    _comment(task_id, board, _sanitize(
        f"[ginflow] origin=worker profile={_sanitize(profile) or 'unknown'} run={run_id} "
        f"kind=transient reason={_sanitize(reason) or '(no reason given)'}"))
    base = ["hermes", "kanban"] + (["--board", board] if board else [])
    for step in (["assign", task_id, "gintary"], ["unblock", task_id]):
        subprocess.run(base + step, text=True, capture_output=True, timeout=30)


def guard_block(args: dict, task_id: str = "", **_: object) -> dict | None:
    """pre_tool_call guard for kanban_block (trace on only). Inactive on lookup errors."""
    try:
        selected = str(args.get("task_id") or task_id or os.environ.get("HERMES_KANBAN_TASK") or "").strip()
        board = args.get("board") or os.environ.get("HERMES_KANBAN_BOARD")
        workspace = str(_load_task(selected, board).get("workspace_path") or "")
        if not workspace or not _trace_on(Path(workspace)):
            return None
    except Exception as exc:
        logger.warning("ginflow block guard inactive: %s", exc)
        return None
    kind = args.get("kind")
    if kind not in VALID_KINDS:
        return {"action": "block", "message": (
            f"ginflow-gate: kanban_block requires kind, one of: {', '.join(VALID_KINDS)} (got {kind!r})")}
    if kind in CRITICAL_KINDS and not _REQUIRED_ACTION.search(str(args.get("reason") or "")):
        return {"action": "block", "message": (
            f"ginflow-gate: kanban_block kind={kind} requires a `required_action:` line in reason "
            "stating what the human must do")}
    return None


def build_message(task_id: str, reason: object, profile: object, run_id: object) -> str:
    match = _REQUIRED_ACTION.search(str(reason or ""))
    action = _sanitize(match.group(1)) if match else ""
    reason = _sanitize(reason) or "(no reason given)"
    return _sanitize(
        f"Ginflow block: task {task_id} needs a human. Reason: {reason}. "
        f"Required action: {action or reason}. Worker: {_sanitize(profile) or 'unknown'}. Run: {run_id}."
    )


def on_task_blocked(task_id: str = "", board: str | None = None, assignee: str | None = None,
                    run_id: int | None = None, reason: str | None = None, **_: object) -> None:
    try:
        task = _load_task(task_id, board)
        workspace = str(task.get("workspace_path") or "")
        kind = task.get("block_kind")
        if not workspace or kind not in CRITICAL_KINDS | {"transient"}:
            return
        path = Path(workspace)
        if not _trace_on(path):
            return
        if kind == "transient":
            # Prior auto-repair marker lives on the card; a repeat becomes critical (no reassign).
            if not any(str(c.get("body") or "").startswith(_REPAIR_MARKER) for c in task["comments"]):
                _route_repairable(task_id, board, assignee or task.get("assignee"), run_id, reason)
                return
        error = _config.context_error(path)
        if error:
            logger.warning("ginflow block routing: invalid project config route: %s", error)
            return
        target = _config.configured_notify_target(path)
        message = build_message(task_id, reason, assignee or task.get("assignee"), run_id)
        try:
            destination = target or _native_destination(task_id, board)
        except Exception as exc:
            logger.warning("ginflow block routing: subscription lookup failed: %s", exc)
            destination = None
        if destination and _push(destination, message):
            return
        _comment(task_id, board, f"[ginflow] {'push failed' if destination else 'no notify destination'}: {message}")
    except Exception as exc:  # observer-only: never break the block transition
        logger.warning("ginflow block routing failed: %s", exc)


def _pre_tool_call(tool_name: str, args: dict, task_id: str = "", **kwargs: object) -> dict | None:
    return guard_block(args, task_id) if tool_name == "kanban_block" else None


def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("kanban_task_blocked", on_task_blocked)
