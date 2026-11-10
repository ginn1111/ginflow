---
status: draft
card: CARDS-1
scope: see spec
owner: ginb
---

# Plan — CARDS-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: parse specs
- Core helper (new small module in `skills/ginflow/lib`, e.g. `spec_cards.py`): `load_spec(path)` → key, assignee, blocked_by, scope, title, objective, acceptance, plan path; `order(specs, existing_keys)` → topological order or cycle error.
- Unit-free test through the command later; for now a direct script test of `order` cycles is acceptable only if the command test cannot express it.

## Step 2: `cards create` preflight
- New `skills/ginflow/scripts/test-ginflow-cards.py`: temp `HERMES_HOME`, temp repo + bare origin, board with `default_workdir`; failure cases leave `hermes kanban list` empty.

## Step 3: create + link + unblock
- Create in order with `--json`; link edges; harness check (`validate-harness.py --kanban-task-id`); unblock passing.
- Test the 3-spec graph, statuses, body round-trip, rerun idempotence, existing-card reuse.

## Step 4: docs
- `templates/spec.md`, `references/kanban-guide.md`, `SKILL.md` card section, `integration-status.md`.

## Step 5: verify
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
