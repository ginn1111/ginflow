"""Provider document builder and local adapter for one Work Unit record.

Builder is pure (no filesystem, network, credentials). Local adapter is separate.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA = "provider_document/v1"
LOCAL_DIR = "docs/work-units"
REQUIRED = ("key", "objective", "scope", "acceptance", "contract", "spec", "plan", "verification")
SECTIONS = (
    ("Objective", "objective"), ("Scope", "scope"), ("Acceptance", "acceptance"),
    ("Contract", "contract"), ("Spec", "spec"), ("Plan", "plan"),
    ("Verification", "verification"), ("Dependencies", "dependencies"), ("Risks", "risks"),
)
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def normalize(text: str) -> str:
    """Newline and trailing-space normalization only; one final newline."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).rstrip("\n") + "\n"


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def _present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, (list, tuple)) and any(isinstance(v, str) and v.strip() for v in value)


def _render(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return "\n".join(f"- {item}" for item in value if str(item).strip())


def _render_local(package: Mapping[str, Any]) -> str:
    key = package["key"]
    parts = [f"---\nprovider: local\nwork_unit: {key}\nschema: {SCHEMA}\n---\n", f"# {key}\n"]
    for heading, field in SECTIONS:
        if _present(package.get(field)):
            parts.append(f"## {heading}\n\n{_render(package[field])}\n")
    return "\n".join(parts)


_RENDERERS = {"local": _render_local}


def build_provider_document(
    provider: str, work_package: Mapping[str, Any], target: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Render one deterministic provider document. Raises on unknown provider or bad package."""
    if provider not in _RENDERERS:
        raise ValueError(f"unknown provider: {provider}")
    if not isinstance(work_package, Mapping):
        raise ValueError("work package must be a mapping")
    missing = [f for f in REQUIRED if not _present(work_package.get(f))]
    if missing:
        raise ValueError("incomplete work package: missing " + ", ".join(missing))
    key = work_package["key"]
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError(f"invalid work unit key: {key!r}")
    body = normalize(_RENDERERS[provider](work_package))
    first_line = _render(work_package["objective"]).splitlines()[0]
    return {
        "provider": provider,
        "title": f"{key} — {first_line}",
        "body": body,
        "target_hints": {**dict(target or {}), "path": f"{LOCAL_DIR}/{key}.md"},
        "metadata": {"provider": provider, "work_unit": key, "schema": SCHEMA},
        "content_hash": content_hash(body),
    }


def write_local_document(document: Mapping[str, Any], root: str | Path) -> dict[str, str]:
    """Write missing file, adopt exact match, block (never overwrite) on conflict."""
    relative = document["target_hints"]["path"]
    path = Path(root) / relative
    result = {"path": relative, "content_hash": document["content_hash"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(document["body"])
        return {**result, "status": "written"}
    except FileExistsError:
        if content_hash(path.read_text(encoding="utf-8")) == document["content_hash"]:
            return {**result, "status": "adopted"}
        return {**result, "status": "blocked", "reason": "existing document differs; not overwritten"}


__all__ = ["build_provider_document", "content_hash", "normalize", "write_local_document"]
