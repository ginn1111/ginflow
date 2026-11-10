---
status: draft
scope: skills/ginflow/lib/project_config.py; test fixtures under skills/ginflow/scripts/ and plugins/ginflow-gate/; .ginflow.yaml, README.md, docs/guides/project-config.md, skills/ginflow/references/project-context.md
owner: ginb
---

# Spec — CLEANUP-1.5: Versionless .ginflow.yaml; stale version fails closed

## Problem / desired behavior

Project config holds only the `ginflow` mapping. Any other top-level key, including a stale `version: 1`, fails closed with `project config has unknown top-level keys: <keys>`. First-use initialization writes no version. The unused preview/apply migration API and its backup folder are removed. This repo's own config and all test fixtures drop the version line, and the project-context reference, README and config guide show the versionless shape and say how to fix a stale key.

## Acceptance criteria

- [ ] A config with `version: 1` makes startup routing fail closed with the unknown-top-level-keys message
- [ ] Saving a documents block into such a config is refused, and the file is unchanged
- [ ] Initialization writes `ginflow: {board, workspace}` only
- [ ] The migration API no longer exists, and no code or docs mention it
- [ ] No test fixture or doc example contains `version: 1`
- [ ] `make lint test` passes

## Blocked by

- #4 (GitHub issue numbers)

## Constraints

- Workspace: main checkout `/home/aioz/personal/ginflow`, local commits only, never `git push`.
- Stay in card scope. Smallest coherent commits.
- Canonical verification: `make lint test`, run serially (Hermes-backed tests share Kanban test boards).
- Before review: set this spec and the linked plan frontmatter to `status: completed`, commit, then `kanban_request_review` with `verification_result` and `artifact_baseline` (paths = both linked docs).
- Parent issue: https://github.com/ginn1111/ginflow/issues/1 ; ticket: https://github.com/ginn1111/ginflow/issues/6


## Rollout constraint

Installed profiles (`~/.agents/skills/ginflow`, `~/.hermes/profiles/{cindy,ginb}/plugins/ginflow-gate`) still require `version: 1`. After committing, before `kanban_request_review`, call `kanban_block` kind `needs_input` with a `required_action:` line asking Gin to approve `make install PROFILES="cindy ginb"`. Do not run the install yourself.
