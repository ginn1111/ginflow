---
status: draft
scope: plugins/ginflow-gate/routing.py; plugins/ginflow-gate/test_ginflow_gate.py; skills/ginflow/lib/routing.py
owner: ginb
---

# Spec — CLEANUP-1.3: Routing context without legacy v1 guidance

## Problem / desired behavior

Worker agents see only the current four-phase Initiative guidance in the routing context. The legacy v1 card detector and the Work Mode / Work Size guidance formatter are removed, together with its skill table, size set, default outputs and output-override env vars. Card metadata can no longer switch routing into a legacy flow. The private route alias in core routing is removed.

## Acceptance criteria

- [ ] With no card for the workspace, routing context names Discovery → Shaping → Execution → Decision and contains no 'legacy' text
- [ ] A selected card carrying old version metadata gets the same guidance as any other card
- [ ] Tests for the legacy detector and the guidance formatter are removed; a test asserts no legacy text appears
- [ ] No code or docs reference the removed formatter or the output-override env vars
- [ ] `make lint test` passes

## Blocked by

- #3 (GitHub issue numbers)

## Constraints

- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: after review passes, reviewer `kanban_complete` auto-publishes a GitHub PR to `main` (`ginflow.publish`). Gin merges it before the next card dispatches.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/4
