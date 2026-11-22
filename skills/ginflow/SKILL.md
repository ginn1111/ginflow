---
name: ginflow
description: Use when starting, resuming, or finishing work in a project under Hermes Kanban. Triggers - "start a task", "shape the work", "spec-first flow", "create a Kanban card", "complete the card", "hand off", "export handoff", "where do docs go". Governs spec-first flow (shape, cards, execute, review, PR), card format, evidence, and stop rules.
---

# ginflow

Workflow integration for Hermes profiles. Hermes owns lifecycle (identity, Kanban, dispatch, state). `ginflow-gate` owns evidence checks at native transitions.

## When to use

- starting, resuming, or closing project work
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

Before implementation, apply the complexity triggers and gate in `references/complex-work-gate.md`. No selected/running card owns the workspace: route new work to shaping. No selected card blocks execution when the complex-work gate applies.

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

## Startup

On first load or session resume, follow `references/project-context.md` for project config and execution startup.

## Continuous flow

Never wait for a human merge to continue. A parent card is `done` when the reviewer completes it; its PR merge is asynchronous.

- Child cards start from the parent's branch, not `main`: stack the worktree (`references/kanban-guide.md` "Stacking"), then unblock. Hermes holds children in `todo` until every parent is `done`.
- Keep dispatching every card whose parents are `done`. Report each opened PR; do not ask before moving on.
- Merging stays with the human, any time and in any order GitHub allows. Stacked PRs make order explicit.

Wait for the human only when:

- the next step is dangerous or irreversible: force-push or history rewrite, deleting branches/boards/cards/data, merging, repo or security settings, credentials, purchases, external messages as the human;
- real human input is needed: a `needs_input` / `capability` block, an unresolvable stack merge conflict, an unclear or conflicting requirement, missing access.

Everything else (open PRs, push card branches, stack, unblock, re-dispatch, recovery) proceeds without asking.

## Definition of done

- [ ] Acceptance criteria satisfied.
- [ ] Relevant project checks ran and passed.
- [ ] Changed files reviewed against scope.
- [ ] Card records verification evidence.
- [ ] Hermes status accurate.
- [ ] Linked artifacts reflect completion.
- [ ] Restartable from documented verification path.
- [ ] Remaining limits or blockers explicit.

## Completion

Before review or completion, follow `references/completion.md` for evidence, metadata, and completed-card artifact checks.

## Stop rules

Stop and clarify when (and only then; a pending PR merge is never a stop reason, see "Continuous flow"):

- card missing required fields
- completed card missing a valid completion commit for linked docs
- completed card artifact missing, committed after, or uncommitted relative to completion commit
- fuzzy requirement, missing acceptance, or no verification path
- unclear cause but user expects direct fix

## References

- `references/completion.md`, `references/handoff-export.md`, `references/example-flow.md`
- `references/complex-work-gate.md` (load before implementation when any complexity trigger applies)
- `references/doc-layout.md`, `references/kanban-guide.md`, `references/drift-detect.md`
- `references/project-context.md`, `references/blank-project-checklist.md`
- `references/workspace-health-warnings.md`
- `references/trace-routing.md` (block kinds, `required_action`; read before `kanban_block`)
- `templates/plan.md`, `templates/spec.md`, `templates/kanban-task.md`, `templates/session-handoff.md`
- `templates/hermes.md`
- maintainer notes: `docs/ginflow-design-notes.md`
