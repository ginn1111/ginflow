---
status: completed
card: GATEID-1
scope: see spec
owner: ginb
---

# Plan — GATEID-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first; commit per step.

## Step 1: failing tests (B1–B4)
- In `plugins/ginflow-gate/test_ginflow_gate.py`, stub `load_card` (and validation) to record the id it receives. Cases: env card + UUID kwarg, explicit args id, kwarg only, empty → `requires task_id`; cover `kanban_request_review` and `kanban_complete`. Restore `HERMES_KANBAN_TASK` after each case.
- Same inputs through `post_tool_call` (stub `_publish.finish`) and `block_routing.guard_block` (stub `_load_task`).
- Verify RED: `python3 plugins/ginflow-gate/test_ginflow_gate.py`.

## Step 2: shared helper (B1, B2)
- Add `selected_task_id(args, task_id)` to an existing gate module both files already import (or a small new module in the plugin) and use it at `gate.py:144`, `gate.py:175`, `block_routing.py:109`.
- Verify GREEN: same command.

## Step 3: verify and hand off
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review` with verification and `artifact_baseline`.
