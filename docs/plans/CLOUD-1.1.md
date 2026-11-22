---
status: completed
card: CLOUD-1.1
scope: see spec
owner: ginb
---

# Plan — CLOUD-1.1

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: one config lookup (B2, B3)
- Extend `skills/ginflow/scripts/test-worktree-context.py`: untracked config in the main checkout, worktree without a copy → readers return main values; writer from worktree updates main file only; worktree with its own copy wins.
- `project_config.config_path` resolves per B2; writers use it. Grep for direct `".ginflow.yaml"` joins (`plugins/ginflow-gate/stacking.py`, `ginflow.py`) and route them through the lookup.
- Verify: `python3 skills/ginflow/scripts/test-worktree-context.py`.

## Step 2: `init` exclude step (B4, B5)
- Extend `skills/ginflow/scripts/test-ginflow-init.py`: fresh repo → `set exclude`, clean `git status`; rerun → `ok exclude`; repo tracking the file → `fail exclude`, index unchanged.
- Add `Init.exclude` after `context` in `skills/ginflow/scripts/ginflow.py`.
- Verify: `python3 skills/ginflow/scripts/test-ginflow-init.py`.

## Step 3: untrack in setup repo (B6)
- `git rm --cached .ginflow.yaml`; add `.ginflow.yaml` to `.gitignore`.
- Verify: `git ls-files .ginflow.yaml` prints nothing; local file still present.

## Step 4: docs (B7)
- `docs/guides/project-config.md`, `README.md`, `skills/ginflow/references/project-context.md`, `docs/architecture/integration-status.md`.

## Step 5: verify and hand off
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
