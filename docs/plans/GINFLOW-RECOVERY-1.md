---
status: completed
scope: plugins/ginflow-gate/{block_routing,blocker_reporting,recovery_policy,feedback}.py + tests; docs/architecture/integration-status.md; skills/ginflow/references/trace-routing.md
owner: ginb
---

# Plan — GINFLOW-RECOVERY-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. Locate code by symbol. RED test first per step, then change, then the step's test. Each step leaves `make test` green.

Facts (Hermes `hermes_cli/kanban_db.py`): `VALID_BLOCK_KINDS = {dependency, needs_input, capability, transient}`; `BLOCK_RECURRENCE_LIMIT = 2`; same-kind re-block at the limit sets status `triage` and event `block_loop_detected`; `kanban_task_blocked` fires for both `blocked` and `triage` outcomes (and for `dependency`, inside the txn).

## Step 1: blocker_reporting on Hermes kinds

- `BLOCKER_KINDS = frozenset({"transient", "needs_input", "capability"})` (dependency never reaches recovery). `HUMAN_KINDS = {"needs_input", "capability"}`. Replace `MAX_ATTEMPTS = 3` with `BLOCK_RECURRENCE_LIMIT = 2`; drop `NON_RECOVERABLE_KINDS`.
- `build_blocker_event(..., attempt=...)` becomes `recurrences: int` (≥ 1) plus `status: str` (`blocked` | `triage`); `recovery_candidate = kind == "transient" and status == "blocked"`; `max_attempts` field becomes `limit`.
- `blocker_comment`: `[ginflow-recovery] event=<id> kind=<k> recurrences=<n>/<limit> decision=<d> owner=<o> reason=<r>`.
- Tests (`test_blocker_reporting.py`): only the 3 kinds accepted; `limit == 2`; if `hermes_cli.kanban_db` imports, `assert BLOCK_RECURRENCE_LIMIT == kanban_db.BLOCK_RECURRENCE_LIMIT` and `BLOCKER_KINDS | {"dependency"} == kanban_db.VALID_BLOCK_KINDS`.

## Step 2: recovery_policy on Hermes state

- `evaluate_recovery(event, *, current_card_id, current_workspace, current_assignee, current_status, reviewer, processed_keys)`.
- Order: malformed → `stay_blocked/malformed_safety_state`; duplicate → `skip`; card/workspace mismatch, terminal, missing/mismatched worker → existing reasons; `current_status not in {blocked, triage}` → `invalid_state`; kind in `HUMAN_KINDS` → `notify_human/<kind>`; status `triage` → `notify_human/retry_exhausted`; no `reviewer` → `notify_human/no_reviewer`; else `reassign` with `target_assignee=reviewer`.
- Rewrite `test_recovery_policy.py` cases to the table in the spec; keep every safety-check case.

## Step 3: feedback accepts recovery

- `"recovery"` is already in `WORK_MODES`; no code change. Add a `test_feedback.py` case: `work_mode="recovery", signal="retry_exhausted"` → `next_action == "notify_human"`.

## Step 4: wire the hook

`block_routing.on_task_blocked`:
1. `_load_task`; skip when no workspace, trace off, or `block_kind == "dependency"`.
2. `context_error` → warn and return (unchanged).
3. Build event: `event_id = f"{run_id}:{recurrences}"`, `card_id = task_id`, `previous_assignee = assignee or task assignee`, `status = task status`. `ValueError` → treat as `malformed_safety_state`.
4. `processed_keys` = keys parsed from existing `[ginflow-recovery] event=` comments.
5. `decision = evaluate_recovery(...)`, reviewer from `configured_reviewer`.
6. Act: `reassign` → comment `blocker_comment(event)`, `kanban assign <reviewer>`, `kanban unblock`; on any non-zero step comment `... reassign_failed`. `notify_human` (and `stay_blocked/malformed_safety_state`) → existing destination chain with `build_message`. Others → log only.
7. Emit `feedback.build_feedback_event` via the trace adapter (`@trace` on a small `_record_feedback(event)` function is enough; no new storage).
- Delete `_route_repairable` and `_REPAIR_MARKER`. No code reads `origin=worker` (checked on main 97c7ea2); `trace-routing.md` "Injected repair context" describes an unimplemented reader, so remove that section in Step 5.
- `_push(destination, message, profile)`: argv `["hermes", "-p", profile, "send", "--to", destination, "-q", message]` when `profile`, else current argv.

Tests (`test_block_routing.py`, live temp board): update STUB to log when any arg equals `send` (accept `-p <p> send`); cases from the spec acceptance list; second-transient case drives a real repeat block so Hermes sets `triage`.

## Step 5: docs + report

- `skills/ginflow/references/trace-routing.md`: replace "Repairable route", "Injected repair context" and "Credential constraint" with the policy table and reviewer-profile push.
- `docs/architecture/integration-status.md`: flip Wired for `build_blocker_event`, `blocker_comment`, `evaluate_recovery`, `build_feedback_event` to `[x] kanban_task_blocked`; update summary line.

## Step 6: verify and hand off

```bash
git grep -n "MAX_ATTEMPTS\|config_error\|persist_error\|human_input" plugins skills   # no output
make lint test; echo exit=$?                                                           # exit=0
```
Spec + plan `status: completed`; commit; `kanban_request_review` with `verification_result` + `artifact_baseline`.
