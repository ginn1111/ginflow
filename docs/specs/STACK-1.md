---
status: completed
card: STACK-1
assignee: ginb
blocked_by: [PRUNE-1]
scope: plugins/ginflow-gate (new kanban_task_completed hook, publish base selection) + tests, skills/ginflow/lib/publish.py, skills/ginflow/references/trace-routing.md or kanban-guide.md, integration-status.md
owner: ginb
---

# Spec — STACK-1: a child card stacks on its parent's branch

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

Hermes promotes a child card as soon as its parents are `done`, i.e. reviewer-approved, but the parent's code is only on `wt/<parent>` until Gin merges its PR. Hermes cuts a missing worktree branch from `HEAD` of the board's `default_workdir` checkout, so the child starts without the parent's code. Today the orchestrator holds children blocked until merge. Gin chose stacking (brainstorming Q3 = B) with the child PR based on the parent branch (Q4 = A).

## Desired behavior

New `kanban_task_completed` hook in `ginflow-gate` (trace not required; runs when the completed card's workspace is a worktree under a repo with `.ginflow.yaml`):

- For each child of the completed card whose workspace kind is `worktree` and whose parents are now all `done`, and whose branch (`branch_name` or `wt/<child-id>`) does not exist yet:
  - one worktree parent: create the child worktree `<repo>/.worktrees/<child-id>` on a new branch from the parent's branch head;
  - several: from the first parent's branch (parent link order), then `git merge --no-ff` each other parent branch; on conflict `git merge --abort`, leave the worktree, comment `[ginflow-stack] conflict <branches>` and block the child `needs_input` with `required_action: resolve merge of <branches>`.
  - comment `[ginflow-stack] base=<parent branch(es)> head=<sha>` on the child.
- Hermes then reuses that worktree (`_ensure_git_worktree` returns early for an existing worktree of the same repo).
- Publish: for a card with exactly one worktree parent whose PR (parent's `ginflow-publish: <url>` comment) is still open, `gh pr create --base <parent branch>`; several parents or parent PR merged/absent: base = configured target, and the body lists open parent PRs as `Merge after: <urls>`.

## Constraints

- Observer-only: exceptions are caught and logged; the completion transition is never affected.
- Never touches a child that is already `running`/`done`/`archived`; if its branch exists but lacks a parent head, comment `[ginflow-stack] stale-base` and notify via the existing block-routing destination chain.
- Hook signature: confirm the `kanban_task_completed` kwargs in Hermes `hermes_cli/kanban_db.py` (`_fire_task_hook("kanban_task_completed", ...)`) before coding.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: reviewer `kanban_complete` auto-publishes a GitHub PR to `main`. Gin merges.
- Canonical verification: `make lint test`.
- Before review: set this spec and the linked plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both linked docs).
- Parent design: GitHub issue `GINFLOW-SPEC-FIRST` (see Links on the card). Decisions there are settled; do not re-open them.

## Acceptance criteria

- [ ] Live temp board + temp repo/bare origin: parent A (worktree, commit on `wt/A`) linked to child B; after `hermes kanban complete A` and the hook, `wt/B` exists at `wt/A` head and `.worktrees/B` is a worktree on it; B has the `[ginflow-stack] base=` comment
- [ ] Two parents with non-conflicting commits: `wt/C` contains both heads; conflicting commits: C `blocked`, kind `needs_input`, conflict comment, no partial merge left (`git status` clean after abort)
- [ ] Child already `running`: no git change; `stale-base` comment when its branch lacks the parent head
- [ ] Publish with one open parent PR: stub log shows `gh pr create ... -B wt/A`; with two parents: `-B main` and body contains `Merge after:`
- [ ] `integration-status.md` lists the hook wired; docs describe stacking
- [ ] `make lint test` passes

## Edge cases

- Parent card has no `branch_name` (dir workspace): skip stacking for that child.
- Hook fires once per parent completion; only the completion that makes all parents `done` acts.
- Dispatcher claims the child before the hook runs: covered by the `running` rule.

## Blocked by

- PRUNE-1
