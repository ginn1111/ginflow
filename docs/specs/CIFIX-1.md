---
status: completed
scope: plugins/ginflow-gate/test_stacking.py
owner: cindy
---
# CIFIX-1 — test_stacking.py skips without hermes CLI

## Problem

CI (`.github/workflows`, `make lint test`) fails on PR #33 and #35 at `plugin-test`:
`test_stacking.py` runs `hermes kanban init`, the runner has no `hermes`, `FileNotFoundError`.

## Behavior

- `hermes` missing from PATH: print `SKIP: stacking hook (hermes CLI not installed)`, exit 0.
- `hermes` present: test runs unchanged.

Matches sibling guards in `test_block_routing.py`, `test-ginflow-init.py`, `test-ginflow-pr-sync.py`.

## Acceptance criteria

- [x] Without `hermes` on PATH, test prints `SKIP: ...`, exits 0
- [x] `make lint test` passes with and without `hermes` on PATH
- [x] CI `make-test` green on PR #33 and #35

## Out of scope

- Installing `hermes` in CI (test stays local-only coverage).
- `compgen: not found` in `make lint` (Makefile:39, dash has no `compgen`); separate card.
