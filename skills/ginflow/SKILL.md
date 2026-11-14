---
name: ginflow
description: Use when starting, resuming, or finishing work in a project under Hermes Kanban. Triggers - "start a task", "shape the work", "spec-first flow", "create a Kanban card", "complete the card", "hand off", "export handoff", "where do docs go". Governs spec-first flow (shape, cards, execute, review, PR), card format, evidence, and stop rules.
---

# ginflow

Workflow integration for Hermes profiles. Hermes owns lifecycle (identity, Kanban, dispatch, state). Target repo owns product code and canonical verification. Setup repo owns tooling. `ginflow-gate` owns evidence checks at native transitions.

Never use setup repo as workspace. Never copy harness into target repo.

## When to use

- starting, resuming, or closing target-project work
- shaping a Kanban card or its spec/plan
- deciding where docs belong
- exporting a session handoff
- blank project setup

## Spec-first flow

| Step | Does | Card needed |
| --- | --- | --- |
| Shape | write `docs/specs/<KEY>.md` + `docs/plans/<KEY>.md`; approve | no |
| Cards | create blocked cards linking the artifacts | no |
| Execute | work inside card scope | yes |
| Review | `kanban_request_review`; reviewer `kanban_complete` | yes |
| PR | gate auto-publishes the PR | n/a |
| Feedback | PR feedback becomes new cards | n/a |

Shaping may write artifacts but never mutates product code or dispatches. Terms: `GLOSSARY.md`. Decision: `docs/adrs/0002-spec-first-cards.md`.

No selected/running card owns the workspace: route new work to shaping. No selected card blocks project execution.

## Doc layout

| Artifact | Purpose |
| --- | --- |
| `.hermes.md` | local Hermes rules incl. ginflow routing; untracked via `.git/info/exclude` |
| `AGENTS.md` | team-shared; read-only for ginflow; never write ginflow instructions here or in `CLAUDE.md` |
| `docs/specs/<CARD-ID>.md` | behavior/contract detail |
| `docs/plans/<CARD-ID>.md` | execution order |
| `docs/handoffs/<CARD-ID>.md` | optional exported snapshot |
| `docs/adrs/` | durable decisions |

- `<CARD-ID>` (e.g. `APP-9`): human work key, used in titles and artifact paths.
- `$TASK_ID` (e.g. `t_ab12`): Hermes-generated task ID. Use it for Kanban tools and `--kanban-task-id`. Never rename artifacts to it.
- Artifacts: YAML frontmatter at byte 0 (`status`, `scope`, `owner`). No body-only `Status:`.
- No artifacts in setup repo unless task changes the global profile system.
- Details: `references/doc-layout.md`, `references/artifact-content-guide.md`.

### Kanban status mapping

| Ginflow | Hermes Kanban |
| --- | --- |
| `next` | `todo` or `ready` |
| `in_progress` | `running` |
| `blocked` | `blocked` |
| `done` | `done` |
| `cancelled` | `archived` |

Never write `in_progress` to Kanban. `todo`/`ready` needs startup validation before claim.

## Project session startup

First `/ginflow` load: inspect `.ginflow.yaml` at repo root. Missing: show resolved workspace and board, ask user to use it or create a new board (non-empty name required), then write config. Malformed, incomplete, or workspace-mismatched: fail closed, do not overwrite or switch silently. Schema, worker defaults, trace flag: `references/project-context.md`.

Execution startup, in order:

1. Confirm workspace is the real target repo.
2. Read `.hermes.md`, then `AGENTS.md`.
3. Board empty: route to shaping. Else `kanban_list`/`kanban_show`, resume selected card.
4. Execution requires a selected card. Stop if absent.
5. Confirm card fields: ID, title, objective, scope, acceptance, workspace, status, assignee, links. Stop if any missing.
6. Read linked spec/plan.
7. Completed card: run linked-artifact drift gate first.
8. Inspect git state; run project baseline verification.
9. Run external harness against target and card. Report project verification and harness separately.
10. Follow routing context injected by `ginflow-gate`.

Routing hints from the plugin are advisory, not authorization. Call `skill_view` yourself. Precedence: target rules, card contract, Ginflow matrix, selected skill, skill defaults.

## Execution contract

- One active card per mutable workspace. Parallel cards need an isolated worktree or different workspace.
- Execution requires a selected card.
- Stay in card scope and target workspace. Use project-native commands.
- Block on material ambiguity; do not invent requirements.
- Do not resume or derive work from a completed card with unresolved drift. Unrelated cards and unlinked project work may continue.

## Continuous flow

Never wait for a human merge to continue. A parent card is `done` when the reviewer completes it; its PR merge is asynchronous.

- Child cards start from the parent's branch, not `main`: stack the worktree (`references/kanban-guide.md` "Stacking"), then unblock. Hermes holds children in `todo` until every parent is `done`.
- Keep dispatching every card whose parents are `done`. Report each opened PR; do not ask before moving on.
- Merging stays with the human, any time and in any order GitHub allows. Stacked PRs make order explicit.

Wait for the human only when:

- the next step is dangerous or irreversible: force-push or history rewrite, deleting branches/boards/cards/data, merging, repo or security settings, credentials, purchases, external messages as the human;
- real human input is needed: a `needs_input` / `capability` block, an unresolvable stack merge conflict, an unclear or conflicting requirement, missing access.

Everything else (open PRs, push card branches, stack, unblock, re-dispatch, recovery) proceeds without asking.

## Kanban card shape

Thin card: objective, scope, acceptance, link to artifact. Exact body labels (gate rejects malformed):

```text
Objective: <what to achieve>
Scope:
- <files/dirs/areas>
Acceptance:
- <observable completion check>
Links:
- docs/specs/<CARD-ID>.md
```

Hermes stores workspace, status, assignee, ID on the task row, and `artifact_baseline` in latest completion run metadata. No shadow card JSON.

Create cards from specs: put `card`, `assignee`, `blocked_by: [KEY]` in spec front matter, then run `ginflow cards create [--board B] docs/specs/*.md`. It preflights (nothing created on failure), creates blocked cards in dependency order, links `blocked_by` edges, runs the harness candidate check, unblocks passing cards, prints JSON. Rerun is idempotent (matches title prefix `<KEY> — `). Manual path:

Create card without dispatch race:

1. Draft card and artifacts in memory.
2. Create card assigned to the current profile, full future links, `--initial-status blocked`. Current profile loads its configured skill; do not force `--skill ginflow`.
3. Write and commit linked artifacts; run project checks and harness candidate check.
4. Unblock only after readiness passes.

Workspace: `--workspace dir:/abs/path` or `--workspace worktree`.

Body missing sections: keep blocked, ask human to fix in dashboard, rerun harness. `hermes kanban edit` cannot edit body; do not invent a `--body` option. Replacement card only with human approval, linked back to the malformed card.

Build-ready card answers: what to change, where, how done is judged, what not to touch. Missing and risk material: keep blocked, ask the user.

## Definition of done

- [ ] Acceptance criteria satisfied.
- [ ] Relevant project checks ran and passed.
- [ ] Changed files reviewed against scope.
- [ ] Card records verification evidence.
- [ ] Hermes status accurate.
- [ ] Linked artifacts reflect completion.
- [ ] Restartable from documented verification path.
- [ ] Remaining limits or blockers explicit.

## Completion report

Immediately before reporting completion:

1. Run canonical project verification declared by target repo.
2. Read `git status --short`; report only files under card workspace.
3. Quote canonical command and exact fresh result.
4. Record same evidence on card before `kanban_request_review` or `kanban_complete`.
5. Review workspace per `references/workspace-health-warnings.md`; record `Workspace warnings` on card. Warnings do not block by default.

Checklists, metadata, harness examples: `references/completion.md`. Do not substitute temporary checks for canonical verification. Unavailable or failing: report blocked.

```
kanban_request_review(task_id='<hermes-task-id, e.g. t_ab12>', summary='<short review request>',
  metadata={'verification_result': {'commit': '<commit>', 'command': 'make test', 'result': 'passed'},
            'artifact_baseline': {'commit': '<commit>', 'paths': ['docs/specs/<CARD-ID>.md']}})
```

Any worker may complete a card assigned to it through `ginflow-gate`; reviewer calls `kanban_complete` with matching metadata. `ginflow-gate` synchronously validates required card fields, verification metadata, baseline commit, exact linked paths, and drift. If `ginflow-gate` is not installed, fail closed: report blocker, make no completion claim, record evidence and baseline on the card by hand.

### Completed-card artifact gate

Compare only linked paths against completion commit. Do not compare the whole repository. Do not use per-file SHA fallback. Never silently advance completion commit. Drift blocks affected lifecycle use only. Never copy harness script into target repo. Report project verification and ginflow harness as separate results. Drift layers and order: `references/drift-detect.md`. Candidate check: harness `--kanban-task-id "$TASK_ID" --baseline-commit "$COMMIT" --baseline-path <path>` (see `references/completion.md`).

## Session close and restart

Kanban card is default durable handoff. Before ending unfinished or blocked work, record on card: outcome, changed files, verification commands and results, blockers or risks, exact next step, accurate status. Next session resumes from card, linked artifacts, local rules, repo state. Transcript and memory are supporting context only.

## Optional session handoff export

`/hermes handoff export`, only when the user wants a portable snapshot. Ask the user which card; never auto-select; write only after approval. Flow: `references/handoff-export.md`.

## Blank project flow

Copy setup `templates/hermes.md` to `.hermes.md`, add to `.git/info/exclude` before project edits. Add known commands; leave placeholders for unknown. One canonical verification command. No executable files: record `baseline unavailable: no implementation yet`. Then shape first task. Full list and `TERMINAL_CWD` pitfall: `references/blank-project-checklist.md`.

## Stop rules

Stop and clarify when (and only then; a pending PR merge is never a stop reason, see "Continuous flow"):

- wrong repo
- no selected card after pre-card shaping
- card missing required fields
- completed card missing a valid completion commit for linked docs
- completed card artifact missing, committed after, or uncommitted relative to completion commit
- fuzzy requirement, missing acceptance, or no verification path
- unclear cause but user expects direct fix

## References

- `references/completion.md`, `references/handoff-export.md`, `references/example-flow.md`
- `references/doc-layout.md`, `references/kanban-guide.md`, `references/drift-detect.md`
- `references/project-context.md`, `references/blank-project-checklist.md`
- `references/workspace-health-warnings.md`
- `references/trace-routing.md` (block kinds, `required_action`; read before `kanban_block`)
- `templates/plan.md`, `templates/spec.md`, `templates/kanban-task.md`, `templates/session-handoff.md`
- setup repo `templates/hermes.md`
- maintainer notes: `docs/ginflow-design-notes.md` (setup repo)
