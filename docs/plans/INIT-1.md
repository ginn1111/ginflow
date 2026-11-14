---
status: completed
card: INIT-1
scope: see spec
owner: ginb
---

# Plan — INIT-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: command skeleton
- New `skills/ginflow/scripts/ginflow.py` (argparse, subcommand `init`; later cards add `cards`, `pr`). Loads core via the existing single core loader pattern.
- `scripts/install.sh`: symlink `~/.local/bin/ginflow` → installed skill's `scripts/ginflow.py`; uninstall removes it. Add to `scripts/test-install.sh`.

## Step 2: init steps 1–4
- New `skills/ginflow/scripts/test-ginflow-init.py`: temp `HERMES_HOME`, `hermes kanban init`, temp repo + bare origin; assert board/workdir/config/reviewer and idempotence.
- Implement steps `context`, `workdir`, `reviewer`, `worker` using `project_config` functions and `hermes kanban boards` / `hermes config`.

## Step 3: checks 5–8
- Tests: behind-origin repo → `fail main`; no publish → `ok auth`; dispatcher line present.
- Implement `notify`, `auth` (reuse publish auth argv builder), `main`, `dispatcher`.

## Step 4: install hook
- `Makefile` install target passes `PROJECT`; `install.sh` runs `HERMES_HOME=<profile home> ginflow init --project "$PROJECT"` per profile when set.
- Add `test-ginflow-init.py` to `lifecycle-test`.

## Step 5: docs + verify
- `references/project-context.md`: command, steps, flags. `integration-status.md`: flip 6 functions to wired.
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
