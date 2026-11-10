# Block routing (trace on)

Active only when `.ginflow.yaml` has `ginflow.trace: true` (or env `GINFLOW_LOG=1`). Trace off: `kanban_block` is native, no guard, no routing. Implemented in `plugins/ginflow-gate/block_routing.py`.

## Block kinds

`kanban_block` requires `kind`. Missing or other value is rejected, naming valid kinds.

| kind | use when | route |
| --- | --- | --- |
| `needs_input` | human decision or answer needed | critical |
| `capability` | only a human can act (credentials, access, approval, manual step); never for retryable failure | critical |
| `transient` | flaky failure that may clear on retry | repairable (first), critical (repeat) |
| `dependency` | waiting on another task | native: goes to `todo`, untouched by routing |

## required_action

`needs_input` and `capability` reasons must contain a line `required_action: <what the human must do>`. Without it the guard rejects the call. `transient` and `dependency` need no such line. The pushed message uses that line as "Required action"; absent, it falls back to the reason.

## Critical route

Task stays `blocked`; never auto-resumed. One bounded, sanitized message (task ID, reason, required action, worker profile, run ID; max 800 chars) goes to the first available destination:

1. `ginflow.notify.target` (`hermes send --to` format) from `.ginflow.yaml`
2. native Kanban notify-list subscription of the task
3. card comment `[ginflow] no notify destination: ...`

If the push fails, a card comment `[ginflow] push failed: ...` is written. Invalid project config (bad `notify`) skips routing and logs a warning. All failures are swallowed; the block transition is never affected.

## Repairable route

First `transient` block per task: write card comment `[ginflow] origin=worker profile=<p> run=<id> kind=transient reason=<reason>`, assign to `gintary`, unblock. No push.

Second `transient` block on the same task (detected by existing `[ginflow] origin=worker` comment): treated as critical, full chain above, no reassign, stays `blocked`. One auto-repair per task prevents worker/`gintary` ping-pong.

## Injected repair context

When `HERMES_KANBAN_TASK` names a task with an `origin=worker` comment, `pre_llm_call` appends one line (latest such comment only):

    [ginflow origin: error came from worker; profile=<p>; run=<id>; kind=<k>; reason=<r>]

Each field is sanitized (control characters and brackets removed) and capped at 300 chars. No injection without the env var, on task mismatch, or without a comment.

## Credential constraint

`hermes send` runs under the blocked worker's own profile (inherited `HERMES_HOME`). `ginb` has Slack credentials only, so `notify.target` must be a Slack destination for `ginb` workers; other platforms fail the push and fall to the card comment.
