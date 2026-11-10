#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(sys.argv[1]).resolve()
ARGS = sys.argv[2:]
MANIFEST = Path(os.environ.get("GINFLOW_INSTALL_MANIFEST", str(ROOT / ".ginflow-install.json"))).expanduser().resolve()
VERSION = 2



def fail(message: str) -> None:
    print(f"❌ {message}", file=sys.stderr)
    raise SystemExit(1)


def info(message: str) -> None:
    print(f"ℹ️  {message}")


def ok(message: str) -> None:
    print(f"✅ {message}")


# Names copy_tree skips; also skipped when hashing so build output created after install is not a conflict.
SKIP_NAMES = {"__pycache__", ".git", ".DS_Store", "node_modules", "dist", ".tooling"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_dir():
        for item in sorted(path.rglob("*")):
            rel = item.relative_to(path)
            if item.is_file() and not SKIP_NAMES.intersection(rel.parts) and item.suffix != ".pyc":
                digest.update(str(rel).encode())
                digest.update(item.read_bytes())
    else:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def copy_tree(source: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".git",
        ".DS_Store",
        "node_modules",
        "dist",
        ".tooling",
    )
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=str(destination.parent)))
    try:
        shutil.copytree(source, temporary / destination.name, ignore=ignored)
        os.replace(temporary / destination.name, destination)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def backup_path(destination: Path) -> Path:
    return destination.with_name(destination.name + ".bak.ginflow-install")


def backup_existing(destination: Path) -> str | None:
    if not destination.exists() and not destination.is_symlink():
        return None
    backup = backup_path(destination)
    if backup.exists() or backup.is_symlink():
        fail(f"backup already exists; uninstall first or resolve manually: {backup}")
    if destination.is_symlink():
        backup.symlink_to(os.readlink(destination), target_is_directory=destination.is_dir())
    elif destination.is_dir():
        shutil.copytree(destination, backup, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        shutil.copy2(destination, backup)
    return str(backup)


def write_manifest(manifest: dict[str, Any]) -> None:
    temporary = MANIFEST.with_name(MANIFEST.name + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(temporary, MANIFEST)


def discover_profiles(profiles_dir: Path, names: list[str]) -> list[str]:
    if names:
        for name in names:
            if not (profiles_dir / name / "config.yaml").is_file():
                fail(f"Hermes profile missing or invalid: {name}")
        return names
    found = sorted(p.name for p in profiles_dir.iterdir() if (p / "config.yaml").is_file()) if profiles_dir.is_dir() else []
    if not found:
        fail(f"no Hermes profiles found in {profiles_dir}")
    return found


def install(profile_names: list[str]) -> None:
    if MANIFEST.exists():
        info("existing Ginflow installation found; cleaning it before reinstall")
        uninstall()
    source_skill = ROOT / "skills/ginflow"
    plugin_names = ("ginflow-gate", "ginflow-trace")
    core_routing = ROOT / "core/ginflow-core/routing.py"
    if not source_skill.is_dir() or not core_routing.is_file() or not all((ROOT / "plugins" / n).is_dir() for n in plugin_names):
        fail("setup-repo skill, routing core, or plugin source directory is missing")

    real_home = Path(os.environ.get("HERMES_REAL_HOME", str(Path.home()))).expanduser().resolve()
    profiles_dir = Path(os.environ.get("HERMES_PROFILES_DIR", str(real_home / ".hermes/profiles"))).expanduser().resolve()
    profiles = discover_profiles(profiles_dir, profile_names)

    # Skill is shared: one copy under ~/.agents/skills. Plugin goes into every profile.
    targets: list[tuple[str, Path, Path]] = [("skill", real_home / ".agents/skills/ginflow", source_skill)]
    targets += [
        (f"{profile}/{plugin}", profiles_dir / profile / "plugins" / plugin, ROOT / "plugins" / plugin)
        for profile in profiles
        for plugin in plugin_names
    ]
    for key, destination, _ in targets:
        if destination.exists() and not destination.is_dir():
            fail(f"managed destination is not a directory: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if key != "skill" and backup_path(destination).exists():
            fail(f"backup already exists; resolve before install: {backup_path(destination)}")

    manifest: dict[str, Any] = {"version": VERSION, "source_root": str(ROOT), "skill": {}, "plugins": {}}
    rollback: list[tuple[Path, str | None]] = []
    try:
        for key, destination, source in targets:
            # Skill is a plain copy of repo source; overwrite without backup.
            backup = None if key == "skill" else backup_existing(destination)
            rollback.append((destination, backup))
            if destination.exists() or destination.is_symlink():
                remove_path(destination)
            copy_tree(source, destination)
            if destination.name == "ginflow-gate":
                # Copied gate cannot reach repo core/; it falls back to its own lib/routing.py.
                (destination / "lib").mkdir(exist_ok=True)
                shutil.copy2(core_routing, destination / "lib/routing.py")
            entry = {"path": str(destination), "hash": sha256(destination), "backup": backup}
            if key == "skill":
                manifest["skill"] = entry
                ok(f"Ginflow skill installed: {destination}")
            else:
                manifest["plugins"][key] = entry
                ok(f"{key}: plugin installed")
        write_manifest(manifest)
        ok(f"manifest written to {MANIFEST}")
    except Exception:
        print("❌ installation failed; restoring destinations", file=sys.stderr)
        for destination, backup in reversed(rollback):
            remove_path(destination)
            if backup:
                shutil.move(backup, destination)
        raise


# Rollback state stays in memory until every managed path is installed and the
# manifest is atomically committed.


def remove_managed(path: Path, expected_hash: str, backup: str | None) -> bool:
    if not path.exists() and not path.is_symlink():
        return True
    if sha256(path) != expected_hash:
        print(f"⚠️  conflict preserved: {path}", file=sys.stderr)
        return False
    remove_path(path)
    if backup and Path(backup).exists():
        shutil.move(backup, str(path))
    return True


def managed_entries(manifest: dict[str, Any]) -> list[tuple[str, Path, str, str | None]]:
    """(label, path, hash, backup) for v2 manifests and legacy per-profile v1 manifests."""
    entries: list[tuple[str, Path, str, str | None]] = []
    skill = manifest.get("skill")
    if skill:
        entries.append(("skill", Path(skill["path"]), skill["hash"], None))  # skill is never backed up
    for name, item in manifest.get("plugins", {}).items():
        entries.append((name, Path(item["path"]), item["hash"], item.get("backup")))
    for name, item in manifest.get("profiles", {}).items():  # legacy v1
        for key in ("skill", "plugin"):
            if key in item:
                backup = item.get(f"{key}_backup") if key == "plugin" else None
                entries.append((f"{name}:{key}", Path(item[key]), item[f"{key}_hash"], backup))
    return entries


def uninstall() -> None:
    if not MANIFEST.is_file():
        info("no Ginflow installation manifest found; nothing to uninstall")
        return
    entries = managed_entries(json.loads(MANIFEST.read_text()))
    conflicts = [path for _, path, digest, _ in entries if (path.exists() or path.is_symlink()) and sha256(path) != digest]
    if conflicts:
        for path in conflicts:
            print(f"⚠️  conflict preserved: {path}", file=sys.stderr)
        fail("uninstall blocked by conflicts; no managed paths changed")
    for label, path, digest, backup in entries:
        remove_managed(path, digest, backup)
        ok(f"{label}: removed")
    MANIFEST.unlink()


if not ARGS or ARGS[0] not in {"install", "uninstall"}:
    fail(f"usage: {Path(sys.argv[0]).name} install [profile ...]|uninstall")
if ARGS[0] == "install":
    install(ARGS[1:])
elif len(ARGS) == 1:
    uninstall()
else:
    fail("uninstall accepts no profile arguments")
PY
