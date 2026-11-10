---
status: draft
card: STACK-1
scope: see spec
owner: ginb
---

# Plan — STACK-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: confirm hook contract
- Read Hermes `_fire_task_hook` and the `kanban_task_completed` call; record kwargs in the plugin docstring.

## Step 2: branch stacking
- New `plugins/ginflow-gate/stacking.py` + `test_stacking.py` (live temp board like `test_block_routing.py`): single parent, two parents, conflict, running child.
- Register `kanban_task_completed` in the plugin `register`.

## Step 3: publish base
- `test_publish_hook.py`: one open parent PR → `-B wt/<parent>`; two parents → target + `Merge after:` body.
- `publish.prepare`: resolve parents via `hermes kanban show --json` (`parents`), parent PR URL from comments, PR state via `gh pr view --json state`.
- Add the test file to Makefile `plugin-test`.

## Step 4: docs + verify
- Describe stacking in `references/kanban-guide.md`; update `integration-status.md`.
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
