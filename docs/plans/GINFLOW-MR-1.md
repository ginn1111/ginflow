---
status: draft
scope: GINFLOW-MR-1
owner: cindy
---

# Plan — GINFLOW-MR-1

Content rules: `references/artifact-content-guide.md` in `ginflow`.

1. `core/ginflow-core/publish.py`: pure `build_push_argv`, `build_create_argv`, `build_existing_argv`, `build_auth_argv`, `parse_mr_url`; `test_publish.py`; add to `make core-test`.
2. `skills/ginflow/lib/project_config.py`: `configured_publish`, `publish_error`.
3. `plugins/ginflow-gate/gate.py`: accept `worktree:` workspace in `validate_completion`.
4. `plugins/ginflow-gate/publish.py`: `auth_error`, `pre_complete` (reviewer + publish + worktree: block on auth/branch), `post_complete` (push, existing check, create, comment). Wire into `gate.pre_tool_call` / `gate.post_tool_call`.
5. `plugins/ginflow-gate/routing.py`: append publish-auth blocker to routing context.
6. `plugins/ginflow-gate/test_publish_hook.py` with fake `gh`/`glab`/`git`/`hermes` on PATH; add to `make plugin-test`.
7. Docs: `docs/guides/project-config.md`, `skills/ginflow/references/decision.md`, `references/project-context.md`.
8. Verify `make lint test`; record evidence; set spec/plan `status: completed`.
