---
status: draft
card: PRFB-2
scope: see spec
owner: ginb
---

# Plan — PRFB-2

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: merged path
- Extend `test-ginflow-pr-sync.py`: merged fixture, child PR base fixture; assert `gh pr edit` call and marker.
- Implement merged marker + child retarget.

## Step 2: main fast-forward
- Test with temp repo + bare origin: behind+clean → ff; dirty → warn.
- Implement in sync (once per run, only after a merge was seen).

## Step 3: cron step in init
- Confirm `hermes cron create` flags (`--script`, `--no-agent`, `--deliver`, `--name`) and empty-output behavior; record in plan notes.
- Install a small wrapper script under `~/.hermes/scripts/`; `ginflow init` step `sync` ensures the job; test idempotence on temp `HERMES_HOME`.

## Step 4: docs + verify
- Docs + `integration-status.md`.
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
