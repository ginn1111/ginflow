#!/usr/bin/env python3
"""Integration test: ginflow-trace traces the full ginflow-gate lifecycle.

Drives the real ginflow-gate plugin (which wires @trace from ginflow-trace)
against a real Hermes Kanban card on an isolated board through the whole
lifecycle — create -> load -> validate -> complete (and a drift failure) —
and asserts every traced gate call lands on disk with the real gate function
name and the card's identity.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import ginflow_trace.decorator as decorator

# Isolate from an outer Kanban worker: its pinned board DB and write fence would leak into live fixtures.
for _key in [k for k in os.environ if k.startswith(("HERMES_KANBAN_", "HERMES_DELEGATED_"))]:
    del os.environ[_key]


TEST_BOARD = "ginflow-testing"

BODY = (
    "Objective: Integration trace card\n"
    "Scope:\n- trace\n"
    "Acceptance:\n- trace records gate call\n"
    "Links:\n- docs/specs/TRACE-INT.md"
)
SPEC = "---\nstatus: completed\n---\n# Trace integration\n"


def _load_gate_module() -> ModuleType:
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    return importlib.import_module("ginflow-gate.gate")


def _records(root: Path, filename: str) -> list[dict]:
    path = root / "logs" / filename
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@contextlib.contextmanager
def _temp_hermes_home(prefix):
    """Remove temp home safely despite a late Hermes cache writer.

    Root cause: fresh-home boot runs step_install_default_plugins, which launches
    a detached `python -I -c ... runpy.run_module('hermes_cli.default_plugins')`
    child via default_plugins.spawn_install. Its failure path calls
    memory_provider_migration._note_failure and recreates
    <home>/cache/left-core-default-plugins.failed after the CLI returns. Tests set
    HERMES_DISABLE_LAZY_INSTALLS=1 to prevent that child; bounded retry is a backstop.
    Body failures are never masked by cleanup failures.
    """
    home = tempfile.mkdtemp(prefix=prefix)
    failed = False
    try:
        yield home
    except BaseException:
        failed = True
        raise
    finally:
        deadline = time.monotonic() + 5.0
        while True:
            try:
                shutil.rmtree(home)
                break
            except FileNotFoundError:
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    if not failed:
                        raise OSError(f"could not remove temp Hermes home {home}: {exc}") from exc
                    break
                time.sleep(0.1)


def test_full_kanban_lifecycle_traced():
    with (
        tempfile.TemporaryDirectory(prefix="ginflow-trace-project-") as project,
        _temp_hermes_home("ginflow-trace-home-") as home,
    ):
        target = Path(project)
        (target / "docs/specs").mkdir(parents=True)
        (target / "docs/specs/TRACE-INT.md").write_text(SPEC)
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.name", "Ginflow Test"], cwd=target, check=True)
        subprocess.run(["git", "config", "user.email", "ginflow@example.test"], cwd=target, check=True)
        subprocess.run(["git", "add", "docs/specs/TRACE-INT.md"], cwd=target, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=target, check=True)
        baseline = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=target, text=True, capture_output=True, check=True
        ).stdout.strip()

        profile_home = Path(home) / "profiles" / "test"
        profile_home.mkdir(parents=True)
        env = os.environ | {
            "HERMES_DISABLE_LAZY_INSTALLS": "1", "HERMES_HOME": str(profile_home),
            "HERMES_KANBAN_HOME": str(Path(home) / "kanban-home"),
            "HERMES_KANBAN_BOARD": TEST_BOARD,
        }
        subprocess.run(["hermes", "kanban", "init"], env=env, check=True, capture_output=True, text=True)
        subprocess.run(
            ["hermes", "kanban", "boards", "create", TEST_BOARD],
            env=env, check=True, capture_output=True, text=True,
        )
        created = subprocess.run(
            ["hermes", "kanban", "--board", TEST_BOARD, "create", "TRACE-INT — integration trace",
             "--body", BODY, "--assignee", "ginb", "--workspace", f"dir:{target}",
             "--initial-status", "blocked", "--json"],
            env=env, check=True, capture_output=True, text=True,
        )
        task = json.loads(created.stdout)
        task_id = task["id"]

        gate = _load_gate_module()
        load_card = gate.load_card
        validate_completion = gate.validate_completion
        pre_tool_call = gate.pre_tool_call

        (target / ".ginflow.yaml").write_text(
            f"ginflow:\n  board: {TEST_BOARD}\n  workspace: {target}\n  trace: true\n"
        )
        root = target / ".ginflow"
        session = "itest"

        old = {
            key: os.environ.get(key)
            for key in ("GINFLOW_LOG", "HERMES_SESSION_WORKER_ID", "HERMES_KANBAN_TASK",
                        "HERMES_HOME", "HERMES_KANBAN_HOME", "HERMES_KANBAN_BOARD")
        }
        os.environ["GINFLOW_LOG"] = "1"
        os.environ["HERMES_SESSION_WORKER_ID"] = session
        os.environ["HERMES_KANBAN_TASK"] = task_id
        os.environ["HERMES_HOME"] = str(profile_home)
        os.environ["HERMES_KANBAN_HOME"] = env["HERMES_KANBAN_HOME"]
        os.environ["HERMES_KANBAN_BOARD"] = TEST_BOARD
        old_config_start = decorator.CONFIG_START
        decorator.CONFIG_START = lambda: target
        try:
            # 1) CREATE -> load_card — read the real card back through the gate.
            card = load_card(task_id, board=TEST_BOARD)
            assert card["id"] == task_id
            assert card["title"] == "TRACE-INT — integration trace"
            assert card["status"] == "blocked"

            # 2) validate_completion — card has committed completed spec + matching baseline.
            metadata = {
                "verification_result": {"commit": baseline, "command": "make test", "result": "passed"},
                "artifact_baseline": {"commit": baseline, "paths": ["docs/specs/TRACE-INT.md"]},
            }
            assert validate_completion(card, metadata) is None

            # 3) COMPLETE gate — valid completion is allowed (no block).
            allowed = pre_tool_call("kanban_complete", {
                "task_id": task_id, "metadata": metadata,
            }, "", board=TEST_BOARD)
            assert allowed is None, allowed

            # 4) Drift — modify the linked spec after baseline; completion must now block.
            (target / "docs/specs/TRACE-INT.md").write_text(SPEC + "\nchanged\n")
            blocked = pre_tool_call("kanban_complete", {
                "task_id": task_id, "metadata": metadata,
            }, "", board=TEST_BOARD)
            assert blocked is not None
            assert blocked["action"] == "block"
            assert "drift" in blocked["message"].lower() or "docs/specs/TRACE-INT.md" in blocked["message"]
        finally:
            decorator.CONFIG_START = old_config_start
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        # Every traced gate function must be recorded with its real name and status.
        records = _records(root, f"{session}__{task_id}.json")
        names = [r["function"] for r in records]
        assert "load_card" in names, names
        assert "validate_completion" in names, names
        assert "pre_tool_call" in names, names
        assert all(r["status"] == "success" for r in records), records
        allowed_functions = {
            "load_card", "validate_completion",
            "pre_tool_call", "linked_documents_missing_completion",
        }
        assert all(r["function"] in allowed_functions for r in records), records
    print("PASS: full kanban create -> complete lifecycle traced")


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    print("PASS: ginflow trace integration")
