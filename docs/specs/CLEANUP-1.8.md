---
status: draft
scope: GLOSSARY.md, docs/adrs/0001-artifact-first-execution-packages.md, skills/ginflow/SKILL.md; docs/architecture/; docs/specs/GINFLOW-MR-2.md, docs/plans/GINFLOW-MR-2.md
owner: ginb
---

# Spec — CLEANUP-1.8: Architecture docs and Draw.io match the code

## Problem / desired behavior

Readers see the real system. 'v2'/'versioned' qualifiers are gone from the glossary, ADR 0001, the ginflow skill and the flow doc. The flow doc gains a Hermes hook → handler table. The reference doc's ginflow-gate row lists the real hooks and stops claiming active feedback/recovery helpers, and it gains rows for ginflow-trace and the core loader. On the Draw.io 'Harness system overview' page: block routing, auto-publish and the single core home are shown; observability is shown as provided by opt-in ginflow-trace; unwired modules are marked. Stale `core/ginflow-core` paths in the draft MR-2 spec/plan point at `skills/ginflow/lib`. Completed MR-1 artifacts are untouched.

## Acceptance criteria

- [ ] No Execution Package 'v2' wording remains in the glossary, ADR, skill or architecture docs
- [ ] The flow doc lists every registered hook and its handler, matching plugin registration
- [ ] The Draw.io file parses as XML with unique cell ids per page, and shows block routing, auto-publish, core home, trace and unwired modules
- [ ] The draft MR-2 spec/plan reference only existing paths; completed MR-1 files are unchanged
- [ ] `make lint test` passes

## Blocked by

- #4
- #5
- #6
- #7 (GitHub issue numbers)

## Constraints

- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: after review passes, reviewer `kanban_complete` auto-publishes a GitHub PR to `main` (`ginflow.publish`). Gin merges it before the next card dispatches.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/9
