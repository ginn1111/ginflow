---
status: approved
card: CLOUD-1.4
scope: see spec
owner: ginb
---

# Plan — CLOUD-1.4

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: parse specs (B1, B2 file checks)
- New `skills/ginflow/lib/spec_cards.py`: `load_spec(path)` → key, assignee, blocked_by, issue, scope list, title, objective, acceptance, plan path; `order(specs, existing_keys)` → topological order or cycle error.
- New `skills/ginflow/scripts/test-ginflow-cards.py`: temp `HERMES_HOME`, temp repo + bare origin, board with `default_workdir`; preflight failure cases leave `hermes kanban list` empty.

## Step 2: create, link, unblock (B3–B7)
- `ginflow cards create` in `skills/ginflow/scripts/ginflow.py`: body build + `parse_card_body` round-trip, create with idempotency key, link edges, harness check, unblock.
- Tests: 3-spec graph and statuses, issue URL link + key, dotted keys, rerun idempotence, existing-card reuse.

## Step 3: docs (constraints)
- `skills/ginflow/templates/spec.md`, `references/kanban-guide.md`, `SKILL.md` card section, `docs/architecture/integration-status.md`; add test to `lifecycle-test` in `Makefile`.

## Step 4: verify and hand off
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
