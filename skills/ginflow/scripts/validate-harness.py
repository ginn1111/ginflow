#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from harness_core import artifact_gate, check, has, linked_artifacts, load_kanban_card, normalize_card
from project_config import config_exists, config_path, context_error, installed_profiles, resolve_board, reviewer_error


COMMAND_TIMEOUT = 5
def run_bounded(command, *, env=None, cwd=None):
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return "timeout"


def optional_row(tool, state, severity, evidence, recommendation=""):
    return {
        "pass": severity == "pass",
        "message": f"{tool}: {state}",
        "severity": severity,
        "tool": tool,
        "state": state,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def inspect_codegraph(target):
    tool = "codegraph"
    if target is None:
        return optional_row(tool, "not_exercised", "warning", "target workspace not supplied", "Run with --target <workspace>")
    if shutil.which(tool) is None:
        return optional_row(tool, "missing", "warning", "CodeGraph executable not found", "Install CodeGraph")
    if not (target / ".codegraph").is_dir():
        return optional_row(
            tool,
            "not_initialized",
            "warning",
            "target has no .codegraph directory",
            f"Run `codegraph init {target}`",
        )
    result = run_bounded([tool, "status", str(target)])
    if result == "timeout":
        return optional_row(tool, "timeout", "warning", "codegraph status timed out", f"Run `codegraph status {target}`")
    if result is None:
        return optional_row(tool, "missing", "warning", "CodeGraph executable disappeared", "Install CodeGraph")
    output = f"{result.stdout}\n{result.stderr}".lower()
    if any(word in output for word in ("not initialized", "not initialised", "no index")):
        return optional_row(
            tool,
            "not_initialized",
            "warning",
            "CodeGraph reports that the target is not indexed",
            f"Run `codegraph init {target}`",
        )
    if any(word in output for word in ("stale", "outdated", "needs sync", "changes pending")):
        return optional_row(tool, "stale", "warning", "CodeGraph index reports pending changes", f"Run `codegraph sync {target}`")
    if result.returncode != 0:
        return optional_row(tool, "unavailable", "warning", "CodeGraph status failed", f"Run `codegraph status {target}`")
    if any(word in output for word in ("healthy", "up to date", "up-to-date", "current", "indexed")):
        return optional_row(tool, "healthy", "pass", "CodeGraph index status completed successfully")
    return optional_row(tool, "malformed", "warning", "CodeGraph status returned unrecognized output", f"Run `codegraph status {target}`")


def inspect_optional_tools(target):
    rows = [inspect_codegraph(target)]
    status = "warning" if any(row["severity"] == "warning" for row in rows) else "pass"
    return {"status": status, "checks": rows}


def main():
    parser = argparse.ArgumentParser(description="Validate the ginflow five-subsystem harness")
    parser.add_argument("--setup-repo", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--board", help="Explicit Kanban board override")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--card", type=Path, help="Card JSON file; accepts normalized Ginflow or `hermes kanban show --json` shape")
    source.add_argument("--kanban-task-id", help="Read a live card with `hermes kanban show <id> --json`")

    parser.add_argument("--baseline-commit", help="Candidate completion commit to validate before closing a live card")
    parser.add_argument("--baseline-path", action="append", default=[], help="Candidate linked artifact path; repeat for each path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if bool(args.baseline_commit) != bool(args.baseline_path):
        parser.error("--baseline-commit and at least one --baseline-path must be supplied together")


    root = (args.setup_repo or Path(__file__).resolve().parents[3]).resolve()
    ginflow = (root / "skills/ginflow/SKILL.md").read_text()
    target = args.target.resolve() if args.target else None
    config_error = context_error(target) if target else None
    if target and not config_error:
        config_error = reviewer_error(target, installed_profiles())
    if target and not config_error and not config_exists(target):
        config_error = "project config is absent; run `/ginflow` to initialize .ginflow.yaml"
    board = resolve_board(target or Path.cwd(), args.board)
    local = ""
    local_path = None
    if target:
        for name in (".hermes.md", "AGENTS.md"):
            candidate = target / name
            if candidate.exists():
                local_path, local = candidate, candidate.read_text()
                break

    card_load_error = None
    if args.card:
        card_document = json.loads(args.card.read_text())
    elif args.kanban_task_id:
        card_document, card_load_error = load_kanban_card(args.kanban_task_id, board, target)
    else:
        card_document = {}
    card = normalize_card(card_document)

    if args.baseline_commit:
        card["artifact_baseline"] = {
            "commit": args.baseline_commit,
            "paths": args.baseline_path,
        }
    card_fields = ("id", "title", "objective", "scope", "acceptance", "workspace", "status", "assignee", "links")
    linked_docs = [candidate for _, candidate in linked_artifacts(card, target)]
    linked_artifact_exists = bool(linked_docs and any(path.is_file() for path in linked_docs))
    artifact_status = artifact_gate(card, target)
    optional_tools = inspect_optional_tools(target)

    verify_match = re.search(r"(?:Canonical (?:verification )?command|Verification)[^\n]*:\s*`?([^`\n]+)", local, re.I)
    verification_documented = bool(verify_match)

    subsystems = {
        "instructions": check("instructions", [
            (True, "Artifact repository provides shared ginflow instructions", "warning"),
            (all(has(ginflow, heading) for heading in ("## Project session startup", "## Execution contract", "## Definition of done", "## Completion report")), "Canonical ginflow instruction sections exist", "warning"),
            (not target or bool(local_path), "Target local instruction file exists when target supplied", "warning"),
            (not target or has(local, "come from `ginflow`"), "Target local instructions route shared workflow to ginflow when target supplied", "warning"),
        ]),
        "state": check("state", [
            (
                not config_error,
                "Project-local Kanban config matches the target workspace",
                "blocker",
                config_error or "project-local config is absent or matches the target",
                "Run `/ginflow` to initialize .ginflow.yaml or repair it before continuing.",
            ),
            (
                not card_load_error and bool(card) and all(card.get(field) for field in card_fields),
                "Selected card has required fields",
                "blocker",
                card_load_error or "required Ginflow fields are missing from the card body or metadata",
                "Use Objective, Scope, Acceptance, and Links sections in the card body, plus a real target workspace and assignee.",
            ),
            (linked_artifact_exists, "Linked target-local Governance Artifact exists", "blocker"),
            (
                artifact_status["baseline_complete"],
                "Card records a path-scoped completion commit baseline",
                "blocker",
                artifact_status["baseline_details"],
                artifact_status["baseline_resolution"],
            ),
            (
                artifact_status["matches"],
                "Linked artifacts match the recorded completion commit",
                "blocker",
                artifact_status["drift_details"],
                artifact_status["drift_resolution"],
            ),
            (not target or not (target / "session-handoff.md").exists(), "Mandatory root session handoff is absent", "warning"),
        ], exercised=bool(target)),
        "verification": check("verification", [
            (verification_documented, "Canonical project verification is documented", "blocker"),
            (has(ginflow, "Quote canonical") and has(ginflow, "exact fresh result"), "Fresh evidence format is required", "warning"),
        ], exercised=bool(target)),
        "scope": check("scope", [
            (has(ginflow, "One active card per mutable workspace"), "Mutable-workspace isolation rule exists", "warning"),
            (bool(card and all(card.get(field) for field in ("scope", "acceptance", "workspace"))), "Card tracks scope, acceptance, and workspace", "blocker"),
            (any(has(local, word) for word in ("forbidden", "boundaries", "sensitive paths")), "Target local boundaries exist", "warning"),
        ], exercised=bool(target)),
        "lifecycle": check("lifecycle", [
            (has(ginflow, "## Project session startup"), "Startup contract exists", "warning"),
            (has(ginflow, "## Session close and restart"), "Close/restart contract exists", "warning"),
            (has(ginflow, "Kanban card is default durable handoff"), "Kanban-first handoff exists", "warning"),
            (has(ginflow, "## Optional session handoff export"), "Optional export exists", "warning"),
            (not target or verification_documented, "Clean restart verification path is documented when target supplied", "blocker"),
        ]),
        "optional_tools": optional_tools,
    }
    result = {
        "setup_repo": str(root),
        "target": str(target) if target else None,
        "kanban_task_id": args.kanban_task_id,
        "kanban_board": board,
        "project_config": str(config_path(target).relative_to(target)) if target and config_path(target).is_file() else None,
        "project_config_error": config_error,
        "candidate_baseline": bool(args.baseline_commit),
        "card_load_error": card_load_error,
        "subsystems": subsystems,
    }
    statuses = {
        item["status"]
        for name, item in subsystems.items()
        if name != "optional_tools"
    }
    result["status"] = "blocker" if "blocker" in statuses else "warning" if "warning" in statuses else "pass"
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for name, item in subsystems.items():
            print(f"{name}: {item['status']}")
            for row in item["checks"]:
                print(f"  {'PASS' if row['pass'] else 'FAIL'} {row['message']}")
                if name == "optional_tools":
                    print(f"    Evidence: {row['evidence']}")
                    if row.get("recommendation"):
                        print(f"    Recommendation: {row['recommendation']}")
                else:
                    if not row["pass"] and row.get("details"):
                        print(f"    Details: {row['details']}")
                    if not row["pass"] and row.get("resolution"):
                        print(f"    Resolution: {row['resolution']}")
    return 2 if result["status"] == "blocker" else 0


if __name__ == "__main__":
    sys.exit(main())