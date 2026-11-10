#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills/ginflow/scripts/validate-harness.py"

help_result = subprocess.run([sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True)
assert help_result.returncode == 0
assert "--board" not in help_result.stdout, help_result.stdout
CARD_FIELDS = {
    "id": "TEST-1",
    "title": "Test",
    "objective": "Verify gate",
    "scope": ["target"],
    "acceptance": ["check passes"],
    "workspace": "",
    "status": "ready",
    "assignee": "worker",
    "links": ["docs/specs/TEST-1.md"],
}


def run(target, card=None, task_id=None, env=None, baseline_commit=None, baseline_paths=None):
    command = ["python3", str(SCRIPT), "--setup-repo", str(ROOT), "--target", str(target), "--json"]
    if card:
        command += ["--card", str(card)]
    if task_id:
        command += ["--kanban-task-id", task_id]

    if baseline_commit:
        command += ["--baseline-commit", baseline_commit]
    for path in baseline_paths or []:
        command += ["--baseline-path", path]
    return subprocess.run(command, text=True, capture_output=True, env=env)


def git(target, *args):
    return subprocess.run(
        ["git", *args], cwd=target, text=True, capture_output=True, check=True
    ).stdout.strip()


def create_live_card(env, target, body, board=None):
    subprocess.run(["hermes", "kanban", "init"], env=env, text=True, capture_output=True, check=True)
    if board:
        subprocess.run(
            ["hermes", "kanban", "boards", "create", board],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
    create_command = ["hermes", "kanban"]
    if board:
        create_command += ["--board", board]
    created = subprocess.run(
        create_command + [
            "create", "TEST-1 — Test",
            "--body", body,
            "--assignee", "worker",
            "--workspace", f"dir:{target}",
            "--initial-status", "blocked",
            "--json",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(created.stdout)["id"]


def main():
    with tempfile.TemporaryDirectory(prefix="ginflow-harness-") as directory:
        target = Path(directory)
        (target / "AGENTS.md").write_text(
            "Shared workflow rules come from `ginflow`.\n"
            "## Verification\nCanonical command: `make check`\n"
            "## Boundaries\nDo not edit generated files.\n"
        )

        missing = run(target)
        assert missing.returncode == 2, missing.stdout + missing.stderr
        missing_result = json.loads(missing.stdout)
        assert missing_result["status"] == "blocker"
        assert missing_result["subsystems"]["state"]["status"] == "blocker"

        card = target / "card.json"
        complete = CARD_FIELDS | {"workspace": f"dir:{target}"}
        card.write_text(json.dumps(complete))
        (target / "docs/specs").mkdir(parents=True)
        (target / "docs/specs/TEST-1.md").write_text("# Spec\n")
        valid = run(target, card)
        assert valid.returncode == 0, valid.stdout + valid.stderr
        valid_result = json.loads(valid.stdout)
        assert valid_result["status"] == "pass", valid.stdout

        spec_only = complete | {"links": ["docs/specs/TEST-1.md"]}
        card.write_text(json.dumps(spec_only))
        spec_valid = run(target, card)
        assert spec_valid.returncode == 0, spec_valid.stdout + spec_valid.stderr
        assert json.loads(spec_valid.stdout)["status"] == "pass"

        fake_bin = target / "fake-bin"
        fake_bin.mkdir()
        (fake_bin / "codegraph").write_text(
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
            "    if state == 'malformed':\n"
            "        print('???'); raise SystemExit(0)\n"
            "    if state == 'timeout':\n"
            "        import time; time.sleep(6)\n"
            "    print('CodeGraph index healthy')\n"
        )
        (fake_bin / "codegraph").chmod(0o755)
        (target / ".codegraph").mkdir()
        optional_env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}"}
        optional = run(target, card, env=optional_env)
        assert optional.returncode == 0, optional.stdout + optional.stderr
        optional_result = json.loads(optional.stdout)
        assert optional_result["subsystems"]["optional_tools"]["status"] == "pass"
        assert any(
            row["tool"] == "codegraph" and row["state"] == "healthy"
            for row in optional_result["subsystems"]["optional_tools"]["checks"]
        )

        missing_env = optional_env | {"FAKE_CODEGRAPH_STATE": "missing"}
        missing_index = run(target, card, env=missing_env)
        assert missing_index.returncode == 0, missing_index.stdout + missing_index.stderr
        missing_index_result = json.loads(missing_index.stdout)
        codegraph_warning = next(
            row for row in missing_index_result["subsystems"]["optional_tools"]["checks"]
            if row["tool"] == "codegraph"
        )
        assert codegraph_warning["state"] == "not_initialized"
        assert "codegraph init" in codegraph_warning["recommendation"]

        for state, expected in (("stale", "stale"), ("unavailable", "unavailable"), ("malformed", "malformed"), ("timeout", "timeout")):
            result = json.loads(run(target, card, env=optional_env | {"FAKE_CODEGRAPH_STATE": state}).stdout)
            row = next(row for row in result["subsystems"]["optional_tools"]["checks"] if row["tool"] == "codegraph")
            assert row["state"] == expected, row
            assert row["severity"] == "warning", row

        human = subprocess.run(
            ["python3", str(SCRIPT), "--setup-repo", str(ROOT), "--target", str(target), "--card", str(card)],
            text=True, capture_output=True, env=missing_env,
        )
        assert "Recommendation:" in human.stdout
        assert "codegraph init" in human.stdout


        kanban_show = {
            "task": {
                "id": "TEST-1",
                "title": "TEST-1 — Test",
                "body": (
                    "Objective: Verify gate\n"
                    "Scope:\n- target\n"
                    "Acceptance:\n- check passes\n"
                    "Links:\n- docs/specs/TEST-1.md"
                ),
                "assignee": "worker",
                "status": "ready",
                "workspace_kind": "dir",
                "workspace_path": str(target),
            },
            "latest_summary": None,
            "parents": [],
            "children": [],
            "comments": [],
            "events": [],
            "runs": [],
        }
        card.write_text(json.dumps(kanban_show))
        actual_shape = run(target, card)
        assert actual_shape.returncode == 0, actual_shape.stdout + actual_shape.stderr
        assert json.loads(actual_shape.stdout)["status"] == "pass"

        malformed_show = json.loads(json.dumps(kanban_show))
        malformed_show["task"]["body"] = (
            "Objective: Verify gate\n"
            "Scope:\n- target\n"
            "Links:\n- docs/specs/TEST-1.md"
        )
        card.write_text(json.dumps(malformed_show))
        malformed = run(target, card)
        assert malformed.returncode == 2, malformed.stdout + malformed.stderr
        malformed_result = json.loads(malformed.stdout)
        assert malformed_result["status"] == "blocker"
        required = next(
            check for check in malformed_result["subsystems"]["state"]["checks"]
            if check["message"] == "Selected card has required fields"
        )
        assert required["pass"] is False

        with tempfile.TemporaryDirectory(prefix="ginflow-kanban-home-") as hermes_home:
            env = os.environ | {"HERMES_HOME": hermes_home, "HERMES_KANBAN_HOME": hermes_home + "/kanban-home"}
            task_id = create_live_card(env, target, kanban_show["task"]["body"])
            live_card = run(target, task_id=task_id, env=env)
            assert live_card.returncode == 0, live_card.stdout + live_card.stderr
            assert json.loads(live_card.stdout)["status"] == "pass"
            missing_card = run(target, task_id="t_missing", env=env)
            assert missing_card.returncode == 2, missing_card.stdout + missing_card.stderr
            missing_result = json.loads(missing_card.stdout)
            assert missing_result["status"] == "blocker"
            assert "t_missing" in missing_result["card_load_error"]

        incomplete = complete.copy()
        del incomplete["acceptance"]
        card.write_text(json.dumps(incomplete))
        blocked = run(target, card)
        assert blocked.returncode == 2
        assert json.loads(blocked.stdout)["status"] == "blocker"

        brief = target / "docs/specs/TEST-1.md"
        (target / "app.py").write_text("VERSION = 1\n")
        git(target, "init", "-q")
        git(target, "config", "user.name", "Ginflow Test")
        git(target, "config", "user.email", "ginflow@example.test")
        git(target, "add", "AGENTS.md", "app.py", "docs/specs/TEST-1.md")
        git(target, "commit", "-qm", "complete TEST-1")
        completion_commit = git(target, "rev-parse", "HEAD")
        with tempfile.TemporaryDirectory(prefix="ginflow-kanban-home-") as hermes_home:
            env = os.environ | {"HERMES_HOME": hermes_home, "HERMES_KANBAN_HOME": hermes_home + "/kanban-home"}
            task_id = create_live_card(env, target, kanban_show["task"]["body"])
            candidate = run(
                target,
                task_id=task_id,
                env=env,
                baseline_commit=completion_commit,
                baseline_paths=["docs/specs/TEST-1.md"],
            )
            assert candidate.returncode == 0, candidate.stdout + candidate.stderr
            assert json.loads(candidate.stdout)["status"] == "pass"
            subprocess.run(
                [
                    "hermes", "kanban", "complete", task_id,
                    "--summary", "verified",
                    "--metadata", json.dumps({
                        "artifact_baseline": {
                            "commit": completion_commit,
                            "paths": ["docs/specs/TEST-1.md"],
                        },
                    }),
                ],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            live_completed = run(target, task_id=task_id, env=env)
            assert live_completed.returncode == 0, live_completed.stdout + live_completed.stderr
            assert json.loads(live_completed.stdout)["status"] == "pass"

        completed = json.loads(json.dumps(kanban_show))
        completed["task"]["status"] = "done"
        completed["runs"] = [{
            "id": 2,
            "status": "completed",
            "outcome": "completed",
            "metadata": {
                "artifact_baseline": {
                    "commit": completion_commit,
                    "paths": ["docs/specs/TEST-1.md"],
                },
            },
        }, {
            "id": 1,
            "status": "completed",
            "outcome": "completed",
            "metadata": {
                "artifact_baseline": {
                    "commit": "obsolete-run",
                    "paths": ["docs/specs/TEST-1.md"],
                },
            },
        }]
        card.write_text(json.dumps(completed))
        unchanged = run(target, card)
        assert unchanged.returncode == 0, unchanged.stdout + unchanged.stderr

        (target / "app.py").write_text("VERSION = 2\n")
        git(target, "add", "app.py")
        git(target, "commit", "-qm", "unrelated implementation change")
        unrelated = run(target, card)
        assert unrelated.returncode == 0, unrelated.stdout + unrelated.stderr

        brief.write_text("# Brief\n\nHuman changed acceptance after completion.\n")
        git(target, "add", "docs/specs/TEST-1.md")
        git(target, "commit", "-qm", "change completed acceptance")
        drifted = run(target, card)
        assert drifted.returncode == 2, drifted.stdout + drifted.stderr
        drifted_result = json.loads(drifted.stdout)
        assert drifted_result["status"] == "blocker"
        drift_check = next(
            row
            for row in drifted_result["subsystems"]["state"]["checks"]
            if row["message"] == "Linked artifacts match the recorded completion commit"
        )
        assert not drift_check["pass"]
        assert "docs/specs/TEST-1.md" in drift_check["details"]
        assert "create new versioned docs" in drift_check["resolution"]
        assert "link back" in drift_check["resolution"]
        assert "reopen card TEST-1" in drift_check["resolution"]
        assert "editorial" in drift_check["resolution"]

        current_commit = git(target, "rev-parse", "HEAD")
        uncommitted = complete | {
            "status": "in_progress",
            "artifact_baseline": {
                "commit": current_commit,
                "paths": ["docs/specs/TEST-1.md"],
            }
        }
        brief.write_text("# Brief\n\nUncommitted completion edit.\n")
        card.write_text(json.dumps(uncommitted))
        dirty = run(target, card)
        assert dirty.returncode == 2, dirty.stdout + dirty.stderr
        dirty_result = json.loads(dirty.stdout)
        dirty_check = next(
            row
            for row in dirty_result["subsystems"]["state"]["checks"]
            if row["message"] == "Linked artifacts match the recorded completion commit"
        )
        assert not dirty_check["pass"]
        assert "commit linked artifacts" in dirty_check["resolution"].lower()

        no_baseline = complete | {"status": "done"}
        card.write_text(json.dumps(no_baseline))
        unguarded = run(target, card)
        assert unguarded.returncode == 2, unguarded.stdout + unguarded.stderr
        unguarded_result = json.loads(unguarded.stdout)
        baseline_check = next(
            row
            for row in unguarded_result["subsystems"]["state"]["checks"]
            if row["message"] == "Card records a path-scoped completion commit baseline"
        )
        assert not baseline_check["pass"]
        assert "reopen card test-1" in baseline_check["resolution"].lower()

        brief.write_text("# Brief\n\nHuman changed acceptance after completion.\n")
        untracked_spec = target / "docs/specs/TEST-1.md"
        untracked_spec.parent.mkdir(parents=True, exist_ok=True)
        untracked_spec.write_text("# Uncommitted spec\n")
        missing_from_commit = complete | {
            "status": "in_progress",
            "links": ["docs/specs/TEST-1.md", "docs/plans/TEST-1.md"],
            "artifact_baseline": {
                "commit": current_commit,
                "paths": ["docs/specs/TEST-1.md", "docs/plans/TEST-1.md"],
            },
        }
        card.write_text(json.dumps(missing_from_commit))
        uncommitted_new = run(target, card)
        assert uncommitted_new.returncode == 2, uncommitted_new.stdout + uncommitted_new.stderr
        uncommitted_new_result = json.loads(uncommitted_new.stdout)
        baseline_check = next(
            row
            for row in uncommitted_new_result["subsystems"]["state"]["checks"]
            if row["message"] == "Card records a path-scoped completion commit baseline"
        )
        assert not baseline_check["pass"]

    print("ginflow Kanban harness test passed")


if __name__ == "__main__":
    main()
