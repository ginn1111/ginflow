---
status: completed
scope: skills/ginflow/lib/decision.py; skills/ginflow/lib/project_config.py
owner: ginb
---

# Spec — CLEANUP-1.7: Remove never-called duplicate helpers

## Problem / desired behavior

Dead code that misleads readers is gone: the Decision helper that duplicates the decision-context logic, and the unused config-mismatch helper. Both have zero callers, zero tests and no doc mention. Unwired but planned modules stay.

## Acceptance criteria

- [ ] Neither helper exists or is exported
- [ ] Decision readiness/notification and config validation tests are unchanged and pass
- [ ] `make lint test` passes

## Blocked by

- #6 (GitHub issue numbers)

## Constraints

- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: after review passes, reviewer `kanban_complete` auto-publishes a GitHub PR to `main` (`ginflow.publish`). Gin merges it before the next card dispatches.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/8
