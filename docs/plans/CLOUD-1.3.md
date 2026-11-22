---
status: completed
card: CLOUD-1.3
scope: see spec
owner: ginb
---

# Plan — CLOUD-1.3

Content rules: `references/artifact-content-guide.md` in `ginflow`. RED test first per step; commit per step.

## Step 1: test harness with stub App API
- New `skills/ginflow/scripts/test-ginflow-gh-token.py`: temp dir, `openssl genrsa` key, threaded `http.server` stub (`/repos/o/r/installation`, `/app/installations/<id>/access_tokens`) that verifies JWT signature and claims and counts hits; runs the CLI as a subprocess with `GINFLOW_GH_*` env.
- Verify: test fails (no `gh token` subcommand).

## Step 2: mint and cache (B1–B3, B5)
- New `skills/ginflow/lib/gh_app.py`: `app_jwt`, `installation_for_repo`, `installation_token` (cache read/write, 300 s margin).
- `ginflow gh token` subcommand in `skills/ginflow/scripts/ginflow.py`.
- Verify: token, cache reuse, re-mint, repo lookup, multiple repos across two installations, ungranted repo, stale mapping, missing key, 401, file modes.

## Step 3: credential helper (B4)
- `ginflow gh token credential get|store|erase`.
- Verify: github.com, other host, store/erase cases.

## Step 4: docs and wiring (B6)
- `docs/guides/github-app.md`; `docs/architecture/integration-status.md`; add test to `lifecycle-test` in `Makefile`.

## Step 5: verify and hand off
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review`.
