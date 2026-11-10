"""Blocking Ginflow lifecycle policy for Hermes Kanban tools."""

from __future__ import annotations

import hashlib
import importlib.util
import json
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


try:
    from .trace_adapter import trace
except ImportError:
    _trace_spec = importlib.util.spec_from_file_location(
        "ginflow_gate_trace_adapter", Path(__file__).with_name("trace_adapter.py")
    )
    if not _trace_spec or not _trace_spec.loader:
        raise ImportError("unable to load trace adapter")
    _trace_module = importlib.util.module_from_spec(_trace_spec)
    _trace_spec.loader.exec_module(_trace_module)
    trace = _trace_module.trace


def _harness_core_path() -> Path:
    plugin = Path(__file__).resolve()
    real_home = Path(os.environ.get("HERMES_REAL_HOME", str(Path.home()))).expanduser().resolve()
    candidates = (
        plugin.parents[2] / "skills/ginflow/lib/harness_core.py",
        real_home / ".agents/skills/ginflow/lib/harness_core.py",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ImportError("unable to locate Ginflow skill harness core; checked: " + ", ".join(map(str, candidates)))


CORE = _harness_core_path()
_spec = importlib.util.spec_from_file_location("ginflow_harness_core", CORE)
if not _spec or not _spec.loader:
    raise ImportError(f"unable to load Ginflow harness core: {CORE}")
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
artifact_gate = _core.artifact_gate
normalize_card = _core.normalize_card
_cfg_spec = importlib.util.spec_from_file_location("ginflow_project_config", CORE.with_name("project_config.py"))
_project_config = importlib.util.module_from_spec(_cfg_spec)
_cfg_spec.loader.exec_module(_project_config)


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": f"ginflow-gate: {message}"}


@trace
def load_card(task_id: str, board: str | None = None) -> dict:
    command = ["hermes", "kanban"]
    if board:
        command += ["--board", board]
    command += ["show", task_id, "--json"]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"unable to read card {task_id}")
    return normalize_card(json.loads(result.stdout))


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


def _document_error(card: dict, metadata: dict, target: Path) -> str | None:
    """Require matching document_baseline for cards linking a local work-unit document."""
    links = [link for link in card.get("links", []) if isinstance(link, str) and "://" not in link
             and link.startswith("docs/work-units/") and link.endswith(".md")]
    baseline = metadata.get("document_baseline")
    if not links and baseline is None:
        return None  # legacy card: no provider document
    if len(links) != 1:
        return "document_baseline requires exactly one linked docs/work-units/<KEY>.md document"
    if not isinstance(baseline, dict) or not all(baseline.get(n) for n in ("content_hash", "commit")):
        return "metadata.document_baseline requires non-empty content_hash and commit"
    if metadata["verification_result"]["result"] != "passed":
        return "verification_result.result must be passed when a provider document is linked"
    shown = subprocess.run(
        ["git", "show", f"{baseline['commit']}:{links[0]}"], cwd=target, capture_output=True
    )
    if shown.returncode:
        return f"document {links[0]} is not committed at {baseline['commit']}"
    # Same normalization as provider_document.content_hash: newlines, trailing spaces only.
    lines = shown.stdout.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    text = "\n".join(line.rstrip() for line in lines).rstrip("\n") + "\n"
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != baseline["content_hash"]:
        return f"document_baseline.content_hash does not match committed {links[0]}"
    return None


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
    if not workspace.startswith("dir:"):
        return f"unsupported workspace for completion validation: {workspace}"
    target = Path(workspace.removeprefix("dir:")).resolve()

    incomplete = linked_documents_missing_completion(card, target)
    if incomplete:
        return (
            "linked target-local documents require valid YAML frontmatter with status: completed: "
            + ", ".join(incomplete)
            + ". Add the frontmatter at byte 0, commit those changes, "
              "update verification_result.commit and artifact_baseline.commit, then retry review request or completion."
        )

    document_error = _document_error(card, metadata, target)
    if document_error:
        return document_error

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
        # Hermes has no default reviewer setting: inject ginflow.reviewer.profile.
        if tool_name == "kanban_request_review" and not args.get("reviewer"):
            workspace = str(card.get("workspace") or "")
            reviewer = _project_config.configured_reviewer(Path(workspace.removeprefix("dir:"))) if workspace.startswith("dir:") else None
            if reviewer:
                return {"action": "modify", "args": {"reviewer": reviewer}}
        return None
    except Exception as error:
        return _block(f"validation failed closed: {error}")


@trace
def post_tool_call(tool_name: str, result: dict, args: dict, task_id: str = "", **kwargs):
    """Retained compatibility hook; linked documents are finalized before completion."""
    return None


def register(ctx):
    ctx.register_hook("pre_tool_call", pre_tool_call)
    ctx.register_hook("post_tool_call", post_tool_call)
