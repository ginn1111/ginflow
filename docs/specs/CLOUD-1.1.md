---
status: approved
card: CLOUD-1.1
assignee: ginb
blocked_by: []
issue: ginn1111/ginflow#50
scope: skills/ginflow/lib/project_config.py (config lookup), skills/ginflow/scripts/ginflow.py (init exclude step) + tests, .gitignore, .ginflow.yaml (untrack), docs/guides/project-config.md, README.md, skills/ginflow/references/project-context.md
owner: ginb
---

# Spec — CLOUD-1.1: Settings file local to each clone

Content rules: `references/artifact-content-guide.md` in `ginflow`. Parent: issue #49 (CLOUD-1); design `docs/plans/2026-11-19-cloud-agents-design.md`; terms `GLOSSARY.md` (Repository, Workspace).

## Problem

`.ginflow.yaml` stores the absolute Repository path, yet this repo commits it (`/home/aioz/...` on `main`), so every other machine sees a modified, wrong file. Target repos would hit the same problem once a container clones them. Untracking the file alone breaks card Workspaces: Hermes worktrees (`<repo>/.worktrees/<task-id>`) then contain no `.ginflow.yaml`, and routing, gate board resolution, and `pr sync` read it from the current directory.

## Desired behavior

- B1. `.ginflow.yaml` is per-clone local state. It must never be committed by Ginflow.
- B2. Config lookup: for a workspace path `W`, the config file is `W/.ginflow.yaml` when it exists; otherwise, when `W` is inside a git worktree, the main checkout's `.ginflow.yaml` (parent of `git rev-parse --git-common-dir`). Every reader (`config_exists`, `load_config`, `context_error`, `configured_*`, `resolve_board`, gate, routing, stacking, `pr sync`) goes through this one lookup.
- B3. Writers (`persist_context`, `persist_worker_defaults`, `persist_reviewer`, `initialize_context`) write the resolved file: the main checkout's file when called from a worktree that has none. A worktree never gets its own copy.
- B4. `ginflow init` gains step `exclude` (after `context`): ensures `.ginflow.yaml` and `.hermes.md` are lines in `<git-common-dir>/info/exclude`. Prints `set exclude: added <names>` when it appends, `ok exclude: present` otherwise. It must not touch `.gitignore` in a target repo.
- B5. `ginflow init` in a repo that tracks `.ginflow.yaml` prints `fail exclude: .ginflow.yaml is tracked; run git rm --cached .ginflow.yaml` and changes nothing else in git.
- B6. Setup repo: `.ginflow.yaml` removed from the index (`git rm --cached`, local file kept) and listed in `.gitignore` next to the other generated paths.
- B7. Docs (`docs/guides/project-config.md`, `README.md`, `references/project-context.md`) state the file is local per clone, git-excluded, and shared by that clone's worktrees.

## Constraints

- Standard library plus optional PyYAML, as today. No new config keys.
- `context_error` keeps its workspace-match rule; with B2 a worktree resolves to the main checkout's file, which already passes `_same_repository`.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`. Commit only there; never `git push`.
- Canonical verification: `make lint test`.
- Before review: set this spec and its plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both docs).

## Acceptance criteria

- [ ] Fresh clone, `ginflow init --new-board b`: `.ginflow.yaml` written, `info/exclude` holds `.ginflow.yaml` and `.hermes.md`, `git status --short` is empty; rerun prints only `ok` lines
- [ ] Repo tracking `.ginflow.yaml`: `fail exclude: ...`, exit 1, index unchanged
- [ ] Worktree with no `.ginflow.yaml`: `config_exists`, `context_error` (None), `configured_context`, and `resolve_board` return the main checkout's values; `persist_worker_defaults` from the worktree updates the main checkout's file and creates none in the worktree
- [ ] Worktree with its own `.ginflow.yaml` (legacy tracked case): that file wins
- [ ] Setup repo no longer tracks `.ginflow.yaml`; `.gitignore` lists it
- [ ] Docs updated; `docs/architecture/integration-status.md` lists the lookup function
- [ ] `make lint test` passes

## Edge cases

- Not a git repo: lookup is `W/.ginflow.yaml` only (current behavior).
- `info/exclude` missing: create it.
- Exclude entries already present with surrounding whitespace or as `/.ginflow.yaml`: treated as present.
- Bare clone or unreadable common dir: fall back to `W/.ginflow.yaml`, no error.
