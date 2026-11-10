---
status: draft
scope: plugins/ginflow-gate/*.py; plugins/ginflow-trace/test_ginflow_trace_integration.py; skills/ginflow/scripts/test-ginflow-lifecycle.py
owner: ginb
---

# Spec — CLEANUP-1.2: ginflow-gate loads as one package with relative imports

## Problem / desired behavior

`ginflow-gate` loads the way Hermes loads it: one package with package-relative sibling imports. The copy-pasted file-path fallback loaders are gone. Plugin tests, the lifecycle test and the trace integration test import the plugin as a package. Routing's task normalization delegates to core card normalization. Only two loaders remain on purpose: the single core loader (resolves `skills/ginflow/lib` from the repo checkout or the installed skill) and the optional cross-plugin trace adapter.

## Acceptance criteria

- [ ] Gate, routing, publish, block routing and recovery policy contain no file-path fallback loaders
- [ ] Every test that exercised plugin modules imports them through the package
- [ ] Routing builds startup-validation cards with core card normalization; output matches the old behavior for live Hermes tasks and for fixtures without a workspace kind
- [ ] Install test still proves a copied plugin resolves core modules from the installed skill
- [ ] `make lint test` passes

## Blocked by

- #2 (GitHub issue numbers)

## Constraints

- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: after review passes, reviewer `kanban_complete` auto-publishes a GitHub PR to `main` (`ginflow.publish`). Gin merges it before the next card dispatches.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/3
