---
status: completed
card: PRUNE-1
assignee: ginb
blocked_by: []
scope: skills/ginflow/lib, plugins/ginflow-gate (gate document baseline, routing text), skills/ginflow/scripts tests, Makefile, GLOSSARY.md, docs/adrs, docs/architecture, skills/ginflow/SKILL.md + references
owner: ginb
---

# Spec — PRUNE-1: Remove the unwired Initiative chain and documents config

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

`docs/architecture/integration-status.md` shows a whole record chain that no hook or command reaches: `initiative` → `execution_package` → `execution_batch` → `card_creation` → `decision` → `review_cycle` → `merge_request` / `followup`, plus provider-document hosting (`build_provider_document`, `write_local_document`, the gate's `document_baseline` check for `docs/work-units/`) and the documents config (`DOC_PROVIDERS`, `STATUS_KEYS`, `DocumentConfigError`, `configured_documents`, `documents_block_error`, `documents_error`, `resolve_documents`, `require_ready`, `set_documents`). The flow Gin actually runs is spec-first: `docs/specs` + `docs/plans`, blocked cards, gate, auto-publish, recovery. Gin chose to prune to that flow (brainstorming 2026-11-11, Q1 = A).

## Desired behavior

- The modules above, their tests, and their Makefile/lifecycle-test steps are gone. `card_creation` is deleted too; CARDS-1 rewrites card creation against spec front matter.
- `provider_document.py` is deleted entirely: its only live callers are the `document_baseline` gate check and lifecycle step `local-provider-document`, both of which serve `docs/work-units/` documents no card uses. `artifact_baseline` stays the completion evidence.
- `project_config.py` keeps board/workspace/reviewer/worker/notify/publish/trace config. Worker and reviewer seeding functions stay (INIT-1 wires them).
- Routing `no_cards_for_workspace` guidance describes the spec-first flow (shape `docs/specs/<KEY>.md` + `docs/plans/<KEY>.md`, create blocked cards) instead of "initiative record / Discovery → Shaping → Execution → Decision".
- ADR 0002 "Spec-first cards" records the model; ADR 0001 gets `status: superseded` front matter and a pointer to 0002.
- GLOSSARY, `skills/ginflow/SKILL.md` (phase table → spec-first flow; Execution contract and Definition of done drop batch/Initiative/Decision terms), `references/decision.md` (deleted), other references, `docs/architecture/*` (README, flow, reference, Draw.io, integration-status) describe only what exists.

## Constraints

- Behavior of the live paths (gate completion checks except `document_baseline`, publish, block routing/recovery, routing context, trace, harness CLI) is unchanged.
- No new modules, no new config keys.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: reviewer `kanban_complete` auto-publishes a GitHub PR to `main`. Gin merges.
- Canonical verification: `make lint test`.
- Before review: set this spec and the linked plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both linked docs).
- Parent design: GitHub issue `GINFLOW-SPEC-FIRST` (see Links on the card). Decisions there are settled; do not re-open them.

## Acceptance criteria

- [ ] `git grep -nE "initiative|execution_package|execution_batch|card_creation|review_cycle|merge_request|followup|provider_document|document_baseline|work-units|set_documents|resolve_documents|require_ready|DOC_PROVIDERS|STATUS_KEYS" -- . ':!docs/specs' ':!docs/plans' ':!docs/adrs/0001-*'` → only lines in ADR 0002 that name what was removed
- [ ] `git grep -n "decision\.py\|from decision\|load(\"decision\")"` → no output
- [ ] ADR 0002 exists; ADR 0001 front matter `status: superseded`
- [ ] Routing context for a workspace with no cards names `docs/specs/<KEY>.md` and `docs/plans/<KEY>.md`, not Initiative phases (test asserts)
- [ ] `integration-status.md` lists only remaining functions; summary has no "Not wired" Initiative entry
- [ ] `make lint test` passes

## Edge cases

- A remaining module imports a deleted one: remove the import and its dead branch; if live behavior depends on it, stop and block `needs_input`.
- Draw.io: delete removed boxes/edges; keep layout of the rest. Mermaid in `ginflow-flow.md` follows Draw.io.

## Blocked by

None.
