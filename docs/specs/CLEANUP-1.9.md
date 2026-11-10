---
status: completed
scope: docs/architecture/integration-status.md, docs/architecture/README.md; Makefile
owner: ginb
---

# Spec — CLEANUP-1.9: Integration-status report

## Problem / desired behavior

Gin can see at a glance which plugin/core features are wired into the workflow. A new architecture doc has per-module tables for ginflow-gate, ginflow-trace and core lib, each row with Wired / Doc / Tested checkboxes. Wired means reached from a Hermes hook or the harness CLI; Doc means named in the ginflow skill or its references; Tested means covered by `make test`. Wired rows name their hook. The report has a regenerate-evidence recipe and a summary of unwired chains, and it is linked from the architecture README. The orphaned feedback-event test joins `make test` (or is recorded as an open item if it fails).

## Acceptance criteria

- [ ] Report covers every non-test module in ginflow-gate, ginflow-trace and core lib
- [ ] Every public function appears with three checkboxes that match a grep of callers and tests
- [ ] The unwired Initiative chain, provider document builder, blocker/recovery/feedback helpers, worker defaults, documents config and reviewer seeding are marked not wired
- [ ] Functions with no caller and no test are listed in the summary
- [ ] Every plugin test file runs under `make test`
- [ ] `make lint test` passes

## Blocked by

- #8
- #9 (GitHub issue numbers)

## Constraints

- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: after review passes, reviewer `kanban_complete` auto-publishes a GitHub PR to `main` (`ginflow.publish`). Gin merges it before the next card dispatches.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/10
