"""Atomic JSON-list storage for trace and trace-error records."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import Lock

_LOCKS: dict[Path, Lock] = {}
_LOCKS_GUARD = Lock()


def _lock(path: Path) -> Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(path, Lock())


def append_record(root: Path, filename: str, record: dict[str, object]) -> None:
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock(path):
        try:
            records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if not isinstance(records, list):
                records = []
        except (OSError, ValueError):
            records = []
        records.append(record)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(records, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
