---
status: completed
scope: scripts/install.sh; scripts/test-install.sh
owner: ginb
---

# Spec — CLEANUP-1.6: Versionless install manifest

## Problem / desired behavior

The install manifest records only source root, skill and plugins. Uninstall no longer reads the old per-profile manifest layout. Install, reinstall and uninstall behave as before.

## Acceptance criteria

- [ ] After install the manifest keys are exactly `source_root`, `skill`, `plugins`
- [ ] Uninstall removes everything the manifest lists and restores backups
- [ ] Reinstall stays idempotent
- [ ] The install test asserts the manifest keys
- [ ] `make lint test` passes

## Blocked by

- #2 (GitHub issue numbers)

## Constraints

- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: after review passes, reviewer `kanban_complete` auto-publishes a GitHub PR to `main` (`ginflow.publish`). Gin merges it before the next card dispatches.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/7
