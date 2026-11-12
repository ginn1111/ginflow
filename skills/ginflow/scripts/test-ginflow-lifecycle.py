#!/usr/bin/env python3
"""Canonical ginflow harness lifecycle integration test.

Runs the full ginflow flow as ONE flat sequence, reporting PASS/FAIL per
step, using an isolated temp target workspace, the dedicated
``ginflow-testing`` board, and a temp ``HERMES_HOME`` for any live
Kanban interaction.

Flow (each step is one row in the final report):
  1. init-context    -- persist/validate .ginflow.yaml (board + abs workspace)
  2. select-card     -- parse card body + required-field selection
  3. startup-gate    -- harness_core.startup_gate -> ready_to_start
  4. harness-validate-- validate-harness.py over the selected card (all pass)
  5. optional-tools  -- codegraph/mcp health via fake-bin (non-blocking)
  6. completion-gate -- ginflow-gate validate_completion + pre_tool_call
  7. drift-guard     -- artifact_gate baseline + drift detection

Exit code: 0 only when every step PASSES. Each step is executed and its
result reported even if an earlier step fails (so the whole flow is
visible in one run).
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Isolate from an outer Kanban worker: its pinned board DB and write fence would leak into live fixtures.
for _key in [k for k in os.environ if k.startswith(("HERMES_KANBAN_", "HERMES_DELEGATED_"))]:
    del os.environ[_key]


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills/ginflow/scripts/validate-harness.py"
TEST_BOARD = "ginflow-testing"


def _load(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _syspath_insert():
    lib = ROOT / "skills/ginflow/lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


CARD_ID = "LIFE-1"
CARD_BODY = (
    "Objective: Run full ginflow lifecycle\n"
    "Scope:\n- harness\n- gate\n"
    "Acceptance:\n- integrate in one flow\n"
    "Links:\n- docs/specs/LIFE-1.md\n- docs/plans/LIFE-1.md"
)


class Report:
    """Collect per-step PASS/FAIL so all steps run even when one fails."""

    def __init__(self):
        self.rows = []

    def record(self, name):
        def decorator(fn):
            try:
                detail = fn()
                self.rows.append((name, True, detail))
            except Exception as error:  # noqa: BLE001 - report any failure
                self.rows.append((name, False, str(error)))
            return fn
        return decorator

    def passed(self):
        return all(ok for _, ok, _ in self.rows)

    def render(self):
        out = []
        for name, ok, detail in self.rows:
            out.append(f"  {'PASS' if ok else 'FAIL'} {name}")
            if detail:
                out.append(f"    {detail}")
        return "\n".join(out)


def write_fake_bin(directory):
    """Write fake codegraph/hermes executables for optional-tool probing."""
    fake = Path(directory)
    fake.mkdir(exist_ok=True)
    (fake / "codegraph").write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "state = os.environ.get('FAKE_CODEGRAPH_STATE', 'healthy')\n"
        "if sys.argv[1:2] == ['status']:\n"
        "    if state == 'missing':\n"
        "        print('CodeGraph is not initialized', file=sys.stderr); raise SystemExit(1)\n"
        "    if state == 'stale':\n"
        "        print('CodeGraph index is stale'); raise SystemExit(0)\n"
        "    if state == 'unavailable':\n"
        "        print('status failed', file=sys.stderr); raise SystemExit(1)\n"
        "    print('CodeGraph index healthy')\n"
    )
    (fake / "hermes").write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "args = sys.argv\n"
        "if args[1:3] == ['profile', 'list']:\n"
        "    if os.environ.get('FAKE_PROFILE_STATE') != 'none': print('◆ marker-profile')\n"
        "    raise SystemExit(0)\n"
        "if args[-2:] == ['mcp', 'list']:\n"
        "    mode = os.environ.get('FAKE_MCP_STATE', 'healthy')\n"
        "    if mode == 'unavailable': raise SystemExit(1)\n"
        "    if mode == 'none': print('MCP Servers:')\n"
        "    else: print('MCP Servers:\\n  codegraph  codegraph serve --mcp  all  ✓ enabled')\n"
        "elif len(args) >= 2 and args[-2] == 'test':\n"
        "    print('connected')\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )
    for name in ("codegraph", "hermes"):
        (fake / name).chmod(0o755)
    return fake


def git(target, *args):
    return subprocess.run(
        ["git", *args], cwd=target, text=True, capture_output=True, check=True
    ).stdout.strip()


def run_harness(target, card_path, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--setup-repo", str(ROOT),
         "--target", str(target), "--card", str(card_path), "--json"],
        text=True, capture_output=True, env=env,
    )


def create_live_card(env, target):
    subprocess.run(["hermes", "kanban", "init"], env=env, text=True,
                   capture_output=True, check=True)
    boards = json.loads(subprocess.run(
        ["hermes", "kanban", "boards", "list", "--json"], env=env,
        text=True, capture_output=True, check=True,
    ).stdout)
    if not any(b["slug"] == TEST_BOARD for b in boards):
        subprocess.run(["hermes", "kanban", "boards", "create", TEST_BOARD],
                       env=env, text=True, capture_output=True, check=True)
    created = subprocess.run(
        ["hermes", "kanban", "--board", TEST_BOARD, "create", f"{CARD_ID} — lifecycle",
         "--body", CARD_BODY, "--assignee", "worker",
         "--workspace", f"dir:{target}", "--initial-status", "blocked", "--json"],
        env=env, text=True, capture_output=True, check=True,
    )
    return json.loads(created.stdout)["id"]


def main():
    parser = argparse.ArgumentParser(description="Canonical ginflow lifecycle test")
    parser.add_argument("--no-live", action="store_true",
                        help="Skip live-Kanban steps (completion gate + drift use file cards)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable report")
    args = parser.parse_args()

    _syspath_insert()
    project_config = _load("lifecycle_project_config", ROOT / "skills/ginflow/lib/project_config.py")
    harness_core = _load("lifecycle_harness_core", ROOT / "skills/ginflow/lib/harness_core.py")
    if str(ROOT / "plugins") not in sys.path:
        sys.path.insert(0, str(ROOT / "plugins"))
    gate = importlib.import_module("ginflow-gate.gate")

    report = Report()

    with tempfile.TemporaryDirectory(prefix="ginflow-lifecycle-") as project:
        target = Path(project)
        (target / "docs/specs").mkdir(parents=True)
        (target / "docs/plans").mkdir(parents=True)
        (target / "AGENTS.md").write_text(
            "Shared workflow rules come from `ginflow`.\n"
            "## Verification\nCanonical command: `make check`\n"
            "## Boundaries\nDo not edit generated files.\n"
        )
        spec = target / "docs/specs/LIFE-1.md"
        plan = target / "docs/plans/LIFE-1.md"
        spec.write_text("---\nstatus: completed\n---\n# LIFE-1 Spec\nObjective: integrate.\n")
        plan.write_text("---\nstatus: completed\n---\n# LIFE-1 Plan\nOrdered steps.\n")
        (target / "app.py").write_text("VERSION = 1\n")
        git(target, "init", "-q")
        git(target, "config", "user.name", "Ginflow Test")
        git(target, "config", "user.email", "ginflow@example.test")
        git(target, "add", "AGENTS.md", "app.py", "docs/specs/LIFE-1.md", "docs/plans/LIFE-1.md")
        git(target, "commit", "-qm", "baseline fixture")
        baseline_commit = git(target, "rev-parse", "HEAD")

        # ---- 1. init-context ----
        @report.record("init-context")
        def init_context():
            path = project_config.persist_context(target, board=TEST_BOARD)
            assert path == project_config.config_path(target)
            assert project_config.config_exists(target)
            assert project_config.context_error(target) is None
            assert project_config.resolve_board(target, env={}) == TEST_BOARD
            # explicit override wins over the persisted board
            assert project_config.resolve_board(target, explicit="override", env={}) == "override"
            return f".ginflow.yaml -> board={TEST_BOARD}"

        # ---- 2. select-card ----
        card_path = target / "card.json"
        card_doc = {
            "task": {
                "id": CARD_ID,
                "title": CARD_ID + " — lifecycle",
                "body": CARD_BODY,
                "assignee": "worker",
                "status": "ready",
                "workspace_kind": "dir",
                "workspace_path": str(target),
            },
            "runs": [],
        }

        @report.record("select-card")
        def select_card():
            parsed = harness_core.parse_card_body(CARD_BODY)
            assert parsed["objective"] == "Run full ginflow lifecycle"
            assert parsed["scope"] == ["harness", "gate"]
            assert parsed["acceptance"] == ["integrate in one flow"]
            assert parsed["links"] == ["docs/specs/LIFE-1.md", "docs/plans/LIFE-1.md"]
            normalized = harness_core.normalize_card(card_doc)
            required = ("id", "title", "objective", "scope", "acceptance",
                        "workspace", "status", "assignee", "links")
            assert all(normalized.get(f) for f in required), normalized
            card_path.write_text(json.dumps(normalized))
            return "card fields parsed + normalized"

        # ---- 3. startup-gate ----
        @report.record("startup-gate")
        def startup_gate():
            card = json.loads(card_path.read_text())
            gate_result = harness_core.startup_gate(card, target, target)
            assert gate_result["route"] == "ready_to_start", gate_result
            assert gate_result["valid"] is True
            assert gate_result["transition_required"] is True
            worktree_card = {**card, "workspace": f"worktree:{target}"}
            assert harness_core.startup_gate(worktree_card, target, target)["route"] == "ready_to_start"
            return "ready_to_start"

        # ---- 4. harness-validate ----
        @report.record("harness-validate")
        def harness_validate():
            result = run_harness(target, card_path)
            assert result.returncode == 0, result.stdout + result.stderr
            parsed = json.loads(result.stdout)
            assert parsed["status"] == "pass", parsed
            for name in ("instructions", "state", "verification", "scope", "lifecycle"):
                assert parsed["subsystems"][name]["status"] == "pass", name
            return "all non-optional subsystems pass"

        # ---- 5. optional-tools ----
        @report.record("optional-tools")
        def optional_tools():
            fake = write_fake_bin(target / "fake-bin")
            (target / ".codegraph").mkdir(exist_ok=True)
            env = os.environ | {
                "HERMES_PROFILE": "test-profile",
                "PATH": f"{fake}:{os.environ['PATH']}",
            }
            result = run_harness(target, card_path, env=env)
            assert result.returncode == 0, result.stdout + result.stderr
            parsed = json.loads(result.stdout)
            rows = parsed["subsystems"]["optional_tools"]["checks"]
            assert any(r["tool"] == "codegraph" and r["state"] == "healthy" for r in rows)
            # optional_tools never blocks the flow
            assert parsed["status"] == "pass", parsed["status"]
            return "codegraph healthy; warnings non-blocking"

        # ---- 6. completion-gate ----
        @report.record("completion-gate")
        def completion_gate():
            card = json.loads(card_path.read_text())
            card["status"] = "running"
            metadata = {
                "verification_result": {"commit": baseline_commit,
                                        "command": "make check", "result": "passed"},
                "artifact_baseline": {"commit": baseline_commit,
                                      "paths": ["docs/specs/LIFE-1.md", "docs/plans/LIFE-1.md"]},
            }
            # valid request-review and completion allowed; invalid evidence blocked
            error = gate.validate_completion(card, metadata)
            assert error is None, error
            # pre_tool_call resolves the card from Kanban; stub load_card to
            # the in-memory card so this stays a flat, self-contained flow.
            load_card = getattr(gate, "load_card")
            setattr(gate, "load_card", lambda task_id, board=None: card)
            try:
                for tool_name in ("kanban_request_review", "kanban_complete"):
                    allowed = gate.pre_tool_call(
                        tool_name, {"task_id": CARD_ID, "metadata": metadata}, "",
                        profile="worker",
                    )
                    assert allowed is None, allowed
                    blocked = gate.pre_tool_call(
                        tool_name, {"task_id": CARD_ID, "metadata": {}}, "",
                        profile="worker",
                    )
                    assert blocked and blocked["action"] == "block"
                    assert "verification_result" in blocked["message"] or "artifact_baseline" in blocked["message"]
            finally:
                setattr(gate, "load_card", load_card)
            return "valid->allow; missing evidence->block"

        # ---- 7. drift-guard ----
        @report.record("drift-guard")
        def drift_guard():
            completed = json.loads(card_path.read_text())
            completed["status"] = "done"
            completed["artifact_baseline"] = {
                "commit": baseline_commit,
                "paths": ["docs/specs/LIFE-1.md", "docs/plans/LIFE-1.md"],
            }
            prior = card_path.read_text()
            card_path.write_text(json.dumps(completed))
            try:
                clean = run_harness(target, card_path)
                assert clean.returncode == 0, clean.stdout + clean.stderr
                assert json.loads(clean.stdout)["status"] == "pass"
                # unrelated change does not drift
                (target / "app.py").write_text("VERSION = 2\n")
                git(target, "add", "app.py")
                git(target, "commit", "-qm", "unrelated change")
                unrelated = run_harness(target, card_path)
                assert unrelated.returncode == 0, unrelated.stdout + unrelated.stderr
                # linked artifact change after completion drifts
                spec.write_text("---\nstatus: completed\n---\n# LIFE-1 Spec\nCHANGED\n")
                git(target, "add", "docs/specs/LIFE-1.md")
                git(target, "commit", "-qm", "drift linked artifact")
                drifted = run_harness(target, card_path)
                assert drifted.returncode == 2, drifted.stdout + drifted.stderr
                drifted_result = json.loads(drifted.stdout)
                assert drifted_result["status"] == "blocker"
                return "clean+unrelated pass; linked-artifact change -> blocker"
            finally:
                card_path.write_text(prior)

    ok = report.passed()
    rendered = report.render()
    if args.json:
        print(json.dumps({
            "test": "ginflow-lifecycle",
            "status": "pass" if ok else "fail",
            "steps": [{"name": n, "pass": s, "detail": d} for n, s, d in report.rows],
        }, indent=2))
    else:
        print("ginflow lifecycle: full-flow integration test")
        print(rendered)
        print(f"RESULT: {'ALL PASS' if ok else 'FAILURE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
