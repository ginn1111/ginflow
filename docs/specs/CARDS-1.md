---
status: completed
card: CARDS-1
assignee: ginb
blocked_by: [INIT-1]
scope: skills/ginflow/scripts/ginflow.py (cards subcommand) + test, skills/ginflow/lib (front matter + card body helpers), skills/ginflow/templates/spec.md, skills/ginflow/references/kanban-guide.md, SKILL.md card section, integration-status.md
owner: ginb
---

# Spec — CARDS-1: `ginflow cards create` builds cards from spec front matter

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

Cards are created by hand: body labels typed from the spec, dependencies written as "Blocked by" prose, merge gates held in the orchestrator's head, workspace path easy to forget. Gin chose spec front matter as the single source (brainstorming Q2 = A) and Hermes `link` edges for dependencies.

## Desired behavior

Spec front matter (existing `status`/`scope`/`owner` kept):

```yaml
card: GINFLOW-PRFB-1          # stable key, [A-Z][A-Z0-9]*(-[A-Z0-9]+)*-\d+
assignee: ginb                # installed profile
blocked_by: [GINFLOW-CARDS-1] # card keys; optional, default []
```

`ginflow cards create [--board B] SPEC...`:

1. Preflight (nothing created on any failure, exit 1, one line per problem): board resolves and has `default_workdir`; local target branch not behind `origin`; each spec has valid `card`, installed `assignee`, a matching `docs/plans/<KEY>.md`, `## Problem` and `## Acceptance criteria` sections; every `blocked_by` key is in the given set or already a card on the board; no cycle.
2. Create, in dependency order, one card per spec not already on the board: title `<KEY> — <spec H1 after "Spec — <KEY>: ">`, body with labels `Objective:` (first sentence of `## Desired behavior`, else first sentence of `## Problem`), `Scope:` (front matter `scope`), `Acceptance:` (checklist items of `## Acceptance criteria`), `Links:` (spec + plan); `--assignee`, `--workspace worktree`, `--initial-status blocked`.
3. `hermes kanban link <parent> <child>` for each `blocked_by` edge (skip existing edges).
4. Run the harness candidate check per new card; unblock passing cards (Hermes lands children in `todo` until parents are `done`). Failing cards stay blocked with a comment naming the failed check.
5. Print JSON `[{key, id, status, parents, created}]`.

A card already on the board is matched by title prefix `<KEY> — ` (non-archived) and reused, never duplicated.

## Constraints

- Uses only `hermes kanban` CLI (no DB access). Reuses `harness_core` card parsing for the body round-trip check.
- `templates/spec.md` gains the three keys; `kanban-guide.md` and `SKILL.md` "Create card" steps point to the command.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: reviewer `kanban_complete` auto-publishes a GitHub PR to `main`. Gin merges.
- Canonical verification: `make lint test`.
- Before review: set this spec and the linked plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both linked docs).
- Parent design: GitHub issue `GINFLOW-SPEC-FIRST` (see Links on the card). Decisions there are settled; do not re-open them.

## Acceptance criteria

- [ ] Temp board, specs A, B(`blocked_by: [A]`), C(`blocked_by: [A, B]`): one run creates 3 cards, edges A→B, A→C, B→C; A `ready`, B and C `todo`; each body parses with `harness_core.parse_card_body` and has all 4 labels
- [ ] Second run: `created: false` for all, no new cards or edges
- [ ] Cycle A↔B, unknown key, missing plan, or uninstalled assignee: exit 1, board unchanged
- [ ] Board without `default_workdir`: exit 1 before any create
- [ ] `blocked_by` naming an existing board card links to it
- [ ] Docs updated; `integration-status.md` lists the new functions wired
- [ ] `make lint test` passes

## Edge cases

- Spec without front matter `card`: preflight error naming the file.
- Partial failure mid-create (Hermes error): stop, print created cards so far, exit 1; rerun resumes via title matching.
- Harness check unavailable: cards stay blocked, comment `harness unavailable`.

## Blocked by

- INIT-1 (adds the `ginflow` command and `default_workdir` setup)
