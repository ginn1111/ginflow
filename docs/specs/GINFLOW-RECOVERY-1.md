---
status: draft
scope: plugins/ginflow-gate/{block_routing,blocker_reporting,recovery_policy,feedback}.py + tests; docs/architecture/integration-status.md; skills/ginflow/references/trace-routing.md
owner: ginb
---

# Spec — GINFLOW-RECOVERY-1: wire block recovery and notify into the block hook

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

`docs/architecture/integration-status.md` marks `blocker_reporting`, `recovery_policy` and `feedback` as not wired. They model block recovery with their own kinds (`transient`, `unknown`, `config_error`, `persist_error`, `human_input`) and `MAX_ATTEMPTS = 3`. Hermes uses `VALID_BLOCK_KINDS = {dependency, needs_input, capability, transient}` and routes a card to `triage` (`block_loop_detected`) at `BLOCK_RECURRENCE_LIMIT = 2`. Three attempts can never happen. Meanwhile the live `kanban_task_blocked` hook in `block_routing.py` has its own ad-hoc rules, no safety checks, no alert when a card lands in `triage`, and pushes alerts as the blocked worker's profile, which fails when that profile has no gateway credentials (`ginb`).

Vision link: `docs/plans/2026-11-10-gin-v1-vision.md` — "Kanban complete/fail/recovery and report via the gateway".

## Desired behavior

One policy, Hermes kinds, decided by `recovery_policy.evaluate_recovery` inside the existing `kanban_task_blocked` hook (trace on only):

| Hermes kind | first block (`block_recurrences` = 1, status `blocked`) | repeat (status `triage`, `block_loop_detected`) |
| --- | --- | --- |
| `transient` | `reassign`: recovery comment, assign `ginflow.reviewer.profile`, unblock; no push | `notify_human` (`retry_exhausted`) |
| `needs_input`, `capability` | `notify_human` | `notify_human` |
| `dependency` | ignored (Hermes waits in `todo`) | n/a |

- No reviewer configured: `transient` becomes `notify_human`.
- Safety checks from `evaluate_recovery` stay: duplicate event (`skip`), card/workspace/assignee mismatch, terminal card, malformed event (`stay_blocked`). `stay_blocked` with `malformed_safety_state` also notifies a human; other `stay_blocked`/`skip` only log.
- `notify_human` destination chain unchanged: `ginflow.notify.target`, then the card's notify subscription, then a card comment. Push runs as the reviewer profile (`hermes -p <reviewer> send ...`) when one is configured; else the current profile.
- Every decision is recorded as a `feedback.build_feedback_event` (`work_mode=recovery`; signal `blocked` / `recovered` / `retry_exhausted`) through the ginflow-trace adapter. Nothing new is persisted outside trace.
- Retry count comes from Hermes (`block_recurrences` and status), not a plugin counter. `MAX_ATTEMPTS` is removed.

## Inputs / outputs

- Input: Hermes `kanban_task_blocked` kwargs (`task_id`, `board`, `assignee`, `run_id`, `reason`) plus `hermes kanban show --json` (status, `block_kind` from latest block event, `block_recurrences`, comments, `workspace_path`).
- Output: at most one of {reassign + unblock, one push, one card comment}; one trace feedback record.

## Constraints

- Hook stays observer-only: any exception is caught and logged; the Hermes block/triage transition is never affected.
- `blocker_reporting.BLOCK_RECURRENCE_LIMIT` mirrors Hermes; a test pins it to `hermes_cli.kanban_db.BLOCK_RECURRENCE_LIMIT` when the hermes package is importable, else skips that assert.
- Keep the existing `guard_block` (`pre_tool_call`) behavior: `kind` required, `required_action:` line for `needs_input`/`capability`.
- No new config keys. No new modules. No `decision.build_notification` (Initiative keys; out of scope).
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: reviewer `kanban_complete` auto-publishes a GitHub PR to `main`. Gin merges.
- Canonical verification: `make lint test`.
- Before review: set this spec and the linked plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both linked docs).

## Acceptance criteria

- [ ] `blocker_reporting` accepts exactly Hermes' 4 kinds; `MAX_ATTEMPTS` and the 5-kind set are gone (`git grep -n "MAX_ATTEMPTS\|config_error\|persist_error\|human_input" plugins skills` → no output)
- [ ] `evaluate_recovery` returns `reassign` (to reviewer) for a first `transient` block, `notify_human`/`retry_exhausted` for a card in `triage`, `notify_human` for `needs_input`/`capability`, and keeps every existing safety-check outcome
- [ ] Live hook test: first `transient` block assigns the reviewer, unblocks, writes a `[ginflow-recovery]` comment, sends nothing
- [ ] Live hook test: second `transient` block (Hermes routes to `triage`) produces exactly one send, run as the reviewer profile (`-p <reviewer>` in the stub log)
- [ ] Existing block-routing cases still pass (trace off, invalid `notify.target`, subscription fallback, comment fallback, `needs_input` stays `blocked`)
- [ ] A `work_mode=recovery` feedback event maps `retry_exhausted` to `notify_human` (test); the hook emits one feedback record per handled block
- [ ] `integration-status.md` marks `build_blocker_event`, `blocker_comment`, `evaluate_recovery`, `build_feedback_event` wired (`kanban_task_blocked`); `trace-routing.md` documents the policy table and reviewer-profile push
- [ ] `make lint test` passes

## Edge cases

- Hook fires twice for the same block event: second call `skip` (idempotency key = `<task>:<run>:<recurrences>`).
- Assign succeeds, unblock fails: card stays blocked under the reviewer; comment `[ginflow-recovery] ... reassign_failed`.
- Card moved/completed between block and hook: `terminal_card` / `invalid_state`, no action.
- `block_kind` missing from `show --json`: read from latest `blocked`/`block_loop_detected` event payload (existing `_load_task` logic); still missing = `malformed_safety_state`, notify human.
- Reviewer profile equals blocked worker: still reassign once (re-entry gets repair context); repeat goes to `triage` anyway.

## Blocked by

- #10 (CLEANUP-1.9, PR #19: adds `integration-status.md`)
