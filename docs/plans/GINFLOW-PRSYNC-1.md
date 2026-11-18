---
status: draft
scope: PR-sync integration test runtime isolation
owner: cindy
---
# GINFLOW-PRSYNC-1 — Execution plan

1. Inspect the PR-sync test's subprocess environment and Hermes CLI runtime initialization. Capture a bounded reproduction of the cold `HERMES_HOME` launch and a control using only `HERMES_KANBAN_HOME` (B1).
2. Add a focused red-capable assertion at the test setup seam, then adjust the PR-sync test environment to keep board isolation without cold runtime provisioning. Preserve all existing feedback assertions (B1–B3).
3. Run `python3 skills/ginflow/scripts/test-ginflow-pr-sync.py`, then canonical `make lint && make test`; inspect board isolation and `git diff --check` (B1–B3).
4. Record exact verification evidence, changed files, remaining risks, and next step on `t_3999ca96`. Keep GINFLOW-INSTALL-2 blocked until its canonical verification can be rerun independently.
