# Completion

Native `kanban_request_review` (worker) and `kanban_complete` (reviewer) both pass through `ginflow-gate`.

## Worker: before `kanban_request_review`

- [ ] Run canonical project verification from target repo.
- [ ] Read `git status --short`; report only files under card workspace.
- [ ] Finalize every linked local spec/plan: YAML frontmatter at byte 0 with `status: completed`. Body status text is ignored.
- [ ] Commit those documents and card-scoped changes. Stage only exact linked artifacts and intended files.
- [ ] Record fresh command and exact result on the card.
- [ ] Call `kanban_request_review` with `metadata.verification_result` and `metadata.artifact_baseline` (commit matches).

## Reviewer: before `kanban_complete`

- [ ] Validate scope, acceptance, diff, evidence independently.
- [ ] Call `kanban_complete` with `metadata.verification_result` (`commit`, `command`, `result`) and matching `metadata.artifact_baseline` (`commit`, `paths`).
- [ ] `ginflow-gate` checks card fields, baseline commit, exact linked paths, drift. Invalid or unavailable evidence rejects the transition.
- [ ] Return invalid review with `kanban_request_changes`: `reason`, `evidence` (file:line, command, or gate error), `next_action`.

## Workspace warnings

Review workspace per `workspace-health-warnings.md`. Record findings under `Workspace warnings` on card and in report. Warnings do not block by default. Never copy warning policy or scanners into target repo.

## Evidence rules

- Project verification proves product behavior. Harness never substitutes for it.
- Temporary or ad-hoc checks are not evidence unless card targets that artifact.
- Canonical verification unavailable or failing: report blocked/not done.

## Manual/CI harness (optional)

```bash
# Startup/resume: reads task row, body, latest run metadata.
python3 <setup-repo>/skills/ginflow/scripts/validate-harness.py \
  --setup-repo <setup-repo> --target <target-repo> \
  --kanban-task-id "$TASK_ID" --json

# Candidate check before kanban_request_review.
python3 <setup-repo>/skills/ginflow/scripts/validate-harness.py \
  --setup-repo <setup-repo> --target <target-repo> \
  --kanban-task-id "$TASK_ID" --baseline-commit "$COMMIT" \
  --baseline-path docs/specs/<CARD-ID>.md --json
```

`--card <json-file>` accepts fixtures (normalized Ginflow JSON or saved `hermes kanban show --json`).

## Completed-card artifact gate

- Compare only linked paths against completion commit. Never whole repo. No per-file SHA fallback.
- Missing commit, path-list mismatch, missing artifact, committed or uncommitted change = drift. Blocks affected lifecycle use only. Unrelated paths and cards continue.
- Never silently advance completion commit.
- Never copy harness script into target repo. Report project verification and harness separately.
