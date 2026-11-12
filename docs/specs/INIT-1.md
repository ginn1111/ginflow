---
status: completed
card: INIT-1
assignee: ginb
blocked_by: [PRUNE-1]
scope: skills/ginflow/scripts (new ginflow command + test), skills/ginflow/lib/project_config.py, scripts/install.sh, Makefile, docs/architecture/integration-status.md, skills/ginflow/references/project-context.md
owner: ginb
---

# Spec — INIT-1: `ginflow init` sets up a project in one command

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

Project setup is spread across agent prose and manual steps. Nobody sets the board `default_workdir` (RECOVERY-1's first dispatch died on `workspace_kind=worktree but no workspace_path`), the reviewer profile is seeded by hand, worker defaults are never persisted, and stale local `main` silently becomes every worktree's base. `initialize_context`, `seed_default_reviewer`, `hermes_default_reviewer`, `persist_worker_defaults`, `configured_worker` and `resolve_worker_dispatch` exist but nothing calls them.

## Desired behavior

New `ginflow` command (installed with the skill, on `PATH` after `make install`) with subcommand `init`:

```
ginflow init [--project PATH] [--board NAME | --new-board NAME] [--worker PROFILE[:PROVIDER:MODEL]]
```

Steps, each printing one line `ok|set|fail <step>: <detail>`:

1. `context` — `.ginflow.yaml` valid: ok. Missing: `initialize_context` with `--board` (current) or `--new-board` (created via `hermes kanban boards create --default-workdir <repo>`); neither given → fail with the choice. Invalid → fail (`context_error`), never overwrite.
2. `workdir` — board `default_workdir` equals repo root: ok; unset → `hermes kanban boards set-default-workdir`; set to another path → fail.
3. `reviewer` — `seed_default_reviewer` against installed profiles and current `hermes_default_reviewer()`; writes only on difference.
4. `worker` — `--worker` given: `persist_worker_defaults`; print `resolve_worker_dispatch` result.
5. `notify` — `notify_error` clean: ok, else fail.
6. `auth` — publish provider CLI auth (`gh auth status` / `glab auth status`) when `publish` configured.
7. `main` — `git fetch` remote; local target branch equal to or ahead of `origin/<target>`: ok; behind → fail with count.
8. `dispatcher` — `hermes gateway status` running: ok, else fail.

Exit 0 when no `fail`, else 1. Second run with nothing changed prints only `ok` lines and writes nothing.

`make install PROFILES="..." PROJECT=<path>` runs `ginflow init --project <path>` once per profile (`HERMES_HOME` of that profile) after copying files. Without `PROJECT`, install behaves as today.

## Constraints

- Reuse `project_config` functions; no new config keys. `.ginflow.yaml` is written only by `initialize_context` / `persist_worker_defaults`.
- No interactive prompts in the command; the `/ginflow` skill asks Gin and passes flags.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`, based on `main`. Commit only there; never `git push` yourself.
- PR: reviewer `kanban_complete` auto-publishes a GitHub PR to `main`. Gin merges.
- Canonical verification: `make lint test`.
- Before review: set this spec and the linked plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both linked docs).
- Parent design: GitHub issue `GINFLOW-SPEC-FIRST` (see Links on the card). Decisions there are settled; do not re-open them.

## Acceptance criteria

- [ ] Fresh temp project (temp `HERMES_HOME`, temp repo with bare `origin`): `ginflow init --project P --new-board B` exits 0; board B exists with `default_workdir` = P; `.ginflow.yaml` names B; reviewer written to Hermes config
- [ ] Immediate second run: exit 0, only `ok` lines, `.ginflow.yaml` and Hermes config byte-identical
- [ ] Local `main` behind `origin/main` → `fail main: behind origin/main by N`, exit 1
- [ ] Board `default_workdir` pointing elsewhere → `fail workdir`, exit 1, nothing rewritten
- [ ] `make install PROJECT=<path>` runs init per profile (install test asserts)
- [ ] `integration-status.md` marks the 6 functions wired (`ginflow init`); `project-context.md` documents the command
- [ ] `make lint test` passes

## Edge cases

- Gateway not installed in the test env: the test stubs `hermes gateway status` via `PATH` shim only for that call, or asserts the `fail dispatcher` line.
- No `publish` block: `auth` step prints `ok auth: publish not configured`.
- No remote / no `origin/<target>`: `fail main: no origin/<target>`.

## Blocked by

- PRUNE-1 (both edit `project_config.py`)
