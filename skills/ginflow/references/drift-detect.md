# Verification separation

Use three separate checks. Never merge their meaning.

## 1. Project verification

Run exact canonical command declared by target repo from target root, for example:

```bash
make verify
```

Target may instead declare `./verify.sh` or another project-native command. Ginflow does not force script name or location.

Purpose:
- prove project behavior matches project rules
- block completion when command fails or is unavailable

### What the target project documents

Keep the project-specific drift contract in target-repo `.hermes.md`. It must name:

- the canonical verification command and required working directory
- the authoritative local rules and task artifacts it checks
- generated files or schemas that must be regenerated after their sources change
- the expected response to drift: update the authority artifact first, regenerate dependents, rerun verification, and record unresolved drift on the selected Kanban card

Do not copy setup-repo profile checks or the ginflow harness into the target project. A target may link to a longer local runbook when the contract needs more detail.

Example target-local section:

```markdown
## Drift detection
- Run `make verify` from the repository root.
- Treat `.hermes.md`, the selected card, and its linked spec/plan as authorities.
- Regenerate `api/generated/` after changing `api/schema.yaml`.
- Resolve authority conflicts before implementation; record unresolved drift on the selected card.
```

## 2. Ginflow harness

Run harness from setup repo or deployed ginflow skill against target repo and selected Kanban card. Never copy harness script into target repo, add it to target dependencies, or include it in project verification.

Purpose:
- detect workflow readiness and drift
- report result separately from project verification
- block affected lifecycle stage for missing card, wrong workspace, missing acceptance, missing required artifact, missing completion verification path, or completed-card artifact drift
- report other drift as warning

Harness unavailable is a warning and never substitutes for project verification.

For a live Hermes card, let the harness call `hermes kanban show <task-id> --json` itself:

```bash
python3 <setup-repo>/skills/ginflow/scripts/validate-harness.py \
  --setup-repo <setup-repo> --target <target-repo> \
  --kanban-task-id "$TASK_ID" --json
```

The adapter reads Objective, Scope, Acceptance, and Links sections from the task body; workspace/status/assignee/ID from the task row; and `artifact_baseline` from latest completion-run metadata. Use harness `--board <slug>` for a non-current board; direct CLI placement is `hermes kanban --board <slug> show ...`. Saved `hermes kanban show --json` output may instead be passed with `--card` for deterministic fixtures.

### Completed-card linked-artifact validation

Ginflow permits this baseline commit without human review. The worker must commit every linked artifact and stage only exact linked artifacts plus card-scoped implementation files. Worker prepares truthful review-request metadata: verification evidence plus `artifact_baseline` containing completion commit and exact linked target-local paths. Assigned worker calls `kanban_request_review`; reviewer calls final `kanban_complete` after independent validation. `ginflow-gate` is enforcement authority and validates card fields, metadata, baseline commit, exact paths, and drift during both tool calls. Invalid or unavailable evidence rejects transition.

```json
{
  "artifact_baseline": {
    "commit": "<git-commit>",
    "paths": [

      "docs/specs/GIN-123.md"
    ]
  }
}
```

`ginflow-gate` performs this validation during native `kanban_request_review` and `kanban_complete` tool calls. External harness checks remain optional manual/CI evidence.

The external harness compares only those paths against the completion commit when the completed card is selected for startup, resume, handoff, or derived work. Advancing repository `HEAD` with unrelated changes does not cause drift. Uncommitted linked-artifact edits, later committed edits, missing paths, unavailable commits, and a path list that differs from the card's local links are blockers. The comparison is actor-agnostic: it detects a human or agent edit but cannot decide whether that edit is material.

When blocked, do not use that card as authority. Unrelated work may continue. Present these human decisions:

1. **New intent:** restore the completed artifact, create new versioned docs plus a follow-up card, and link them back to the completed card and original artifacts.
2. **Changed completed scope:** reopen the card, reconcile docs, implementation, acceptance, and verification evidence; commit the result, record the new completion commit, rerun verification and the harness, and complete again.
3. **Editorial only:** after explicit human classification, commit the editorial edit, advance the baseline commit, and record an approval note without reopening implementation work.

Never silently replace the completion commit. Do not fall back to per-file hashes. The human must choose a resolution first.

## 3. Repository artifact verification

Run from the Ginflow artifact repository:

```bash
make verify
```

Checks:
- standalone harness validation passes
- optional workspace tooling reports health or advisory warnings
- canonical artifact files are committed

Purpose:
- prove the repository artifacts and harness remain internally consistent

## Report shape

```text
Project verification: pass|fail|blocked
Ginflow harness: pass|warning|blocker|unavailable
Optional runtime integration: pass|warning|not-run
```

Project verification comes first during real work. Ginflow harness remains external. Repository verification checks artifact and harness health; runtime integrations are optional and out of scope.
