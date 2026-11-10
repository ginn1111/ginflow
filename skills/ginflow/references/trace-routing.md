# Block routing (trace on)

Active only when `.ginflow.yaml` has `ginflow.trace: true` (or env `GINFLOW_LOG=1`). Trace off: `kanban_block` is native, no guard, no routing. Implemented in `plugins/ginflow-gate/block_routing.py`; decisions come from `recovery_policy.evaluate_recovery`.

## Block kinds

`kanban_block` requires `kind`, one of the Hermes kinds. Missing or other value is rejected, naming valid kinds.

| kind | use when |
| --- | --- |
| `needs_input` | human decision or answer needed |
| `capability` | only a human can act (credentials, access, approval, manual step); never for retryable failure |
| `transient` | flaky failure that may clear on retry |
| `dependency` | waiting on another task; native: goes to `todo`, untouched by routing |

## required_action

`needs_input` and `capability` reasons must contain a line `required_action: <what the human must do>`. Without it the guard rejects the call. `transient` and `dependency` need no such line. The pushed message uses that line as "Required action"; absent, it falls back to the reason.

## Recovery policy

Retry count comes from Hermes, not a plugin counter: the same kind blocked twice (`BLOCK_RECURRENCE_LIMIT = 2`) sends the card to `triage` (`block_loop_detected`). The hook fires for both `blocked` and `triage`.

| kind | first block (`blocked`) | repeat (`triage`) |
| --- | --- | --- |
| `transient` | `reassign`: comment, assign `ginflow.reviewer.profile`, unblock; no push | `notify_human` (`retry_exhausted`) |
| `needs_input`, `capability` | `notify_human`; card stays `blocked` | `notify_human` |
| `dependency` | ignored | n/a |

- No reviewer configured: `transient` becomes `notify_human` (`no_reviewer`).
- Safety checks stay: duplicate event (`skip`), card/workspace/assignee mismatch, terminal card, malformed event (`stay_blocked`; `malformed_safety_state` also notifies a human).
- Recovery comment: `[ginflow-recovery] event=<run>:<n> kind=<k> recurrences=<n>/2 decision=<d> owner=worker reason=<r>`. Raw reason text is never included. Assign succeeds but unblock fails: comment ends `reason=reassign_failed`, card stays blocked.
- Each handled block emits one `work_mode=recovery` feedback event (`blocked`, `recovered`, `retry_exhausted`) through the trace adapter.

## Notify route

One bounded, sanitized message (task ID, reason, required action, worker profile, run ID; max 800 chars) goes to the first available destination:

1. `ginflow.notify.target` (`hermes send --to` format) from `.ginflow.yaml`
2. native Kanban notify-list subscription of the task
3. card comment `[ginflow] no notify destination: ...`

If the push fails, a card comment `[ginflow] push failed: ...` is written. Invalid project config (bad `notify`) skips routing and logs a warning. All failures are swallowed; the block transition is never affected.

## Reviewer-profile push

When `ginflow.reviewer.profile` is set, the push runs as that profile (`hermes -p <reviewer> send ...`), so a worker profile without gateway credentials (`ginb`) still alerts. Without a reviewer, it runs as the current profile.
