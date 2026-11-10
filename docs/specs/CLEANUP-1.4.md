---
status: draft
scope: skills/ginflow/lib/execution_package.py, card_creation.py, execution_batch.py, provider_document.py and their tests; plugins/ginflow-gate/gate.py (comment only)
owner: ginb
---

# Spec — CLEANUP-1.4: Versionless Execution Package and provider document

## Problem / desired behavior

Shaping produces Execution Packages with no version field, and validation and card creation no longer check one. Every Work Unit must reference exactly one provider document; validation names the Work Unit that lacks one. Work Unit cards link only their provider document, and the Integration card keeps the package contract/spec links. Provider documents are rendered with no schema tag (frontmatter holds only provider and Work Unit identity).

## Acceptance criteria

- [ ] A shaped package has no version field; an approved package passes validation and card creation without one
- [ ] A package whose Work Unit lacks a document is invalid, with an error naming that unit
- [ ] Execution Batch creation still produces blocked unit and integration cards carrying lineage metadata and document links
- [ ] Local provider document frontmatter and metadata carry no schema tag; the completion gate still accepts a matching document baseline
- [ ] No 'v2'/'legacy' wording remains in these core modules
- [ ] `make lint test` passes

## Blocked by

- #2 (GitHub issue numbers)

## Constraints

- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: after review passes, reviewer `kanban_complete` auto-publishes a GitHub PR to `main` (`ginflow.publish`). Gin merges it before the next card dispatches.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/5
