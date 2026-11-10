---
status: draft
card: PRFB-1
scope: see spec
owner: ginb
---

# Plan — PRFB-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: publish updates an existing PR
- `test_publish_hook.py`: existing PR → push + `gh pr comment <url> --body "[ginflow] updated ..."`, no create; card comment `(updated)`.
- `publish.publish`: existing-URL branch posts the comment.

## Step 2: read PR feedback
- New `skills/ginflow/scripts/test-ginflow-pr-sync.py`: stub `gh` serving JSON fixtures per subcommand from a temp dir; temp board with a `done` parent card carrying a publish comment.
- `ginflow pr sync`: candidate selection, marker parsing, item filtering.

## Step 3: feedback cards
- Create/append/link/unblock; stale worktree removal; marker comment.
- Tests from the spec acceptance list.

## Step 4: docs + verify
- `references/kanban-guide.md` "PR feedback" section; `integration-status.md`.
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
