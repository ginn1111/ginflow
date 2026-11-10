---
status: draft
card: PRFB-1
assignee: ginb
blocked_by: [INIT-1, STACK-1]
scope: skills/ginflow/scripts/ginflow.py (pr sync) + test, plugins/ginflow-gate/publish.py (update existing PR), skills/ginflow/references, integration-status.md
owner: ginb
---

# Spec — PRFB-1: PR review comments start a follow-up card on the same branch

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

After auto-publish, Gin's PR comments go nowhere: Hermes has no PR event hook, a `done` card cannot be reopened (`reopen-review` only from `review`), so feedback means a manual new card. Gin chose follow-up cards on the same branch (Q5 = A) that run without asking (Q6 = A).

## Desired behavior

`ginflow pr sync [--board B]`:

- Candidates: `done` cards with a `ginflow-publish: <url>` comment and no `[ginflow-pr] merged` comment.
- For each, read the PR (`gh pr view <url> --json state,headRefName,reviews,comments` and inline review comments via `gh api .../pulls/<n>/comments`). New items = review bodies, `CHANGES_REQUESTED` reviews, issue comments, inline comments created after the card's latest `[ginflow-pr] synced=<iso>` comment (default: card `completed_at`), excluding comments whose body starts with `[ginflow]`.
- New items and no open feedback card for this PR: create `<KEY>-fb<N> — PR #<n> feedback` (N = 1 + existing fb cards), assignee = parent assignee, `--workspace worktree`, `--branch <PR head branch>`, `--initial-status blocked`; body `Objective:` address PR review feedback, `Scope:` parent card's Scope, `Acceptance:` one line per comment (author, file:line, text, truncated 300 chars) + `make lint test` passes, `Links:` parent card links. `link <parent> <fb>`; harness check; unblock.
- New items and an open feedback card exists: append them as one comment on that card instead.
- Always end with `[ginflow-pr] synced=<now iso> items=<n>` on the parent card when items were found.
- Before creating a feedback card, if the PR head branch is still checked out in a clean stale worktree, `git worktree remove` it; dirty → create the card blocked `needs_input` with the reason.

Publish: when the branch already has an open PR, push, post PR comment `[ginflow] updated <sha> by <KEY>` and card comment `ginflow-publish: <url> (updated)`; never create a second PR.

## Constraints

- `gh` only for GitHub (GitLab `glab` path: print `skip <url>: provider gitlab not supported yet`).
- The PR author and Gin share one GitHub account, so ginflow's own PR comments must carry the `[ginflow]` prefix; that prefix is the only author filter.
- No new storage: markers live in card comments.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: reviewer `kanban_complete` auto-publishes a GitHub PR to `main`. Gin merges.
- Canonical verification: `make lint test`.
- Before review: set this spec and the linked plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both linked docs).
- Parent design: GitHub issue `GINFLOW-SPEC-FIRST` (see Links on the card). Decisions there are settled; do not re-open them.

## Acceptance criteria

- [ ] Temp board, parent card `done` with publish comment, stub `gh` returning one review + one inline comment: sync creates one fb card with `branch_name` = PR head, both comments in Acceptance, edge parent→fb, status `ready`; parent gets `synced=` marker
- [ ] Rerun with no new stub items: no new card, no new marker
- [ ] New comment while fb card open: comment appended to fb card, no second card
- [ ] `[ginflow] updated ...` comments are ignored
- [ ] Publish on a branch with an open PR: stub log has push + `gh pr comment`, no `gh pr create`
- [ ] Docs + `integration-status.md` updated
- [ ] `make lint test` passes

## Edge cases

- PR closed without merge: comment `[ginflow-pr] closed` and stop syncing it.
- `gh` failure for one PR: report it, continue with the rest, exit 1 at the end.
- Feedback on a feedback card's PR: same PR, so items go to the open fb card or a new `fb<N+1>`.

## Blocked by

- INIT-1 (`ginflow` command)
- STACK-1 (both change publish; branch reuse)
