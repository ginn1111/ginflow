---
status: completed
card: GATEID-1
assignee: ginb
blocked_by: []
scope: plugins/ginflow-gate/gate.py, plugins/ginflow-gate/block_routing.py, plugins/ginflow-gate/test_ginflow_gate.py
owner: ginb
---

# Spec — GATEID-1: Gate picks the worker's card without an explicit task_id

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

`ginflow-gate` picks the card for `kanban_request_review` / `kanban_complete` as `args.task_id or task_id or HERMES_KANBAN_TASK` (`plugins/ginflow-gate/gate.py:144`, `:175`; `block_routing.py:109`). Hermes passes its own per-call `task_id` kwarg to every `pre_tool_call` / `post_tool_call` hook (`agent/inline_tool_executors.py: tool_hook_ids`). That value is an agent task UUID, not a Kanban card id. A dispatched worker that omits `task_id` (allowed: Kanban tools default to `HERMES_KANBAN_TASK`) therefore has the gate look up the UUID and fail closed:

```
ginflow-gate: validation failed closed: Unable to read Kanban card dff0611b-409e-4361-ac85-2cfc3b658472: no such task
```

Seen on CLOUD-1.1, 1.3 and 1.4 (`t_adbe11e3`, `t_8702ba56`, `t_6f3b8127`) at both review request and completion; passing `task_id` explicitly worked every time.

## Desired behavior

- B1. One helper in `plugins/ginflow-gate/` selects the card id: first non-empty of `args["task_id"]`, `os.environ["HERMES_KANBAN_TASK"]`, hook kwarg `task_id`; stripped string; `""` when none.
- B2. `gate.pre_tool_call`, `gate.post_tool_call` and `block_routing.guard_block` use that helper; no other selection logic remains.
- B3. Explicit `args.task_id` always wins. With no args id and no env, the hook kwarg is still used (behavior kept for non-worker callers).
- B4. Empty result keeps today's error: `<tool> requires task_id`.

## Constraints

- No change to Hermes; ginflow-gate only.
- Do not change `routing.py` (it already reads only `HERMES_KANBAN_TASK`).

## Acceptance criteria

- [ ] Env card + no args id + UUID kwarg → `pre_tool_call` loads the env card for `kanban_request_review` and `kanban_complete`
- [ ] Explicit `args.task_id` beats env and kwarg
- [ ] No args id, no env → kwarg used
- [ ] `post_tool_call` and `guard_block` select the same id as `pre_tool_call` for the same inputs
- [ ] `make lint test` passes

## Edge cases

- Whitespace-only values count as empty.
- `args` may be `None` in `post_tool_call`.
