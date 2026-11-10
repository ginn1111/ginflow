"""Inject Kanban board state before LLM calls to route ginflow agents.

When ginflow skill is loaded, this plugin runs on every pre_llm_call hook
and injects the current Kanban board snapshot — card count, titles, statuses —
so the agent can route itself to work shaping (no cards) or resume (cards exist).

When ginflow skill is NOT loaded, the plugin is a no-op — no subprocess call,
no context injection.

The injected context is ephemeral (per-turn) and never persisted to the session DB.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from .trace_adapter import trace
from . import skill_lib


_core = skill_lib.load("harness_core")
startup_gate = _core.startup_gate
_routing_core = skill_lib.load("routing")
_route_policy = _routing_core.route
_workspace = _routing_core.workspace
_resolve_board = _core.resolve_board
_context_error = _core.context_error
_config_exists = _core.config_exists
_publish_config = skill_lib.load("project_config")
from . import publish as _publish



logger = logging.getLogger(__name__)


def _parse_skill_list(raw: str) -> set[str]:
    """Parse comma/newline-delimited skill env values into canonical names."""
    names: set[str] = set()
    for part in raw.replace("\n", ",").split(","):
        item = part.strip()
        if item:
            names.add(item)
    return names


def _ginflow_loaded() -> bool:
    """Check if ginflow skill is active in current session."""
    try:
        import os

        active = _parse_skill_list(os.environ.get("HERMES_TUI_SKILLS", ""))
        return "ginflow" in active
    except Exception:
        return False


def _route(tasks: list[dict[str, Any]], explicit_id: str | None = None) -> dict[str, Any]:
    """Inject Hermes cwd into core routing policy."""
    return _route_policy(tasks, Path.cwd(), explicit_id)


def _publish_route(current: Path) -> tuple[str, str] | None:
    """Startup check: configured publish CLI must be authenticated before work starts."""
    error = _publish_config.publish_error(current)
    config = None if error else _publish_config.configured_publish(current)
    if not error and config:
        error = _publish.auth_error(config, cwd=current)
    if not error:
        return None
    return "publish_unavailable", (
        f"`ginflow.publish` cannot run: {error}. Fix `.ginflow.yaml` or authenticate "
        "the provider CLI before execution; reviewer completion is blocked until it passes."
    )


def _project_config_route(current: Path) -> tuple[str, str] | None:
    """Return a mutation-blocking route when project context is unusable."""
    error = _context_error(current)
    if error:
        return "project_config_invalid", (
            f"Project-local `.ginflow.yaml` is invalid: {error}. "
            "Repair `.ginflow.yaml` for this workspace before continuing; "
            "do not silently switch workspace or board."
        )
    if not _config_exists(current):
        return "project_config_missing", (
            "Project-local `.ginflow.yaml` is missing. Run `/ginflow` to initialize "
            "the project context by choosing the current/default board or creating "
            "a new board before continuing."
        )
    return _publish_route(current)


@trace
def _routing_context(**kwargs: Any) -> dict[str, str] | str | None:
    """Inject deterministic workspace/card routing context when ginflow is active."""
    if not _ginflow_loaded():
        return None

    current = Path.cwd().resolve()
    config_route = _project_config_route(current)
    if config_route:
        route_name, guidance = config_route
        return {"context": (
            f"[ginflow-gate routing: route={route_name}; workspace={current}; "
            "mutation_allowed=False; task=none; candidates=none. " + guidance + "]"
        )}

    tasks = _load_tasks()
    explicit_id = os.environ.get("HERMES_KANBAN_TASK") or None
    route = _route(tasks, explicit_id)
    route_name = route["route"]
    candidates = route.get("candidates", [])
    candidate_ids = [item["id"] if isinstance(item, dict) else item for item in candidates]
    if route_name == "no_card":
        route_name = "no_cards_for_workspace"
    if route_name == "invalid_status":
        route_name = "validation_failed"
    action = route.get("action", "block")
    context = (
        f"[ginflow-gate routing: route={route_name}; workspace={current}; "
        f"mutation_allowed={action == 'execute'}; "
        f"task={route.get('id', explicit_id or 'none')}; "
        f"candidates={','.join(candidate_ids) if candidate_ids else 'none'}. "
    )
    if route_name == "no_cards_for_workspace":
        context += (
            "Report workspace to orchestrator; no Kanban card exists for workspace. "
            "For new work, shape `docs/specs/<KEY>.md` and `docs/plans/<KEY>.md`, then create "
            "blocked cards linking them; do not mutate product code or dispatch until cards exist."
        )
    elif route_name == "needs_card_selection":
        details = "; ".join(f"{item['id']}: {item['title']}" for item in candidates)
        context += f"Report candidates to orchestrator; ask orchestrator to select one card from candidates ({details}); Do not select or implement."
    elif route_name == "blocked_card":
        metadata = route.get("blocker_metadata")
        context += "Report blocker to orchestrator; do not implement."
        if metadata:
            context += f" Blocker metadata: {json.dumps(metadata, sort_keys=True)}."
    elif route_name == "validate_card_docs":
        selected = next((task for task in tasks if task.get("id") == route.get("id")), None)
        if selected:
            card = _normalize_task(selected)
            validation = startup_gate(card, current, current)
            route_name = validation["route"]
            context = context.replace("route=validate_card_docs", f"route={route_name}")
            if validation["valid"]:
                context += (
                    " Linked-document validation passed; resume implementation inside the "
                    "validated workspace and scope. Submit for review via the native "
                    "kanban_request_review tool only after completing the work and running "
                    "canonical verification; do not call kanban_complete directly (the "
                    "reviewer calls it to approve valid work)."
                )
            else:
                context += " Validate linked docs before next-to-in_progress transition."
        else:
            context += " Validate linked docs before next-to-in_progress transition."
    elif route_name == "ready_to_start":
        context += "Resume implementation only within validated workspace and scope."
    else:
        context += "Do not implement; report route to orchestrator."
    return {"context": context + "]"}


@trace
def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Adapt live task fields for the shared Ginflow startup validator."""
    card = _core.normalize_card({"task": task})
    if not card["workspace"]:
        card["workspace"] = task.get("workspace") or task.get("workspace_path") or ""
    return card


@trace
def _load_tasks() -> list[dict[str, Any]]:
    """Load board tasks as dictionaries; return empty on unavailable board."""
    try:
        current = Path.cwd()
        if _context_error(current) or not _config_exists(current):
            return []
        result = _core.kanban_run(_resolve_board(current), "list", "--json", timeout=15)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    tasks = data if isinstance(data, list) else data.get("tasks", data.get("items", [data]))
    return [task for task in tasks if isinstance(task, dict)]


def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _routing_context)
