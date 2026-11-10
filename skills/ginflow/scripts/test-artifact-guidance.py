#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/ginflow"


def require(text, values, source):
    missing = [value for value in values if value not in text]
    assert not missing, f"{source}: missing {missing}"


def main():
    skill = (SKILL / "SKILL.md").read_text()
    layout = (SKILL / "references/doc-layout.md").read_text()
    content = (SKILL / "references/artifact-content-guide.md").read_text()
    kanban = (SKILL / "references/kanban-guide.md").read_text()
    drift = (SKILL / "references/drift-detect.md").read_text()
    workspace_warnings = (SKILL / "references/workspace-health-warnings.md").read_text()
    evals = json.loads((SKILL / "evals/evals.json").read_text())["evals"]
    agents_template = (ROOT / "templates/hermes.md").read_text()

    artifact_paths = (
        "Target Spec artifact",
        "Target Plan artifact",
        "Target Handoff artifact",
        "Target ADR location",
    )
    require(skill, artifact_paths, "SKILL.md")
    require(layout, artifact_paths, "doc-layout.md")
    require(kanban, ("<target-spec-path>", "<target-plan-path>"), "kanban-guide.md")

    require(content, (
        "## Authority and boundaries",

        "## Spec",
        "## Plan",
        "## Kanban card",
        "## ADR",
        "## Session handoff",
        "observable, testable, atomic",
        "never invent them",
        "Record unresolved drift on card",
        "docs/adrs/NNNN-<kebab-title>.md",
    ), "artifact-content-guide.md")

    target_drift_contract = (
        "## Drift detection",
        "canonical verification command",
        "generated",
        "authority",
        "unresolved drift on the selected Kanban card",
    )
    require(skill, (
        "No selected card blocks project execution",
        "Never copy harness script into target repo",
        "Report project verification and ginflow harness as separate results",
        "Completed-card artifact gate",
        "artifact_baseline",
        "Unrelated cards and unlinked project work may continue",
        "Do not compare the whole repository",
        "Do not use per-file SHA fallback",
        "--kanban-task-id",
        "--baseline-commit",
        "Hermes-generated task ID",
        "--initial-status blocked",
        "do not force `--skill ginflow`",
        "assigned to the current profile",
        "do not invent a `--body` option",
        "synchronously validates required card fields",
        "One active card per mutable workspace",
        "isolated worktree",
        "references/workspace-health-warnings.md",
        "Workspace warnings",
    ), "SKILL.md")
    require(workspace_warnings, (
        "Warnings do not block completion by default",
        "Missing runtime config contract",
        "Error suppression anti-pattern",
        "Unrelated workspace changes",
        "## Route healing requests",
        "Current blocker",
        "Optional in-scope warning",
        "Unrelated warning",
        "Completed-card warning",
        "permit read-only inspection and task shaping only",
        "Never silently expand scope",
        "Do not copy this policy into target repo",
    ), "workspace-health-warnings.md")
    eval_ids = [case["id"] for case in evals]
    assert len(eval_ids) == len(set(eval_ids)), "eval IDs must be unique"
    warning_evals = {case.get("name") for case in evals if 16 <= case["id"] <= 20}
    assert warning_evals == {
        "workspace-missing-config-warning",
        "workspace-secret-risk-blocker",
        "workspace-unrelated-change-warning",
        "workspace-error-suppression-blocker",
        "workspace-health-clean",
    }, f"workspace warning eval coverage changed: {warning_evals}"
    require(kanban, ("No selected card blocks execution", "never copy harness into target repo", "artifact_baseline", "Never silently advance", "Unrelated paths and cards remain unblocked", "Objective:", "Acceptance:", "Links:", "--kanban-task-id"), "kanban-guide.md")
    require(drift, ("Never copy harness script into target repo", "Project verification: pass|fail|blocked", "artifact_baseline", "Advancing repository `HEAD` with unrelated changes does not cause drift", "Unrelated work may continue", "Editorial only", "hermes kanban show", *target_drift_contract), "drift-detect.md")
    require(skill, ("ginflow-gate", "Any worker may complete", "artifact_baseline"), "SKILL.md")
    require(kanban, ("Any worker assigned to card makes `kanban_complete`", "ginflow-gate"), "kanban-guide.md")
    require(drift, ("ginflow-gate", "Any assigned worker may call `kanban_complete`"), "drift-detect.md")

    duplicate_snapshots = []
    for candidate in (ROOT / "skills" / "ginflow-workspace").rglob("SKILL.md"):
        if "\nname: ginflow\n" in f"\n{candidate.read_text()}\n":
            duplicate_snapshots.append(str(candidate.relative_to(ROOT)))
    assert not duplicate_snapshots, f"evaluation snapshots must not shadow live ginflow skill: {duplicate_snapshots}"
    require(agents_template, (*target_drift_contract, "artifact_baseline", "blocks use of that card", "Unrelated work remains unblocked"), "templates/hermes.md")

    for template in ("spec.md", "plan.md", "kanban-task.md", "session-handoff.md"):
        text = (SKILL / "templates" / template).read_text()
        require(text, ("references/artifact-content-guide.md",), template)

    legacy_paths = ("`briefs/<CARD-ID>.md`", "`specs/<CARD-ID>.md`", "`plans/<CARD-ID>.md`", "`adrs/`")
    for path in (SKILL / "SKILL.md", SKILL / "references/doc-layout.md", SKILL / "references/kanban-guide.md"):
        text = path.read_text()
        found = [value for value in legacy_paths if value in text]
        assert not found, f"{path.name}: legacy root paths remain: {found}"

    print("ginflow artifact guidance test passed")


if __name__ == "__main__":
    main()
