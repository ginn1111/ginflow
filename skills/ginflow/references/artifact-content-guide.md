# Artifact content guide

Use this guide when writing or updating project artifacts. Keep each fact in its authority artifact; link instead of copying detail.

## Shared quality rules

- Use one Kanban card ID in filenames, headings, and links.
- Write known facts only. Mark unknowns as `TBD` with owner or blocking decision; never invent them.
- Make scope name affected systems, areas, or paths. Put exclusions in non-goals.
- Make acceptance criteria observable, testable, atomic, and implementation-neutral unless implementation is itself required.
- Link dependencies and source evidence. Do not paste long transcripts or duplicate linked content.
- Update authority artifact first when requirements change, then update links, plan, and card state. Record unresolved drift on card.
- Remove empty optional sections. Do not create artifact without decision value.

## Authority and boundaries

| Artifact | Owns | Must not become |
|---|---|---|

| Spec | exact behavior, contracts, states, failure cases, detailed behavioral acceptance | business pitch or implementation checklist |
| Plan | ordered change and verification path | restated requirements |
| Kanban card | live assignment, workspace, status, thin summary, links, progress evidence | duplicate spec/plan |
| ADR | durable architectural decision, alternatives, consequences | meeting notes or task plan |
| Handoff | approved point-in-time resume snapshot sourced from card and links | independent source of truth |

When content conflicts: latest approved requirement wins; update the Kanban card for scope/outcome, spec first for behavior/contract, ADR first for accepted architecture, and card first for live progress/status. Stop work while material conflict remains unresolved.

## Spec

Use when behavior, API, data, compatibility, security, migration, or failure semantics can drift.

Describe, when relevant:
- actors, preconditions, inputs, outputs, state transitions, and invariants
- success, validation, authorization, error, timeout, retry, concurrency, and partial-failure behavior
- API/data schema, compatibility, migration/rollback, retention, observability, and security constraints
- edge cases and detailed acceptance examples

Use normative language: **must**, **must not**, **may**. Separate confirmed decisions from `TBD` questions. Give behavior stable IDs such as `B1`, `B2` when plan/tests need traceability.

Spec acceptance must not silently widen the Kanban card's scope or change its outcome. Escalate conflict to the card owner.

## Plan

Every step must name:
1. target component, path, or discovery goal
2. concrete change or decision
3. verification evidence produced
4. spec criterion covered when traceability matters

Order steps by dependency. Put investigation before code when cause or target is unknown. Put focused failing test before behavior change when project supports tests. Include migration, compatibility, rollback, rollout, or manual checkpoint only when risk requires it.

Use explicit commands only after confirming project-native commands. Mark steps complete in plan or card, not by rewriting completed steps as prose.

Bad: `Implement feature.`
Good: `Add duplicate-event integration test around webhook handler; verify B2 with <project-native test command>.`

## Kanban card

Keep card thin and current.

At creation:
- short action title
- objective summary
- bounded scope plus key exclusion
- acceptance summary
- real workspace
- links to spec/plan/ADR as applicable
- assignee and accurate status

During work or close, record:
- completed outcome and exact next step
- changed files
- canonical verification command and fresh result
- blockers, risks, decisions, artifact drift, and related cards when present
- before review request, truthful `artifact_baseline` metadata with completion commit and exact linked target-local paths; `ginflow-gate` validates that linked artifacts are committed and free of drift during `kanban_request_review` and final `kanban_complete`

Link all artifacts individually. Never use card body to replace missing required artifact.

## ADR

Create ADR only for accepted or proposed decision with durable, cross-task cost: architecture boundary, dependency, data model, security model, compatibility policy, or hard-to-reverse trade-off. Keep local implementation choices in plan/code.

Filename: follow target convention; otherwise `docs/adrs/NNNN-<kebab-title>.md`, next zero-padded number.

Required:
- title and card link
- status: `proposed`, `accepted`, `deprecated`, or `superseded`
- context and decision drivers
- decision stated plainly
- viable alternatives and why rejected
- positive and negative consequences
- follow-up work or validation

Never rewrite accepted history to hide changed decision. Add new ADR and mark old one `superseded by <link>`. Approval follows target-project ownership rules; absent rule, leave status `proposed` and request owner approval.

## Session handoff

Export only with Gin approval. Source every field from selected card, directly linked artifacts, Git config, or export timestamp as defined by export flow. Preserve source wording for objective, scope, acceptance, progress, decisions, and evidence; summarize only to remove duplication without changing meaning.

Content must answer:
- who owns work and where workspace lives
- which artifacts govern work and whether they drift
- what completed, what remains, and which files changed
- exact verification evidence
- blockers, risks, decisions, related cards, and exact next step

Use required missing-value wording from `ginflow`; never infer facts from chat, repository history, unrelated cards, or OS identity. Handoff freezes snapshot time and never overrides Kanban or authority artifacts.

## Final review

Before linking or dispatching:

- [ ] No invented facts or unresolved material contradictions.
- [ ] Objective, scope, exclusions, and acceptance align.
- [ ] Behavioral detail lives in spec; ordered work lives in plan.
- [ ] Criteria are observable and verification path exists.
- [ ] Risks, dependencies, migration, rollback, security, and failure cases appear when relevant.
- [ ] Card stays thin, current, assigned, and points at real workspace.
- [ ] ADR captures only durable decisions; handoff remains sourced snapshot.
