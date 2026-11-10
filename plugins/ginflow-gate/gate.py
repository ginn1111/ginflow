"""Blocking Ginflow lifecycle policy for Hermes Kanban tools."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - optional parser fallback is tested below
    yaml = None


def _frontmatter_status(text: str) -> str | None:
    """Read simple status frontmatter without making gate import depend on PyYAML."""
    if not text.startswith("---\n"):
        return None
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator and key.strip() == "status":
            status = value.strip()
            if status and not status.startswith(("[", "{", "|", ">")):
                return status.strip("'\"")
    return None


def _frontmatter_status_is_completed(text: str) -> bool:
    if yaml is not None:
        try:
            lines = text.splitlines()
            end = lines.index("---", 1)
            frontmatter = yaml.safe_load("\n".join(lines[1:end]))
        except (ValueError, yaml.YAMLError):
            frontmatter = None
        return isinstance(frontmatter, dict) and frontmatter.get("status") == "completed"
    return _frontmatter_status(text) == "completed"


from .trace_adapter import trace
from . import publish as _publish
from . import skill_lib


_core = skill_lib.load("harness_core")
artifact_gate = _core.artifact_gate
normalize_card = _core.normalize_card
_project_config = skill_lib.load("project_config")


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": f"ginflow-gate: {message}"}


@trace
def load_card(task_id: str, board: str | None = None) -> dict:
    # Board: explicit, HERMES_KANBAN_BOARD, cwd .ginflow.yaml, then Hermes current board.
    document, error = _core.load_kanban_card(task_id, board)
    if error:
        raise RuntimeError(error)
    return normalize_card(document)


@trace
def linked_documents_missing_completion(card: dict, target: Path) -> list[str]:
    """Return linked local brief/spec/plan paths without completed frontmatter."""
    target = target.resolve()
    missing = []
    for link in card.get("links", []):
        path_str = link if isinstance(link, str) else link.get("path") if isinstance(link, dict) else None
        if not isinstance(path_str, str) or "://" in path_str:
            continue
        artifact = (target / path_str).resolve()
        try:
            artifact.relative_to(target)
        except ValueError:
            continue
        relative = artifact.relative_to(target)
        if artifact.is_file() and artifact.suffix.lower() == ".md" and any(
            part in {"briefs", "specs", "plans"} for part in relative.parts
        ):
            text = artifact.read_text(encoding="utf-8")
            if not text.startswith("---\n"):
                missing.append(path_str)
                continue
            if not _frontmatter_status_is_completed(text):
                missing.append(path_str)
    return sorted(missing)


@trace
def validate_completion(card: dict, metadata: dict) -> str | None:
    required = ("id", "title", "objective", "scope", "acceptance", "workspace", "assignee", "links")
    missing = [name for name in required if not card.get(name)]
    if missing:
        return "card missing required fields: " + ", ".join(missing)

    baseline = metadata.get("artifact_baseline")
    verification = metadata.get("verification_result")
    if not isinstance(verification, dict) or not all(verification.get(name) for name in ("commit", "command", "result")):
        return "metadata.verification_result requires non-empty commit, command, and result"
    if not isinstance(baseline, dict):
        return "metadata.artifact_baseline requires commit and exact linked paths"
    if verification["commit"] != baseline.get("commit"):
        return "verification_result.commit must match artifact_baseline.commit"

    workspace = str(card["workspace"])
    kind, _, path = workspace.partition(":")
    if kind not in ("dir", "worktree") or not path:
        return f"unsupported workspace for completion validation: {workspace}"
    target = Path(path).resolve()

    incomplete = linked_documents_missing_completion(card, target)
    if incomplete:
        return (
            "linked target-local documents require valid YAML frontmatter with status: completed: "
            + ", ".join(incomplete)
            + ". Add the frontmatter at byte 0, commit those changes, "
              "update verification_result.commit and artifact_baseline.commit, then retry review request or completion."
        )

    candidate = card | {"artifact_baseline": baseline}
    status = artifact_gate(candidate, target)
    if not status["baseline_complete"]:
        return status["baseline_details"]
    if not status["matches"]:
        return status["drift_details"]
    return None


VALIDATED_TOOLS = {"kanban_request_review", "kanban_complete"}


@trace
def pre_tool_call(tool_name: str, args: dict, task_id: str = "", **kwargs):
    if tool_name not in VALIDATED_TOOLS:
        return None
    try:
        selected = str(args.get("task_id") or task_id or os.environ.get("HERMES_KANBAN_TASK") or "").strip()
        if not selected:
            return _block(f"{tool_name} requires task_id")
        metadata = args.get("metadata")
        if not isinstance(metadata, dict):
            return _block("metadata object is required")
        card = load_card(selected, args.get("board") or os.environ.get("HERMES_KANBAN_BOARD"))
        error = validate_completion(card, metadata)
        if error:
            return _block(error)
        if tool_name == "kanban_complete":
            board = args.get("board") or os.environ.get("HERMES_KANBAN_BOARD")
            error = _publish.prepare(selected, card, metadata, board, _project_config, kwargs)
            if error:
                return _block(error)
        # Hermes has no default reviewer setting: inject ginflow.reviewer.profile.
        if tool_name == "kanban_request_review" and not args.get("reviewer"):
            workspace = str(card.get("workspace") or "")
            kind, _, path = workspace.partition(":")
            reviewer = _project_config.configured_reviewer(Path(path)) if kind in ("dir", "worktree") and path else None
            if reviewer:
                return {"action": "modify", "args": {"reviewer": reviewer}}
        return None
    except Exception as error:
        return _block(f"validation failed closed: {error}")


@trace
def post_tool_call(tool_name: str, result: dict, args: dict, task_id: str = "", **kwargs):
    """Publish MR/PR after a reviewer kanban_complete prepared in pre_tool_call; observer only."""
    if tool_name == "kanban_complete":
        selected = str((args or {}).get("task_id") or task_id or os.environ.get("HERMES_KANBAN_TASK") or "").strip()
        try:
            _publish.finish(selected, result, kwargs)
        except Exception:
            pass
    return None


def register(ctx):
    ctx.register_hook("pre_tool_call", pre_tool_call)
    ctx.register_hook("post_tool_call", post_tool_call)
