---
status: draft
scope: GINFLOW-MR-2
owner: cindy
---

# Plan — GINFLOW-MR-2

Content rules: `references/artifact-content-guide.md` in `ginflow`.

1. `skills/ginflow/lib/publish.py`: add pure `parse_remote_host(url)`, `select_base(candidates, scores, branch)`; `build_existing_argv(provider, branch, base)`; `build_auth_argv(provider, host)`; drop `draft` param from `build_create_argv`. Extend `test_publish.py`.
2. `skills/ginflow/lib/project_config.py`: `PUBLISH_FIELDS = {"provider"}`; `configured_publish` returns `{"provider"}` only.
3. `plugins/ginflow-gate/publish.py`: `_host(ws)` via remote URL + `ssh -G`; `_resolve_base(ws, commit, branch, override)` runs fetch/for-each-ref/merge-base/rev-list and calls `select_base`; `prepare` stores base + reason; `publish` uses it; body adds base line.
4. `plugins/ginflow-gate/routing.py`: startup auth with derived host.
5. Rewrite `plugins/ginflow-gate/test_publish_hook.py` cases for detection, tie, override, provider-only config.
6. Docs: `docs/guides/project-config.md`, `skills/ginflow/references/project-context.md`, `skills/ginflow/references/decision.md`.
7. `make lint test`; spec/plan `status: completed`; `kanban_request_review` with evidence.
