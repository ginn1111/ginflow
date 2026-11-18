---
status: draft
scope: PR-sync integration test runtime isolation
owner: cindy
---
# GINFLOW-PRSYNC-1 — Bound PR-sync test runtime setup

## Problem

The canonical `make lint && make test` run stalls at `skills/ginflow/scripts/test-ginflow-pr-sync.py`. The test sets a new `HERMES_HOME` before invoking `hermes kanban init`, which starts preparing dependencies for that data root rather than immediately exercising Kanban. An isolated invocation reproduced the dependency-preparation output and remained unfinished after 156 seconds. The same Kanban init command with only an isolated `HERMES_KANBAN_HOME` returned exit 0 promptly.

This is separate from the installer fixture path correction owned by GINFLOW-INSTALL-2 (`t_aab8dee1`).

## Desired behavior

- B1: The PR-sync integration test must isolate its Kanban board and test data without implicitly installing a fresh Hermes runtime on every invocation.
- B2: The test must continue to validate PR feedback card creation, append/deduplication, failure reporting, and merged-PR behavior against a live temporary board and stub GitHub CLI.
- B3: The test must not read or mutate the real ginflow board or production PR state.

## Constraints

Only change `skills/ginflow/scripts/test-ginflow-pr-sync.py` test setup and assertions. Do not modify Hermes installation, production PR-sync behavior, or installer implementation. Preserve unrelated worktree changes.

## Acceptance criteria

- [ ] A fast, deterministic signal demonstrates that test setup invokes Hermes without a cold isolated runtime while still using a temporary Kanban board.
- [ ] `python3 skills/ginflow/scripts/test-ginflow-pr-sync.py` exits 0 and reports its PR-sync assertions passing.
- [ ] `make lint && make test` exits 0 on macOS.
