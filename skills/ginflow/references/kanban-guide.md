# Kanban guide

## Gate

Pre-card work (shaping) may brainstorm, inspect read-only context, draft package artifacts, and draft card content. Execution requires one selected card before implementation investigation, code change, dispatch, progress, verification, completion, or handoff.

No selected card blocks execution. Selected card requires ID, title, objective, scope, acceptance, workspace, status, assignee, and links. Missing field blocks execution until repaired.

Thin card pattern:
- title
- 1-2 sentence objective
- scope
- acceptance
- link to artifact if present

Use these exact body labels on Hermes Kanban cards; the external harness parses them from `hermes kanban show --json`:

```text
Objective: <what to achieve>
Scope:
- <files/dirs/areas>
Acceptance:
- <observable completion check>
Links:
- docs/specs/<CARD-ID>.md
```

Pass workspace and assignee through Kanban task fields, not duplicate body prose. The harness maps `workspace_kind` + `workspace_path`, status, assignee, and ID from the task row. On completed cards it reads `artifact_baseline` from the latest run metadata.

Use a stable human-facing card key chosen before creation for linked artifacts; use the separate Hermes-generated task ID (`t_...`) for Kanban commands:

- `docs/specs/<CARD-ID>.md`
- `docs/plans/<CARD-ID>.md`

Put the key in the task title and explicit `Links:` paths. The harness follows those links rather than deriving filenames from the generated task ID.

Draft card and artifact content before writing. Create the card assigned to the current profile, with its future links and `--initial-status blocked`. Write linked artifacts, then unblock once readiness passes. Current profile loads its canonical local Ginflow skill; do not force `--skill ginflow`.

For a malformed existing body, keep the task blocked and have the human edit title/body in the Kanban dashboard before rerunning the harness. `hermes kanban edit` is only for completed-task recovery fields, not body edits. Do not invent a CLI `--body` repair command or acceptance criteria. If dashboard repair is unavailable, replacing the card requires human approval and an explicit backlink/comment.

Before closing unfinished or blocked work, record outcome, changed files, verification, blockers, next step, and accurate status on card. Optional Markdown handoff export does not replace or mutate card.

Before completion, re-run canonical verification in target repo and derive changed-file evidence from target-repo `git status --short`. Temporary checks outside card workspace do not prove completion.

Before `kanban_request_review`, worker prepares truthful verification evidence and exact linked target-local paths in `artifact_baseline`. Human review is not required for this baseline commit; never include unrelated work. The worker must commit every linked artifact and stage only exact linked artifacts plus intended card work. `ginflow-gate` validates card fields, verification metadata, baseline commit, exact paths, and drift during both `kanban_request_review` and final reviewer `kanban_complete`. Invalid or unavailable evidence rejects transition. Before startup, resume, handoff, or derived work involving that card, compare only those paths against commit. Unrelated paths and cards remain unblocked. Propose:

- restore the completed docs, create new versioned docs and a follow-up card, and link back to the completed card;
- reopen the card, reconcile docs with implementation and evidence, commit, record a new completion commit, rerun verification and the harness, and complete again; or
- after explicit human classification as editorial, commit the edit and advance the baseline with an approval note.

Never silently advance the completion commit or substitute per-file hashes.

Optional manual/CI candidate check:

```bash
python3 <setup-repo>/skills/ginflow/scripts/validate-harness.py \
  --setup-repo <setup-repo> --target <target-repo> \
  --kanban-task-id "$TASK_ID" --baseline-commit "$COMMIT" \
  --baseline-path docs/specs/<CARD-ID>.md --json
```

Assigned worker requests review with `kanban_request_review(summary=..., metadata={"verification_result": ..., "artifact_baseline": ...})`. Reviewer makes final `kanban_complete` call after independent validation. `ginflow-gate` revalidates synchronously before each mutation and rejects invalid output. External harness rerun is optional manual/CI evidence.

Invalid review: reviewer calls `kanban_request_changes` with a minimal handoff (`reason`, `evidence`, `next_action`) so the worker can fix and re-request review. This is a normal rework loop, not a blocker; `kanban_block` stays reserved for external blockers.

Workspace rule:
- use real target repo
- `dir:/abs/path` for existing checkout
- `worktree` for isolated code changes

Do not leave project work in scratch workspace if files must be read from repo.

## Feedback boundary

Notification transport remains adapter-owned.

## Task notifications

Do not launch a `/background` watcher for a selected `running` card. Card creation from a persistent TUI or gateway session auto-subscribes the originating session when `kanban.auto_subscribe_on_create` is enabled; `subscribed: true` confirms registration. Let the dispatcher deliver terminal events and remove the subscription after `done` or `archived`. When creation does not confirm a subscription, use the normal Kanban notification subscription surface or explicit board reads instead of hidden polling.

Run target-declared project verification first. Run ginflow harness externally against target and selected card; never copy harness into target repo. Report project verification and harness result separately.
After artifact-repository updates, run `make verify` for standalone repository health. Runtime integration checks are optional and external.

## Stacking

A child card does not wait for its parent's PR merge. `ginflow-gate` (`kanban_task_completed` hook, `stacking.py`) acts when the completion makes all parents of a `worktree` child `done`, in a repo with `.ginflow.yaml`:

- one parent: `wt/<child>` is created from the parent branch head and `<repo>/.worktrees/<child>` is its worktree; Hermes reuses it.
- several parents: branch from the first parent (link order), `git merge --no-ff` the rest. Conflict: merge aborted (clean tree), child blocked `needs_input` with `required_action: resolve merge of <branches>`.
- child gets `[ginflow-stack] base=<branches> head=<sha>`.
- child already `running`/`done`/`archived`: no git change; `[ginflow-stack] stale-base` comment + notify when its branch lacks a parent head.
- parent without a worktree (`dir:`): skipped. Hook is observer-only; failures are logged.

Publish: exactly one parent with an open PR (`ginflow-publish: <url>` comment, `gh pr view` state `OPEN`) opens the child PR with `--base <parent branch>`. Several parents: base is the configured target and the body lists open parent PRs as `Merge after: <urls>`. Merged or absent parent PR: configured target.

## PR feedback

`ginflow pr sync [--board B] [--project P]` (run by hand or cron; Hermes has no PR event hook) turns PR review feedback into a follow-up card on the same branch:

- candidates: `done` cards with a `ginflow-publish: <url>` comment and no `[ginflow-pr] merged|closed` comment. GitHub only; GitLab URLs print `skip <url>: provider gitlab not supported yet`.
- new items = review bodies (incl. `CHANGES_REQUESTED`), issue comments and inline comments newer than the latest `[ginflow-pr] synced=<iso>` comment (default: card `completed_at`). Bodies starting with `[ginflow]` are ignored: Gin and ginflow share one GitHub account, so that prefix is the only author filter.
- no open feedback card for the PR: create `<KEY>-fb<N> — PR #<n> feedback` on the PR head branch (`--branch`), assignee = parent assignee, Scope/Links copied from the parent, one Acceptance line per comment plus `make lint test` passes; linked parent → fb; unblocked to `ready`. A clean stale worktree holding the branch is removed first; a dirty one leaves the card `blocked needs_input`.
- open feedback card exists: items are appended there as a `[ginflow-pr] new feedback:` comment.
- parent gets `[ginflow-pr] synced=<now> items=<n>` whenever items were found. Merged/closed PR: parent gets `[ginflow-pr] merged|closed` and is no longer synced.
- one `gh` failure is reported (`fail <id>: ...`), the rest continue, exit 1.

Publish on a branch with an open PR pushes, comments `[ginflow] updated <sha> by <KEY>` on the PR and `ginflow-publish: <url> (updated)` on the card; no second PR.
