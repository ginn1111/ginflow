---
status: completed
card: PRUNE-1
scope: see spec
owner: ginb
---

# Plan — PRUNE-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. Locate code by symbol. Commit after each step; each step leaves `make test` green.

## Step 1: delete the Initiative chain
- `git rm` lib modules `initiative`, `execution_package`, `execution_batch`, `card_creation`, `decision`, `review_cycle`, `merge_request`, `followup` and their `test_*.py`, plus `test_initiative_workflow.py`. Drop their Makefile `core-test` lines.
- `git grep` each module name in `plugins/` and `skills/`; remove remaining imports.

## Step 2: delete provider documents and documents config
- `git rm skills/ginflow/lib/provider_document.py` + its test, `plugins/ginflow-gate/test_document_baseline.py`, `skills/ginflow/scripts/test-document-config.py`.
- `gate.py`: remove `_content_hash` load and the `document_baseline` check (symbol search `document_baseline`).
- Lifecycle test: remove step `local-provider-document`.
- `project_config.py`: remove `DOC_PROVIDERS`, `STATUS_KEYS`, `DocumentConfigError` and the documents functions; update `__all__`.
- Makefile: drop removed test lines.

## Step 3: routing guidance
- RED: plugin test asserting `no_cards_for_workspace` context contains `docs/specs/<KEY>.md` and not `Discovery`.
- Rewrite that context string in `routing.py`.

## Step 4: docs
- New `docs/adrs/0002-spec-first-cards.md`: decision (spec + plan per card, front matter `card`/`assignee`/`blocked_by`, Hermes `link` edges, stacked branches, PR feedback cards), what was removed and why, trade-offs.
- ADR 0001: front matter `status: superseded`, first line "Superseded by ADR 0002".
- GLOSSARY: keep Work Unit/card, Change Group only if still used; remove Initiative, Execution Package/Batch, Provider document, Document reference/baseline, Tracker status sync, Integration, Decision, Review Cycle, Disposition vs outcome, Decision Projection, Notification, MR Intent, Prototype promotion unless a remaining doc uses the term.
- `SKILL.md`: replace "Four-phase Initiative lifecycle" with "Spec-first flow" (shape → cards → execute → review → PR → feedback); remove `references/decision.md` and its links.
- `docs/architecture`: README links, `ginflow-flow.md`, `ginflow-reference.md`, `ginflow-system.drawio`, `integration-status.md` regenerated for remaining functions.

## Step 5: verify and hand off
```bash
git grep -nE "<pattern from spec>" -- . ':!docs/specs' ':!docs/plans' ':!docs/adrs/0001-*'
make lint test; echo exit=$?
```
Spec + plan `status: completed`; commit; `kanban_request_review` with `verification_result` + `artifact_baseline`.
