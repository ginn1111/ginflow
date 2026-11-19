---
status: approved
scope: cloud-agents container, GitHub App webhook route, repo onboarding, issue-driven spec-first flow
owner: cindy
---

# Design — Cloud agents: issue-driven Ginflow in one container

Terms: `GLOSSARY.md` (Repository, Workspace, Issue, Issue key, Card key, Feedback card). Decision record: `docs/adrs/0003-cloud-agents.md`.

## Goal

Cindy (orchestrator) receives GitHub Issue events, runs the Ginflow spec-first flow for the Issue, and reports progress as Issue comments. ginb executes cards. Gin decides by labels and comments; Gin merges.

## Topology

One long-lived container serves every Repository.

```
/data/hermes/                 HERMES_HOME: cindy + ginb profiles, one board per Repository
/data/repos/<owner>/<repo>/   Repository clone (never mutated directly)
  .worktrees/<task-id>/       card Workspaces (current ginflow convention)
  .worktrees/shape-<KEY>/     shaping Workspace
/data/repos/<owner>/<repo>.lock   per-Repository lock
/run/secrets/gh-app.pem       GitHub App private key, read-only, outside /data
```

- Non-root user, no Docker socket. Gateway exposes one HTTP route.
- Container start: `hermes gateway` + dispatcher; `ginflow gh redeliver --since <last-seen>` replays deliveries missed while down.

## Repository mapping (derived, no registry)

| Thing | Value |
| --- | --- |
| Clone | `/data/repos/<owner>/<repo>` |
| Board slug | `gh-<owner>-<repo>` |
| Board `default_workdir` | the clone |
| `.ginflow.yaml`, `.hermes.md` | written by onboarding, listed in `.git/info/exclude` |
| Issue key | `<REPO>-<number>` (`REPO` = upper-cased repo name, override in `.ginflow.yaml`) |

`ginflow repo ensure <owner>/<repo>` is idempotent: clone if absent, `git fetch`, create board if absent, `ginflow init --new-board gh-<owner>-<repo>`, write exclude entries. Second run prints only `ok` lines.

## Event ingress

GitHub App (on `ginn1111`, all or selected repos) → `POST /webhooks/github` (`hermes webhook subscribe github --signature github --route-profile cindy --script ginflow-gh-filter --skills ginflow`).

Hermes already provides: HMAC check (`X-Hub-Signature-256`) and duplicate-delivery suppression by `X-GitHub-Delivery`.

`ginflow-gh-filter` (stdin payload → stdout event JSON, empty = drop). Must finish well under GitHub's 10 s timeout (Hermes runs it before responding; 30 s default cap), so it does no network or git work:

1. Drop events whose `sender` is the App bot.
2. Drop label/comment events whose `sender.login` is not in the allowlist (`ginn1111`).
3. Drop event types outside the table below.
4. Emit `{repo, board, workspace, issue, issue_key, event, actor, comment_id?}`. Never forward issue or comment bodies; the agent fetches them with `gh` and treats them as untrusted content.

The agent run then takes the Repository lock and calls `ginflow repo ensure` before anything else.

## Issue state machine

| Trigger (by Gin) | Cindy does | Issue feedback |
| --- | --- | --- |
| label `ginflow:shape` | shaping Workspace `shape/<ISSUE-KEY>`: write one spec/plan pair per card (`<ISSUE-KEY>.<n>`), commit, open draft PR | comment: card list, open questions, PR link |
| comment on a shaping Issue | revise artifacts, push to the same draft PR | comment: what changed |
| label `ginflow:approved` | create cards blocked → link → harness → unblock; ginb executes | comment: card list with task ids |
| card → review / blocked / done | `ginflow-gate` transition hook | one comment `[<CARD-KEY>] <state> → <link>`; blocked adds `ginflow:blocked` label and the question |
| PR review/comment on a card PR | `ginflow pr sync` for that PR only (replaces polling) | Feedback card `<CARD-KEY>-fb<n>`; Issue comment |
| all cards done | add `ginflow:done`; Issue stays open | summary comment |

Rules:

- Re-shaping an Issue continues card numbering (`.4`, `.5`); completed cards' artifacts are never edited.
- Card body `Links:` carries `- issue: <owner>/<repo>#<n>`; the gate reads it to find the Issue.
- Card creation uses `--idempotency-key gh:<owner>/<repo>#<n>:<CARD-KEY>`.
- Bot comments are prefixed `[ginflow]`; the bot identity is the authoritative loop filter.
- Merge stays with Gin. Branch protection on the default branch blocks the bot from merging.

## Auth

A git credential helper and a `gh` wrapper mint GitHub App installation tokens (1 h) from `/run/secrets/gh-app.pem` per call. No PAT in the container. Agents never read the key. Force-push remains forbidden.

## Errors and concurrency

| Case | Handling |
| --- | --- |
| `repo ensure` fails (clone, init, auth) | Comment on the Issue if possible, notify Gin via gateway, stop. GitHub redelivery retries. |
| concurrent events, same Repository | per-Repository `flock` serializes ensure and shaping; cards already isolated by Workspace |
| comment while shaping runs | waits on the lock; applied as the next revision |
| card blocked | Issue comment with reason + `ginflow:blocked`; Gin's comment/label resumes |
| worker crash / timeout | Hermes retries to `max-retries`, then blocked as above |
| restart | state on `/data`; redeliver missed deliveries |
| load | global cap on concurrent workers |

## Components to build

1. `ginflow repo ensure` (`skills/ginflow/scripts/ginflow.py`).
2. `ginflow-gh-filter` webhook script.
3. Issue notifier in `plugins/ginflow-gate` (transition → Issue comment/label).
4. Card creation from spec front matter (ADR 0002 follow-up).
5. Event-driven `ginflow pr sync --pr <url>`.
6. GitHub App token helper (git credential helper + `gh` wrapper).
7. `cloud-agents/`: Dockerfile, entrypoint, compose example, `make docker-smoke`.
8. Fix: `.ginflow.yaml` must be local per clone (currently committed with an absolute path).

## Testing

`make test` (deterministic, stub `gh`, temp `HERMES_HOME`, local bare repos):

- filter: bot drop, allowlist, event mapping, no body forwarding
- `repo ensure`: idempotent; board, workdir, `.ginflow.yaml`, exclude entries
- notifier: one comment per transition; blocked label
- card creation: idempotency key prevents duplicates on redelivery

`make docker-smoke` (needs Docker, not in `make test`): build, start, `hermes webhook test github` with an `issues.labeled` fixture.

## Out of scope (v1)

- Per-job containers, iron-proxy egress injection, GitLab, auto-merge, multi-user allowlists.
