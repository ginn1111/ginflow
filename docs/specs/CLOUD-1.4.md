---
status: draft
card: CLOUD-1.4
assignee: ginb
blocked_by: []
issue: ginn1111/ginflow#53
supersedes: CARDS-1 (draft, issue #26)
scope: skills/ginflow/lib/spec_cards.py (new), skills/ginflow/scripts/ginflow.py (cards create subcommand), skills/ginflow/scripts/test-ginflow-cards.py (new), Makefile (lifecycle-test entry), skills/ginflow/templates/spec.md, skills/ginflow/references/kanban-guide.md, skills/ginflow/SKILL.md (card section), docs/architecture/integration-status.md
owner: ginb
---

# Spec — CLOUD-1.4: Create cards from spec front matter

Content rules: `references/artifact-content-guide.md` in `ginflow`. Parent: issue #49 (CLOUD-1); design `docs/plans/2026-11-19-cloud-agents-design.md`; terms `GLOSSARY.md` (Issue key, Card key). Absorbs the unimplemented CARDS-1 draft (`docs/specs/CARDS-1.md`, issue #26) and extends it with Issue links, idempotency keys, and dotted Card keys.

## Problem

Cards are created by hand: body labels copied from the spec, dependencies written as prose, links easy to forget. Issue-driven shaping (CLOUD-1.7) needs a deterministic command that turns the spec/plan pairs it writes into linked, ready cards, and that a redelivered webhook can rerun without duplicates.

## Desired behavior

Spec front matter (existing `status`/`scope`/`owner` kept):

```yaml
card: CLOUD-1.4          # Card key
assignee: ginb           # installed Hermes profile
blocked_by: [CLOUD-1.1]  # Card keys; optional, default []
issue: owner/repo#53     # optional; the Issue this card came from
```

- B1. Card key grammar: `[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-\d+(\.\d+)*` (`PRFB-1`, `SHOP-42.1`, `CLOUD-1.4`).
- B2. `ginflow cards create [--board B] [--project P] SPEC...` preflight; on any failure nothing is created, exit 1, one `fail <file>: <reason>` line per problem:
  - board resolves (explicit, env, `.ginflow.yaml`) and has `default_workdir`;
  - each spec has a valid `card`, an installed `assignee`, a matching `docs/plans/<KEY>.md`, `## Problem` and `## Acceptance criteria` sections, and is committed (no uncommitted changes to spec or plan);
  - `issue`, when present, matches `owner/repo#n`;
  - every `blocked_by` key is in the given set or already a non-archived card on the board; no cycle.
- B3. Create, in dependency order, one card per spec not already on the board:
  - title `<KEY> — <spec H1 after "Spec — <KEY>: ">`;
  - body labels: `Objective:` (first sentence of `## Desired behavior`, else of `## Problem`), `Scope:` (front matter `scope`, split on `, ` at top level), `Acceptance:` (checklist items of `## Acceptance criteria`), `Links:` (spec, plan, and `https://github.com/<owner>/<repo>/issues/<n>` when `issue` is set);
  - `--assignee`, `--workspace worktree`, `--initial-status blocked`, and `--idempotency-key gh:<owner>/<repo>#<n>:<KEY>` when `issue` is set, else `card:<board>:<KEY>`.
- B4. The Issue link must be the full URL: the harness ignores `://` links but rejects other non-`docs/` links, so the design's `- issue: owner/repo#n` form is not used. CLOUD-1.5 parses this URL.
- B5. Link each `blocked_by` edge with `hermes kanban link <parent> <child>`, skipping existing edges.
- B6. Run the harness candidate check (`validate-harness.py --kanban-task-id`) per new card; unblock passing cards (Hermes keeps children in `todo` until parents are `done`). Failing cards stay blocked with a comment naming the failed check.
- B7. Existing cards are matched by title prefix `<KEY> — ` (non-archived) and reused, never duplicated; the idempotency key is the second guard.
- B8. Output: JSON list `[{key, id, status, parents, created}]` on stdout.

## Constraints

- Only the `hermes kanban` CLI (no DB access). Reuse `harness_core.parse_card_body` for a body round-trip check before create.
- Front matter parsing: PyYAML when present, else a minimal parser for the four keys and `blocked_by` inline lists.
- `templates/spec.md` gains `card`, `assignee`, `blocked_by`, `issue`. `kanban-guide.md` and the `SKILL.md` "Create card" steps point to the command.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`. Commit only there; never `git push`.
- Canonical verification: `make lint test`.
- Before review: set this spec and its plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both docs).

## Acceptance criteria

- [ ] Temp board and repo; specs A, B (`blocked_by: [A]`), C (`blocked_by: [A, B]`): one run creates 3 cards with edges A→B, A→C, B→C; A `ready`, B and C `todo`; every body parses with `harness_core.parse_card_body` with all four labels
- [ ] Spec with `issue: o/r#7`: card `Links:` include `https://github.com/o/r/issues/7`; card created with idempotency key `gh:o/r#7:<KEY>`; harness accepts the card
- [ ] Dotted keys (`SHOP-42.1`, `SHOP-42.2` blocked by `.1`) work end to end
- [ ] Second run: all `created: false`, no new cards or edges
- [ ] Cycle, unknown key, missing plan, uninstalled assignee, malformed `issue`, uncommitted spec: exit 1, board unchanged
- [ ] Board without `default_workdir`: exit 1 before any create
- [ ] `blocked_by` naming an existing board card links to it
- [ ] Docs and template updated; `integration-status.md` lists the new functions; test added to `make lifecycle-test`
- [ ] `make lint test` passes

## Edge cases

- Spec without front matter `card`: preflight error naming the file.
- Hermes error mid-create: stop, print cards created so far, exit 1; rerun resumes via title match.
- Harness unavailable: cards stay blocked with comment `harness unavailable`.
- `scope` containing commas inside parentheses: split only on top-level `, `.
