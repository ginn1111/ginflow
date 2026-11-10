"""Project-local canonical Ginflow Kanban context."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

try:
    import yaml
except ImportError:  # pragma: no cover - exercised when PyYAML is absent
    yaml = None

_PARSE_ERRORS = (OSError, ValueError) + ((yaml.YAMLError,) if yaml else ())

CONFIG_RELATIVE_PATH = Path(".ginflow.yaml")
CONFIG_VERSION = 1
WORKER_FIELDS = ("profile", "provider", "model")


def _scalar(text: str) -> Any:
    if text.startswith('"'):
        return json.loads(text)
    text = text.strip("'")
    if text in {"true", "false"}:
        return text == "true"
    return int(text) if re.fullmatch(r"-?\d+", text) else text


def _simple_loads(text: str) -> dict[str, Any]:
    """Parse the nested key/value subset used by `.ginflow.yaml` without PyYAML."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, separator, value = raw.strip().partition(":")
        if not separator or not key:
            raise ValueError(f"unsupported config line: {raw.strip()}")
        while stack[-1][0] >= indent:
            stack.pop()
        value = value.strip()
        if value:
            stack[-1][1][key] = _scalar(value)
        else:
            child: dict[str, Any] = {}
            stack[-1][1][key] = child
            stack.append((indent, child))
    return root


def _loads(text: str) -> Any:
    return yaml.safe_load(text) if yaml is not None else _simple_loads(text)


def _simple_dumps(data: Mapping[str, Any], indent: int = 0) -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, Mapping):
            lines.append(f"{' ' * indent}{key}:")
            lines.append(_simple_dumps(value, indent + 2))
        else:
            rendered = value if isinstance(value, (bool, int)) and not isinstance(value, str) else json.dumps(str(value))
            lines.append(f"{' ' * indent}{key}: {str(rendered).lower() if isinstance(value, bool) else rendered}")
    return "\n".join(lines)


def _dumps(data: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(data), sort_keys=False) if yaml is not None else _simple_dumps(data) + "\n"


class ContextInitializationError(ValueError):
    """Raised when first-use context cannot be resolved safely."""


def config_path(workspace: Path) -> Path:
    return Path(workspace).expanduser().resolve() / CONFIG_RELATIVE_PATH


def config_exists(workspace: Path) -> bool:
    """Return whether the project-local context file exists."""
    return config_path(workspace).is_file()


def load_config(workspace: Path) -> dict[str, Any]:
    path = config_path(workspace)
    if not path.is_file():
        return {}
    try:
        data = _loads(path.read_text(encoding="utf-8"))
    except _PARSE_ERRORS:
        return {}
    return data if isinstance(data, dict) else {}


def context_error(workspace: Path) -> str | None:
    """Validate an existing project config without silently repairing it."""
    path = config_path(workspace)
    if not path.exists():
        return None
    try:
        data = _loads(path.read_text(encoding="utf-8"))
    except _PARSE_ERRORS as exc:
        return f"project config is malformed: {exc}"
    if not isinstance(data, dict) or data.get("version") != CONFIG_VERSION:
        return f"project config must declare version: {CONFIG_VERSION}"
    context = data.get("ginflow")
    if not isinstance(context, dict):
        return "project config is missing the ginflow mapping"
    board = context.get("board")
    configured = context.get("workspace")
    if not isinstance(board, str) or not board.strip():
        return "project config is missing ginflow.board"
    if not isinstance(configured, str) or not configured.strip():
        return "project config is missing ginflow.workspace"
    configured_path = Path(configured).expanduser()
    if not configured_path.is_absolute():
        return "project config ginflow.workspace must be an absolute path"
    try:
        expected = configured_path.resolve()
    except (OSError, TypeError, ValueError):
        return "project config has an invalid workspace"
    actual = Path(workspace).expanduser().resolve()
    if expected != actual and not _same_repository(expected, actual):
        return f"project config workspace {expected} does not match {actual}"
    return notify_error(context)


def _same_repository(a: Path, b: Path) -> bool:
    """True when both paths share one .git dir: a git worktree is the same workspace as its main checkout."""
    common = _git_common_dir(a)
    return common is not None and common == _git_common_dir(b)


def _git_common_dir(path: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            text=True, capture_output=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(out.stdout.strip()).resolve() if out.returncode == 0 and out.stdout.strip() else None


def notify_error(context: Mapping[str, Any]) -> str | None:
    """Validate optional ginflow.notify.target; None when absent or valid."""
    if "notify" not in context:
        return None
    block = context["notify"]
    if not isinstance(block, dict):
        return "ginflow.notify must be a mapping"
    unknown = set(block) - {"target"}
    if unknown:
        return "ginflow.notify has unknown fields: " + ", ".join(sorted(unknown))
    if "target" in block and (not isinstance(block["target"], str) or not block["target"].strip()):
        return "ginflow.notify.target must be a non-empty string"
    return None


def configured_notify_target(workspace: Path) -> str | None:
    context = load_config(workspace).get("ginflow")
    block = context.get("notify") if isinstance(context, dict) else None
    value = block.get("target") if isinstance(block, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def configured_context(workspace: Path) -> dict[str, str]:
    data = load_config(workspace)
    context = data.get("ginflow", data)
    if not isinstance(context, dict):
        return {}
    result = {}
    for key in ("board", "workspace"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


class WorkerDefaultsError(ValueError):
    """Raised when configured worker dispatch defaults are unusable."""


def worker_error(workspace: Path) -> str | None:
    """Validate the optional worker dispatch block without repairing it.

    Returns a deterministic message when the block exists but is invalid,
    ``None`` when absent or valid. A missing worker block is not an error:
    ``profile``/``provider``/``model`` remain optional dispatch defaults.
    """
    path = config_path(workspace)
    if not path.exists():
        return None
    try:
        data = _loads(path.read_text(encoding="utf-8"))
    except _PARSE_ERRORS:
        return None
    if not isinstance(data, dict):
        return None
    context = data.get("ginflow")
    if not isinstance(context, dict):
        return None
    worker = context.get("worker")
    if worker is None:
        return None
    if not isinstance(worker, dict):
        return "ginflow.worker must be a mapping"
    for field in WORKER_FIELDS:
        value = worker.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            return f"ginflow.worker.{field} must be a non-empty string"
    unknown = set(worker) - set(WORKER_FIELDS)
    if unknown:
        return "ginflow.worker has unknown fields: " + ", ".join(sorted(unknown))
    return None


def configured_worker(workspace: Path) -> dict[str, str]:
    """Return configured worker dispatch defaults for a validated project config.

    Empty or missing values are omitted. The caller distinguishes an absent
    block from an invalid one via :func:`worker_error`.
    """
    data = load_config(workspace)
    context = data.get("ginflow", data)
    if not isinstance(context, dict):
        return {}
    worker = context.get("worker")
    if not isinstance(worker, dict):
        return {}
    result = {}
    for field in WORKER_FIELDS:
        value = worker.get(field)
        if isinstance(value, str) and value.strip():
            result[field] = value.strip()
    return result


def resolve_worker_dispatch(
    workspace: Path,
    explicit: Mapping[str, str] | None = None,
    current_profile: str | None = None,
) -> dict[str, str]:
    """Resolve worker dispatch defaults per field.

    Precedence per field: explicit per-card override, project-configured
    default, runtime fallback (current profile; provider/model left unset).
    Raises :class:`WorkerDefaultsError` when configured defaults are invalid
    so card creation fails closed rather than silently dropping values.
    """
    error = worker_error(workspace)
    if error:
        raise WorkerDefaultsError(error)
    explicit = explicit or {}
    configured = configured_worker(workspace)
    result: dict[str, str] = {}
    for field in WORKER_FIELDS:
        value = (explicit.get(field) or configured.get(field) or "").strip()
        if value:
            result[field] = value
            continue
        if field == "profile":
            profile = (current_profile or "").strip()
            if profile:
                result[field] = profile
    return result


class ReviewerConfigError(ValueError):
    """Raised when the configured project reviewer is unusable."""


def _reviewer_block(workspace: Path) -> Any:
    context = load_config(workspace).get("ginflow")
    return context.get("reviewer") if isinstance(context, dict) else None


def configured_reviewer(workspace: Path) -> str | None:
    block = _reviewer_block(workspace)
    value = block.get("profile") if isinstance(block, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


PUBLISH_FIELDS = {"provider", "target", "remote", "draft", "host"}


def publish_error(workspace: Path) -> str | None:
    """Validate optional ginflow.publish; None when absent or valid."""
    context = load_config(workspace).get("ginflow")
    block = context.get("publish") if isinstance(context, dict) else None
    if block is None:
        return None
    if not isinstance(block, dict):
        return "ginflow.publish must be a mapping"
    unknown = set(block) - PUBLISH_FIELDS
    if unknown:
        return "ginflow.publish has unknown fields: " + ", ".join(sorted(unknown))
    if block.get("provider") not in ("github", "gitlab"):
        return "ginflow.publish.provider must be github or gitlab"
    for name in ("target", "remote"):
        value = block.get(name, "origin" if name == "remote" else None)
        if not isinstance(value, str) or not value.strip() or value.startswith("-"):
            return f"ginflow.publish.{name} must be a non-empty branch/remote name"
    host = block.get("host")
    if host is not None and (not isinstance(host, str) or not host.strip() or host.startswith("-")):
        return "ginflow.publish.host must be a non-empty hostname"
    if not isinstance(block.get("draft", False), bool):
        return "ginflow.publish.draft must be a boolean"
    return None


def configured_publish(workspace: Path) -> dict[str, Any] | None:
    """Validated publish settings with defaults, or None when absent/invalid."""
    if publish_error(workspace):
        return None
    block = load_config(workspace).get("ginflow", {}).get("publish")
    if not isinstance(block, dict):
        return None
    return {"provider": block["provider"], "target": block["target"].strip(),
            "remote": block.get("remote", "origin").strip(), "draft": block.get("draft", False),
            "host": (block.get("host") or "").strip() or None}


def reviewer_error(workspace: Path, installed_profiles: Iterable[str]) -> str | None:
    """Validate optional ginflow.reviewer.profile; None when absent or valid."""
    block = _reviewer_block(workspace)
    if block is None:
        return None
    if not isinstance(block, dict):
        return "ginflow.reviewer must be a mapping"
    unknown = set(block) - {"profile"}
    if unknown:
        return "ginflow.reviewer has unknown fields: " + ", ".join(sorted(unknown))
    value = block.get("profile")
    if not isinstance(value, str) or not value.strip():
        return "ginflow.reviewer.profile must be a non-empty string"
    if value.strip() not in set(installed_profiles):
        return f"ginflow.reviewer.profile {value.strip()!r} is not an installed Hermes profile"
    return None


def installed_profiles() -> list[str]:
    root = Path(os.environ.get("HERMES_PROFILES_ROOT", Path.home() / ".hermes" / "profiles"))
    names = [p.name for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    return ["default", *names]


def hermes_default_reviewer() -> str | None:
    home = os.environ.get("HERMES_HOME")
    if not home or yaml is None:
        return None
    try:
        data = yaml.safe_load((Path(home) / "config.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    kanban = data.get("kanban") if isinstance(data, dict) else None
    value = kanban.get("default_reviewer_profile") if isinstance(kanban, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def _hermes_write(profile: str) -> None:
    subprocess.run(
        ["hermes", "config", "set", "kanban.default_reviewer_profile", profile],
        check=True, capture_output=True, text=True,
    )


def seed_default_reviewer(
    workspace: Path,
    *,
    installed_profiles: Iterable[str],
    current: str | None = None,
    write: Callable[[str], Any] = _hermes_write,
) -> tuple[str | None, list[str]]:
    """Seed Hermes kanban.default_reviewer_profile from project config.

    Absent project reviewer: Hermes config untouched. Invalid reviewer: raises
    before any write (fail closed). Writes only when value differs from
    ``current``. Returns (configured reviewer, values written).
    """
    error = reviewer_error(workspace, list(installed_profiles))
    if error:
        raise ReviewerConfigError(error)
    reviewer = configured_reviewer(workspace)
    written: list[str] = []
    if reviewer and reviewer != current:
        write(reviewer)
        written.append(reviewer)
    return reviewer, written


DOC_PROVIDERS = ("adaptive", "local", "github", "linear")
STATUS_KEYS = ("start", "block", "resume", "review_request", "request_changes", "complete")
_DOC_KEYS = {"provider", "github", "linear", "status_map"}
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_DIRECTIVE_RE = re.compile(r"^\s*ginflow-docs:\s*(.*?)\s*$")
_ORIGIN_RE = re.compile(r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class DocumentConfigError(ValueError):
    """Raised when documentation config or resolution must stop and ask."""


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def documents_block_error(block: Any) -> str | None:
    """Strict validation of a ``ginflow.documents`` block; None when valid."""
    if not isinstance(block, dict):
        return "ginflow.documents must be a mapping"
    unknown = set(block) - _DOC_KEYS
    if unknown:
        return "ginflow.documents has unknown fields: " + ", ".join(sorted(unknown))
    provider = block.get("provider")
    if provider not in DOC_PROVIDERS:
        return "ginflow.documents.provider must be one of: " + ", ".join(DOC_PROVIDERS)
    for name in ("github", "linear"):
        if name in block and provider != name:
            return f"ginflow.documents.{name} requires provider: {name}"
    if provider == "github":
        sub = block.get("github")
        if not isinstance(sub, dict) or set(sub) != {"repo"}:
            return "ginflow.documents.github must be a mapping with only repo"
        if not isinstance(sub["repo"], str) or not _REPO_RE.match(sub["repo"]):
            return "ginflow.documents.github.repo must be owner/name"
    if provider == "linear":
        sub = block.get("linear")
        if not isinstance(sub, dict) or not set(sub) <= {"team", "project"} or "team" not in sub:
            return "ginflow.documents.linear must be a mapping with team and optional project"
        for key, value in sub.items():
            if not isinstance(value, str) or not _UUID_RE.match(value):
                return f"ginflow.documents.linear.{key} must be a stable Linear ID"
    if provider in ("github", "linear"):
        status = block.get("status_map")
        if not isinstance(status, dict):
            return "ginflow.documents.status_map is required for " + provider
        missing = [k for k in STATUS_KEYS if not _nonempty(status.get(k))]
        extra = set(status) - set(STATUS_KEYS)
        if missing:
            return "ginflow.documents.status_map missing or empty: " + ", ".join(missing)
        if extra:
            return "ginflow.documents.status_map has unknown fields: " + ", ".join(sorted(extra))
    elif "status_map" in block:
        return f"ginflow.documents.status_map is not allowed for provider: {provider}"
    return None


def documents_error(workspace: Path) -> str | None:
    """Validate optional ginflow.documents; None when absent or valid."""
    context = load_config(workspace).get("ginflow")
    if not isinstance(context, dict) or "documents" not in context:
        return None
    return documents_block_error(context["documents"])


def configured_documents(workspace: Path) -> dict[str, Any] | None:
    context = load_config(workspace).get("ginflow")
    block = context.get("documents") if isinstance(context, dict) else None
    return block if isinstance(block, dict) else None


def _parse_directive(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in text.split():
        key, sep, value = token.partition("=")
        if not sep or not value or key not in {"provider", "repo", "team", "project"} or key in values:
            raise DocumentConfigError(f"invalid ginflow-docs directive: {text!r}")
        values[key] = value
    if values.get("provider") not in ("local", "github", "linear"):
        raise DocumentConfigError(f"ginflow-docs provider must be local, github, or linear: {text!r}")
    return values


def _origin_repo(workspace: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(workspace), "remote", "get-url", "origin"],
            text=True, capture_output=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = _ORIGIN_RE.search(out.stdout.strip()) if out.returncode == 0 else None
    return f"{match.group(1)}/{match.group(2)}" if match else None


def _stable_linear(value: str, kind: str, resolver: Callable[[str, str], str | None] | None) -> str:
    if _UUID_RE.match(value):
        return value
    resolved = resolver(kind, value) if resolver else None
    if not isinstance(resolved, str) or not _UUID_RE.match(resolved):
        raise DocumentConfigError(f"cannot resolve Linear {kind} {value!r} to a stable ID; provide the ID")
    return resolved


def resolve_documents(
    workspace: Path,
    *,
    linked_docs: Iterable[str] = (),
    canonical_refs: Iterable[str] = (),
    linear_resolver: Callable[[str, str], str | None] | None = None,
    origin: Callable[[Path], str | None] = _origin_repo,
    readiness: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Resolve the documentation authority; raise DocumentConfigError to stop and ask.

    Explicit provider wins. ``adaptive`` reads ``ginflow-docs:`` directives by
    level: AGENTS.md, .hermes.md, linked agent docs, canonical provider refs.
    The first level with directives decides; disagreement inside a level, or no
    directive anywhere, stops. Tools/credentials never select a provider.
    Report: configured, effective, evidence, destination, readiness.
    """
    workspace = Path(workspace).expanduser().resolve()
    error = documents_error(workspace)
    if error:
        raise DocumentConfigError(error)
    block = configured_documents(workspace)
    if block is None:
        raise DocumentConfigError("ginflow.documents is not configured; ask which provider to use")
    configured = block["provider"]
    if configured != "adaptive":
        effective = {"provider": configured, **(block.get(configured) or {})}
        evidence = {"file": str(CONFIG_RELATIVE_PATH), "line": None}
    else:
        levels = [["AGENTS.md"], [".hermes.md"], list(linked_docs), list(canonical_refs)]
        effective = evidence = None
        for files in levels:
            found = []
            for name in files:
                path = workspace / name
                if not path.is_file():
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    match = _DIRECTIVE_RE.match(line)
                    if match:
                        found.append((_parse_directive(match.group(1)), {"file": name, "line": number}))
            if not found:
                continue
            if any(item[0] != found[0][0] for item in found):
                raise DocumentConfigError(
                    "conflicting ginflow-docs directives: "
                    + "; ".join(f"{e['file']}:{e['line']}" for _, e in found)
                )
            effective, evidence = found[0]
            break
        if effective is None:
            raise DocumentConfigError("no ginflow-docs evidence found; ask which provider to use")
    provider = effective["provider"]
    target: dict[str, Any] = {"provider": provider}
    if provider == "github":
        repo = effective.get("repo") or origin(workspace)
        if not isinstance(repo, str) or not _REPO_RE.match(repo):
            raise DocumentConfigError("GitHub repo must be owner/name or an unambiguous origin remote")
        target["repo"] = repo
        destination = f"github:{repo}"
    elif provider == "linear":
        if not effective.get("team"):
            raise DocumentConfigError("Linear team is required")
        target["team"] = _stable_linear(effective["team"], "team", linear_resolver)
        destination = f"linear:team={target['team']}"
        if effective.get("project"):
            target["project"] = _stable_linear(effective["project"], "project", linear_resolver)
            destination += f" project={target['project']}"
    else:
        destination = "local:docs/"
    return {
        "configured": configured,
        "effective": target,
        "evidence": evidence,
        "destination": destination,
        "readiness": (readiness(provider) or "ready") if readiness and provider != "local" else "ready",
    }


def require_ready(provider: str, checker: Callable[[str], str | None]) -> None:
    """Fail closed for governed creation; policy saves never call this."""
    if provider == "local":
        return
    action = checker(provider)
    if action:
        raise DocumentConfigError(f"{provider} documents not ready: {action}")


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def set_documents(workspace: Path, documents: Mapping[str, Any]) -> Path:
    """Save a valid documents block into a valid config, preserving other keys.

    No credentials needed. Outdated/malformed configs use the migration API.
    """
    workspace = Path(workspace).expanduser().resolve()
    error = context_error(workspace) or documents_block_error(dict(documents))
    if error:
        raise DocumentConfigError(error)
    data = load_config(workspace)
    data["ginflow"] = {**data["ginflow"], "documents": dict(documents)}
    _atomic_write(config_path(workspace), _dumps(data))
    return config_path(workspace)


def preview_migration(workspace: Path, new_config: Mapping[str, Any]) -> str:
    """Unified diff of current config text versus the proposed one; writes nothing."""
    import difflib

    path = config_path(workspace)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    return "".join(difflib.unified_diff(
        old.splitlines(True), _dumps(new_config).splitlines(True), ".ginflow.yaml", ".ginflow.yaml (proposed)"))


def _ensure_ignored(workspace: Path) -> None:
    probe = subprocess.run(["git", "-C", str(workspace), "check-ignore", "-q", ".ginflow/x"], capture_output=True)
    if probe.returncode == 0:
        return
    out = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--git-path", "info/exclude"],
        text=True, capture_output=True,
    )
    if out.returncode:
        return
    exclude = Path(out.stdout.strip())
    exclude = exclude if exclude.is_absolute() else workspace / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n.ginflow/\n")


def apply_migration(
    workspace: Path, new_config: Mapping[str, Any], *, approved: bool, now: Callable[[], str] | None = None
) -> Path | None:
    """Write proposed config after explicit approval; returns backup path (None if no prior file).

    Backup is the prior config only, under ignored ``.ginflow/migrations/``.
    """
    import datetime

    workspace = Path(workspace).expanduser().resolve()
    if approved is not True:
        raise DocumentConfigError("migration requires explicit approval; review preview_migration output")
    ginflow = new_config.get("ginflow")
    if new_config.get("version") != CONFIG_VERSION or not isinstance(ginflow, dict):
        raise DocumentConfigError("proposed config must declare version and ginflow mapping")
    if "documents" in ginflow:
        error = documents_block_error(ginflow["documents"])
        if error:
            raise DocumentConfigError(error)
    path = config_path(workspace)
    backup = None
    if path.exists():
        stamp = now() if now else datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        folder = workspace / ".ginflow" / "migrations"
        folder.mkdir(parents=True, exist_ok=True)
        backup = folder / f"{stamp}-.ginflow.yaml"
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        _ensure_ignored(workspace)
    _atomic_write(path, _dumps(new_config))
    return backup


def context_mismatch(workspace: Path) -> str | None:
    """Return a deterministic error when a config belongs to another project."""
    error = context_error(workspace)
    return error if error and "workspace" in error else None


def active_board(env: Mapping[str, str] | None = None) -> str | None:
    values = env if env is not None else os.environ
    explicit = values.get("HERMES_KANBAN_BOARD", "").strip()
    if explicit:
        return explicit
    try:
        result = subprocess.run(
            ["hermes", "kanban", "boards", "current"],
            text=True, capture_output=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        match = re.match(r"^\s*Current board:\s*(\S+)\s*$", line)
        if match:
            return match.group(1)
    return None


def resolve_board(workspace: Path, explicit: str | None = None, env: Mapping[str, str] | None = None) -> str | None:
    """Resolve explicit override, environment override, then project config, then active board."""
    if context_error(workspace):
        return None
    if explicit and explicit.strip():
        return explicit.strip()
    values = env if env is not None else os.environ
    if values.get("HERMES_KANBAN_BOARD", "").strip():
        return values["HERMES_KANBAN_BOARD"].strip()
    return configured_context(workspace).get("board") or active_board(values)


def persist_context(workspace: Path, *, board: str | None) -> Path | None:
    """Persist only complete, resolved context; never create a partial config."""
    workspace = Path(workspace).expanduser().resolve()
    if not board or not workspace.is_dir():
        return None
    path = config_path(workspace)
    if path.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": CONFIG_VERSION, "ginflow": {"board": board, "workspace": str(workspace)}}
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(_dumps(payload), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return None
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path


def persist_worker_defaults(
    workspace: Path,
    *,
    profile: str,
    provider: str,
    model: str,
) -> Path | None:
    """Atomically add or replace a complete worker dispatch block.

    Requires an existing valid project context so the merge never creates a
    partial config or silently changes board/workspace. Returns the config
    path on success and ``None`` on any failure, leaving the original file
    unchanged.
    """
    workspace = Path(workspace).expanduser().resolve()
    path = config_path(workspace)
    if not workspace.is_dir() or context_error(workspace):
        return None
    values = {"profile": profile, "provider": provider, "model": model}
    cleaned = {}
    for field in WORKER_FIELDS:
        value = (values[field] or "").strip()
        if not value:
            return None
        cleaned[field] = value
    data = load_config(workspace)
    context = data.get("ginflow")
    if not isinstance(context, dict):
        context = {}
    merged = dict(context)
    merged["worker"] = cleaned
    data = dict(data)
    data["ginflow"] = merged
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(_dumps(data), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return None
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path


def initialize_context(
    workspace: Path,
    *,
    choice: str,
    current_board: str | None,
    board_name: str | None = None,
    create_board: Any | None = None,
) -> Path:
    """Complete first-use selection, creating a board before config persistence.

    The interactive `/ginflow` skill supplies ``choice`` and ``board_name`` and
    passes a native Kanban board-creation operation as ``create_board``. Keeping
    the decision and side effect behind this small API makes the ordering and
    fail-closed behavior deterministic in tests.
    """
    workspace = Path(workspace).expanduser().resolve()
    path = config_path(workspace)
    if path.exists():
        raise ContextInitializationError(f"project config already exists: {path}")
    if choice == "current":
        board = (current_board or "").strip()
        if not board:
            raise ContextInitializationError("current/default Kanban board is unavailable")
    elif choice == "new":
        board = (board_name or "").strip()
        if not board:
            raise ContextInitializationError("new board name must not be empty")
        if not callable(create_board):
            raise ContextInitializationError("native Kanban board creation is required")
        created = create_board(board)
        if isinstance(created, str) and created.strip():
            board = created.strip()
        elif created is not True:
            raise ContextInitializationError("native Kanban board creation failed")
    else:
        raise ContextInitializationError("choose the current/default board or create a new board")
    persisted = persist_context(workspace, board=board)
    if persisted is None:
        raise ContextInitializationError(f"unable to persist project config: {path}")
    return persisted


__all__ = ["DOC_PROVIDERS", "STATUS_KEYS", "DocumentConfigError", "apply_migration", "configured_documents", "documents_block_error", "documents_error", "preview_migration", "require_ready", "resolve_documents", "set_documents", "ReviewerConfigError", "configured_reviewer", "configured_publish", "publish_error", "hermes_default_reviewer", "installed_profiles", "reviewer_error", "seed_default_reviewer", "CONFIG_RELATIVE_PATH", "CONFIG_VERSION", "WORKER_FIELDS", "ContextInitializationError", "WorkerDefaultsError", "active_board", "config_exists", "config_path", "configured_context", "configured_worker", "context_error", "context_mismatch", "initialize_context", "load_config", "persist_context", "persist_worker_defaults", "resolve_board", "resolve_worker_dispatch", "worker_error"]
