---
status: completed
card: PRFB-2
assignee: ginb
blocked_by: [PRFB-1]
scope: skills/ginflow/scripts/ginflow.py (pr sync merged path, init cron step) + tests, skills/ginflow/references, integration-status.md
owner: ginb
---

# Spec — PRFB-2: merged PRs tidy stacks; sync runs on a schedule

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

When Gin merges a parent PR, stacked child PRs keep the parent branch as base. GitHub retargets them only when the base branch is deleted on merge, and `delete_branch_on_merge` is `false` on `ginn1111/ginflow` (enabling it needs repo admin; the token has push only). Local `main` also goes stale after merges, which breaks new root cards' base. And `pr sync` only runs when someone remembers.

## Desired behavior

`ginflow pr sync` merged path, for a candidate card whose PR state is `MERGED`:

- comment `[ginflow-pr] merged <merge sha>` on the card (stops future syncing);
- for each child card whose open PR has base = this PR's head branch: `gh pr edit <child-url> --base <target>`; skip when GitHub already retargeted;
- once per run after any merge: in the board `default_workdir` checkout, `git fetch`; if on the target branch, clean, and fast-forwardable → `git merge --ff-only origin/<target>`; otherwise print `warn main: <reason>`.

`ginflow init` gains step `sync`: ensure one Hermes cron job named `ginflow-pr-sync:<board>` running `ginflow pr sync --board <board>` every 10 minutes as a no-agent script, delivered to `ginflow.notify.target` when set (else `origin`/home channel), output only when something happened. Exists with same command: ok; differs: fail (never silently replace).

## Constraints

- Never force-push, rebase, or delete remote branches. Never touch a dirty checkout.
- Cron script must live where Hermes accepts it (`~/.hermes/scripts/`); confirm `hermes cron create --script/--no-agent` semantics and empty-output delivery before coding.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: reviewer `kanban_complete` auto-publishes a GitHub PR to `main`. Gin merges.
- Canonical verification: `make lint test`.
- Before review: set this spec and the linked plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both linked docs).
- Parent design: GitHub issue `GINFLOW-SPEC-FIRST` (see Links on the card). Decisions there are settled; do not re-open them.

## Acceptance criteria

- [ ] Stub `gh` reports parent PR merged and child PR base `wt/<parent>`: sync logs `gh pr edit <child> --base main`, parent card gets `merged` marker, later runs skip it
- [ ] Temp repo with local `main` 1 behind `origin/main`, clean: sync fast-forwards it; dirty: `warn main`, no change
- [ ] `ginflow init` twice on a temp `HERMES_HOME`: exactly one `ginflow-pr-sync:<board>` cron job
- [ ] Sync with nothing to do prints nothing (no cron delivery)
- [ ] Docs + `integration-status.md` updated
- [ ] `make lint test` passes

## Edge cases

- Child PR already merged or closed: skip.
- Default workdir checkout on another branch: `warn main: on <branch>`.

## Blocked by

- PRFB-1
