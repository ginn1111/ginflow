"""Notify the configured destination for actionable Kanban blocks."""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path

CRITICAL_KINDS = frozenset({"needs_input", "capability"})
VALID_KINDS = ("needs_input", "capability", "transient", "dependency")
_REQUIRED_ACTION = re.compile(r"(?im)^\s*required_action:[ \t]*(\S.*)$")
MAX_BODY = 800
logger = logging.getLogger(__name__)

from . import alert_outbox, blocker_reporting, feedback, recovery_policy, skill_lib
from .card_id import selected_task_id
from .trace_adapter import trace
_config = skill_lib.load("project_config")
_core = skill_lib.load("harness_core")


def _sanitize(text: object) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:MAX_BODY]


def _telegram_home() -> str | None:
    """Use Hermes' Telegram home-channel alias; no Ginflow credentials are stored."""
    return "telegram"


def _load_task(task_id: str, board: str | None) -> dict:
    data = _core.kanban_json(board, "show", task_id, "--json")
    task = data["task"]
    task["comments"] = data.get("comments") or []
    # `show --json` omits tasks.block_kind; the latest block event carries it.
    if not task.get("block_kind"):
        for event in reversed(data.get("events") or []):
            if event.get("kind") in ("blocked", "block_loop_detected", "dependency_wait"):
                task["block_kind"] = (event.get("payload") or {}).get("kind")
                break
    return task


def _native_destination(task_id: str, board: str | None) -> str | None:
    result = _core.kanban_run(board, "notify-list", "--json", task_id)
    if result.returncode:
        return None
    for sub in json.loads(result.stdout or "[]"):
        if sub.get("platform") and sub.get("chat_id"):
            return ":".join(str(sub[k]) for k in ("platform", "chat_id", "thread_id") if sub.get(k))
    return None


def _push(destination: str, message: str, profile: str | None = None) -> bool:
    # Run as the reviewer profile when configured: the blocked worker may lack gateway credentials.
    argv = ["hermes", *(["-p", profile] if profile else []), "send", "--to", destination, "-q", message]
    try:
        return subprocess.run(argv, text=True, capture_output=True, timeout=60).returncode == 0
    except Exception as exc:
        logger.warning("ginflow block push failed: %s", exc)
        return False


def _comment(task_id: str, board: str | None, message: str) -> None:
    _core.kanban_run(board, "comment", task_id, message)


_RECOVERY_KEY = re.compile(r"^\[ginflow-recovery\] event=(\S+)")


@trace
def _record_feedback(event: dict) -> dict:
    """Trace-only record of one handled block; nothing else is persisted."""
    return event


def _feedback(task_id: str, event_id: str, decision: recovery_policy.RecoveryDecision, status: str) -> None:
    signal = "recovered" if decision.action == "reassign" else (
        "retry_exhausted" if status == "triage" else "blocked")
    _record_feedback(feedback.build_feedback_event(
        event_id=f"{event_id.replace(':', '-')}-{decision.action}", task_id=task_id, work_mode="recovery",
        signal=signal, result="recovered" if signal == "recovered" else "blocked",
        reason=f"{decision.action}/{decision.reason}", evidence=[f"status={status}"]))


def _reassign(task_id: str, board: str | None, event: dict, reviewer: str) -> None:
    """First transient block: recovery comment, assign reviewer, unblock; failure leaves card blocked."""
    _comment(task_id, board, blocker_reporting.blocker_comment(event, decision="reassign", reason="recoverable_blocker"))
    for step in (("assign", task_id, reviewer), ("unblock", task_id)):
        if _core.kanban_run(board, *step).returncode:
            _comment(task_id, board, blocker_reporting.blocker_comment(
                event, decision="reassign", reason="reassign_failed"))
            return


def guard_block(args: dict, task_id: str = "", **_: object) -> dict | None:
    """pre_tool_call guard for kanban_block (trace on only). Inactive on lookup errors."""
    try:
        selected = selected_task_id(args, task_id)
        board = args.get("board") or os.environ.get("HERMES_KANBAN_BOARD")
        workspace = str(_load_task(selected, board).get("workspace_path") or "")
        if not workspace:
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
    fixability = "No" if action else "Unknown"
    card_link = ""
    first = _sanitize(f"[HIGH] {task_id} blocked — {reason}. Agent can fix: {fixability}. {card_link}")
    second = _sanitize(f"Your action: {action or 'Provide the missing information so the next step can be decided.'}")
    return f"{first}\n{second}"


def _processed_keys(task: dict) -> set[str]:
    keys = set()
    for c in task["comments"]:
        match = _RECOVERY_KEY.match(str(c.get("body") or ""))
        if match:
            keys.add(f"{task['id']}:{match.group(1)}")
    return keys


def on_task_blocked(task_id: str = "", board: str | None = None, assignee: str | None = None,
                    run_id: int | None = None, reason: str | None = None, **_: object) -> None:
    try:
        task = _load_task(task_id, board)
        workspace = str(task.get("workspace_path") or "")
        kind = task.get("block_kind")
        if not workspace or kind in (None, "dependency"):
            return
        path = Path(workspace)
        error = _config.context_error(path)
        if error:
            logger.warning("ginflow block routing: invalid project config route: %s", error)
            return
        worker = assignee or task.get("assignee")
        status = str(task.get("status") or "")
        # `show --json` omits block_recurrences; Hermes sets triage exactly at the limit.
        recurrences = int(task.get("block_recurrences") or (blocker_reporting.BLOCK_RECURRENCE_LIMIT if status == "triage" else 1))
        reviewer = _config.configured_reviewer(path)
        try:
            event = blocker_reporting.build_blocker_event(
                event_id=f"{run_id}:{recurrences}", card_id=task_id, workspace=workspace,
                previous_assignee=str(worker or ""), blocker_kind=str(kind), error_summary=_sanitize(reason) or "no reason",
                evidence=[f"block_kind={kind}"], attempted_commands=["kanban_block"],
                recurrences=recurrences, status=status if status in blocker_reporting.STATUSES else "blocked")
            decision = recovery_policy.evaluate_recovery(
                event, current_card_id=task_id, current_workspace=workspace,
                current_assignee=task.get("assignee"), current_status=status,
                reviewer=reviewer, processed_keys=_processed_keys(task | {"id": task_id}))
        except ValueError:  # unknown kind / bad fields: fail closed, still tell a human
            event = {"event_id": f"{run_id}:{recurrences}"}
            decision = recovery_policy.RecoveryDecision("stay_blocked", "malformed_safety_state", 0)
        _feedback(task_id, event["event_id"], decision, status)
        if decision.action == "reassign":
            _reassign(task_id, board, event, str(decision.target_assignee))
            refreshed = _load_task(task_id, board)
            if refreshed.get("assignee") == str(decision.target_assignee) and refreshed.get("status") not in ("blocked", "triage"):
                return
            decision = recovery_policy.RecoveryDecision("notify_human", "reassign_failed", decision.recurrences)

        if not (decision.action == "notify_human" or decision.reason == "malformed_safety_state"):
            logger.info("ginflow block routing: %s/%s", decision.action, decision.reason)
            return
        target = _config.configured_notify_target(path)
        message = build_message(task_id, reason, worker, run_id)
        destinations = [target] if target else []
        home = _telegram_home()
        if home and home not in destinations:
            destinations.append(home)
        def deliver(text: str) -> bool:
            return any(_push(destination, text, reviewer) for destination in destinations)
        if board:
            alert_outbox.enqueue(str(board), task_id, str(decision.reason), message, deliver)
        elif not deliver(message):
            _comment(task_id, board, f"[ginflow] {'push failed' if destinations else 'no notify destination'}: {message}")
    except Exception as exc:  # observer-only: never break the block transition
        logger.warning("ginflow block routing failed: %s", exc)


def _pre_tool_call(tool_name: str, args: dict, task_id: str = "", **kwargs: object) -> dict | None:
    return guard_block(args, task_id) if tool_name == "kanban_block" else None


def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("kanban_task_blocked", on_task_blocked)
