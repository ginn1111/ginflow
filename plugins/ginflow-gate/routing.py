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


WORK_MODE_SKILLS = {
    "investigation": "diagnosing-bugs",
    "implementation": "implement",
    "brainstorming": "brainstorming",
    "clarification": "brainstorming",
    "verification": "verification-before-completion",
    "recovery": "executing-plans",
}

WORK_MODES = frozenset(WORK_MODE_SKILLS)
WORK_SIZES = frozenset({"XS", "S", "M", "L", "XL"})

_DEFAULT_OUTPUTS = {
    "spec": "docs/specs/<CARD-ID>.md",
    "plan": "docs/plans/<CARD-ID>.md",
    "wayfinder": "docs/wayfinding/<MAP-ID>.md",
    "handoff": "docs/handoffs/<CARD-ID>.md",
}


@trace
def format_work_guidance(
    *,
    work_mode: str,
    work_size: str | None,
    size_rationale: str | None,
    eligibility: str,
    risk_impact: str,
    canonical_verification: str | None = None,
    output_overrides: dict[str, str] | None = None,
) -> str:
    """Render bounded, advisory routing guidance for Hermes.

    This formatter is retained only for explicitly active legacy v1 cards. It
    deliberately does not decide eligibility, create records, call ``skill_view``,
    or inspect the selected skill. Hermes supplies the facts and makes the
    affirmative Direct Work decision. New Initiative work never uses this route.
    """
    mode = work_mode if work_mode in WORK_MODES else "clarification"
    skill = WORK_MODE_SKILLS[mode]
    outputs = dict(_DEFAULT_OUTPUTS)
    if output_overrides:
        outputs.update({key: value for key, value in output_overrides.items() if key in outputs})

    if eligibility == "eligible" and work_size in {"XS", "S"} and risk_impact == "none":
        route = "Direct Work"
        route_id = "direct-no-card"
        output = (
            "Route: direct-no-card (Direct Work). Output: Delivery Change + conversation result; "
            "no Kanban Card, Links field, Governance Artifact, or replacement execution record."
        )
    elif eligibility == "unknown" or work_size not in WORK_SIZES or risk_impact == "unknown":
        route = "Clarification"
        route_id = "clarification"
        output = (
            "Route: Clarification. Permit conversation-led brainstorming or read-only investigation "
            "only; no repository mutation, implementation, Kanban Card, working note, or Governance Artifact."
        )
    else:
        route = "Governed Work"
        route_id = "governed"
        output = (
            "Route: Governed Work. Start and validate a build-ready Kanban Card; use conditional "
            f"Spec/Plan outputs ({outputs['spec']}; {outputs['plan']}) when behavior, contract, ordering, "
            "investigation, risk, rollback, or layered verification requires them. No Brief."
        )

    size_text = work_size or "unknown"
    rationale = size_rationale or "unknown shaping evidence"
    verification = canonical_verification or "unknown canonical verification"
    return (
        f"[ginflow work guidance: work-mode={mode}; route={route_id}; work-size={size_text}; "
        f"size-rationale={rationale}; Risk Impact={risk_impact}; candidate skill: {skill}. "
        f"Before acting, Hermes must call skill_view(name='{skill}'). "
        f"{output} Canonical verification: {verification}. "
        "Direct Work Eligibility must be affirmative: clear requirements and target behavior; "
        "known bug root cause; genuine XS/S; localized reversible scope; no actual Risk Impact; "
        "no Governance Artifact need; known verification; project-local permission; unowned single-worker workspace. "
        "Risky keywords alone are not Risk Impact. The plugin provides guidance only: it never calls skill_view, "
        "creates cards or Governance Artifacts, mutates Kanban, or mechanically authorizes Direct Work. "
        "If scope, clarity, ownership, verification, or impact changes, stop mutation and reclassify before continuing. "
        f"Canonical optional outputs remain {outputs['wayfinder']} and {outputs['handoff']}.]"
    )


def _configured_output_overrides() -> dict[str, str]:
    """Read explicit project-local canonical output overrides, if configured."""
    return {
        key: value
        for key, value in (
            ("spec", os.environ.get("GINFLOW_OUTPUT_SPEC", "")),
            ("plan", os.environ.get("GINFLOW_OUTPUT_PLAN", "")),
            ("wayfinder", os.environ.get("GINFLOW_OUTPUT_WAYFINDER", "")),
            ("handoff", os.environ.get("GINFLOW_OUTPUT_HANDOFF", "")),
        )
        if value
    }


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
    """Compatibility adapter: inject Hermes cwd into core policy."""
    return _route_policy(tasks, Path.cwd(), explicit_id)


def _is_legacy_v1_card(task: dict[str, Any]) -> bool:
    """Recognize explicit pre-migration metadata, never infer legacy from absence."""
    metadata = task.get("metadata")
    if not isinstance(metadata, dict):
        return False
    if metadata.get("workflow_version") == 1:
        return True
    if metadata.get("ginflow_version") == 1:
        return True
    return metadata.get("legacy_v1") is True


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
    selected_task = next(
        (task for task in tasks if task.get("id") == route.get("id")),
        None,
    )
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
            "For new governed/autonomous work, create or select one initiative record "
            "and follow Discovery → Shaping → Execution → Decision. Discovery resolves "
            "ambiguity; Shaping approves the artifact-first package; do not mutate product "
            "code or dispatch cards before approved Shaping. Legacy Work Mode/Work Size "
            "guidance applies only when an explicitly active pre-migration v1 card is "
            "identified."
        )
        if selected_task and _is_legacy_v1_card(selected_task):
            context += " " + format_work_guidance(
                work_mode="clarification",
                work_size=None,
                size_rationale=None,
                eligibility="unknown",
                risk_impact="unknown",
                output_overrides=_configured_output_overrides(),
            )
        else:
            context += " Legacy compatibility guidance is withheld because no active v1 card was identified."
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
    if selected_task and _is_legacy_v1_card(selected_task) and route_name in {
        "validate_card_docs",
        "ready_to_start",
    }:
        context += " " + format_work_guidance(
            work_mode="clarification",
            work_size=None,
            size_rationale=None,
            eligibility="unknown",
            risk_impact="unknown",
            output_overrides=_configured_output_overrides(),
        )
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
