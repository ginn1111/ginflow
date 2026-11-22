---
status: completed
card: CLOUD-1.3
assignee: ginb
blocked_by: []
issue: ginn1111/ginflow#52
scope: skills/ginflow/lib/gh_app.py (new), skills/ginflow/scripts/ginflow.py (gh token subcommand), skills/ginflow/scripts/test-ginflow-gh-token.py (new), Makefile (lifecycle-test entry), docs/guides/github-app.md (new), docs/architecture/integration-status.md
owner: ginb
---

# Spec — CLOUD-1.3: GitHub App token helper

Content rules: `references/artifact-content-guide.md` in `ginflow`. Parent: issue #49 (CLOUD-1); design `docs/plans/2026-11-19-cloud-agents-design.md`; decision `docs/adrs/0003-cloud-agents.md`.

## Problem

The cloud-agents container must call GitHub (git fetch/push, `gh` issue comments, PRs) without a personal access token. ADR 0003 chose a GitHub App: the container holds only the App private key, mounted read-only, and must mint short-lived installation tokens for each call. Nothing in Ginflow mints them today.

## Desired behavior

Configuration (environment only; no `.ginflow.yaml` keys):

| Variable | Meaning | Default |
| --- | --- | --- |
| `GINFLOW_GH_APP_ID` | App id | required |
| `GINFLOW_GH_APP_KEY` | private key PEM path | `/run/secrets/gh-app.pem` |
| `GINFLOW_GH_INSTALLATION_ID` | installation used when no repo is given | optional |
| `GINFLOW_GH_API` | API base URL | `https://api.github.com` |
| `GINFLOW_GH_CACHE` | token cache dir | `$HERMES_HOME/cache/ginflow-gh` |

- B0. Multiple repos: one App serves every Repository it is granted. A grant belongs to an installation, one per account (`ginn1111`, each org). An installation token covers all repos in that installation, so repos are mapped to installations and tokens are cached per installation, not per repo. Callers in the container always pass `--repo`; `GINFLOW_GH_INSTALLATION_ID` is a fallback for a single-installation setup only.
- B1. `ginflow gh token [--repo OWNER/REPO | --installation ID]` prints one installation token and a newline, nothing else, exit 0. Installation resolution: `--installation`; else `--repo` via `GET /repos/{owner}/{repo}/installation`; else `GINFLOW_GH_INSTALLATION_ID`; else `fail token: no installation (pass --repo or --installation)`, exit 1.
- B2. App JWT: RS256, header `{"alg":"RS256","typ":"JWT"}`, claims `iat = now-60`, `exp = now+540`, `iss = APP_ID`; signed with `openssl dgst -sha256 -sign <key>`. Token minted via `POST /app/installations/{id}/access_tokens` with `Authorization: Bearer <jwt>`, `Accept: application/vnd.github+json`.
- B3. Cache: one file per installation (`<cache>/<id>.json`: `token`, `expires_at`), dir mode 0700, file mode 0600, atomic write. A cached token is reused while more than 300 s remain; otherwise re-minted. Repo→installation lookups are cached in `<cache>/repos.json`.
- B4. Git credential helper: `ginflow gh token credential <op>` speaks the git credential protocol on stdin/stdout. `get` with `host=github.com` (or the host of `GINFLOW_GH_API`'s web counterpart, `github.com` by default) prints `username=x-access-token` and `password=<token>`; the repo comes from `path=` (`owner/repo[.git]`, requires `credential.useHttpPath=true`), else the env installation. Any other host prints nothing, exit 0. `store` and `erase` read stdin and exit 0.
- B5. Secrets: stdout carries only the token or credential lines. Errors go to stderr as `fail token: <reason>`, naming the key path but never key or token contents. A missing or unreadable key, failed signing, or a non-2xx API response exits 1.
- B6. `docs/guides/github-app.md`: App permissions (Contents, Issues, Pull requests: read/write; Metadata: read), events (Issues, Issue comment, Pull request, Pull request review, Pull request review comment, Installation repositories), the env table, and git setup:
  `git config --global credential.https://github.com.helper '!ginflow gh token credential'` plus `credential.useHttpPath true`; `gh` gets `GH_TOKEN="$(ginflow gh token --repo <o>/<r>)"` (the container wrapper belongs to CLOUD-1.8).

## Constraints

- Standard library (`urllib`, `json`, `base64`) plus the `openssl` binary. No new Python dependencies.
- Network only to `GINFLOW_GH_API`; tests point it at a local stub.
- Workspace: Hermes worktree `.worktrees/<task-id>` on branch `wt/<task-id>`. Commit only there; never `git push`.
- Canonical verification: `make lint test`.
- Before review: set this spec and its plan to `status: completed`, commit, `kanban_request_review` with `verification_result` and `artifact_baseline` (both docs).

## Acceptance criteria

- [ ] Test generates an RSA key with `openssl genrsa`; a local `http.server` stub verifies each JWT signature with the public key (`openssl dgst -verify`) and the `iss`/`exp` claims, and serves installation and token responses
- [ ] `ginflow gh token --installation 7` prints exactly the stub token; second call within validity makes no token request (stub hit count)
- [ ] Cached token with `expires_at` 200 s away is re-minted
- [ ] `--repo o/r` resolves the installation through the stub once, then from cache
- [ ] Multiple repos: stub maps `o/a` and `o/b` to installation 7 and `p/c` to installation 9; tokens for `o/a` and `o/b` are the same (one mint for installation 7), the token for `p/c` differs; `credential get` with `path=p/c.git` returns installation 9's token
- [ ] Repo the App is not granted (stub 404): exit 1, `fail token: App not installed on <owner>/<repo>`
- [ ] `credential get` with `host=github.com`, `path=o/r.git` prints `username=x-access-token` / `password=<token>`; `host=example.com` prints nothing; `store`/`erase` exit 0
- [ ] Missing key file: exit 1, stderr names the path, stdout empty; stub 401: exit 1, no token printed
- [ ] Cache dir 0700, cache files 0600
- [ ] `docs/guides/github-app.md` written; `integration-status.md` lists the new functions; test added to `make lifecycle-test`
- [ ] `make lint test` passes

## Edge cases

- Clock skew: `iat` backdated 60 s; `exp` stays under GitHub's 10-minute limit.
- Corrupt cache file: ignored and overwritten.
- Stale repo mapping (App removed from a repo, or repo moved to another account): a 404 when minting for a cached installation drops that `repos.json` entry and resolves the repo again once.
- Concurrent callers: both may mint; last atomic write wins; no partial file.
- `openssl` missing: `fail token: openssl not found`, exit 1.
