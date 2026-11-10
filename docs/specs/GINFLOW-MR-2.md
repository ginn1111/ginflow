---
status: draft
scope: skills/ginflow/lib/publish.py, plugins/ginflow-gate/publish.py, plugins/ginflow-gate/routing.py, skills/ginflow/lib/project_config.py, tests, docs
owner: cindy
---

# Spec — GINFLOW-MR-2 auto-detect MR base branch; provider-only publish config

## Problem

GINFLOW-MR-1 sends every MR/PR to one fixed `ginflow.publish.target`. Cards that branch from different feature branches get the wrong base. Nothing checks that the reviewed commit actually contains the base, and the existing-MR lookup ignores the base.

## Desired behavior

`ginflow.publish` keeps only `provider`. Everything else is derived:

| Setting | Source |
|---|---|
| provider CLI | `github` = `gh`, `gitlab` = `glab` |
| remote | fixed `origin` |
| host | from `git remote get-url origin`; SSH aliases resolved with `ssh -G <alias>` hostname |
| base | completion `metadata.base` when set, else auto-detected |
| draft | always false |

Auto-detect, run in reviewer `pre_tool_call` for `kanban_complete` after `git fetch origin`:

1. Candidates = `refs/remotes/origin/*`, excluding `origin/HEAD` and the card's own branch.
2. Keep candidates whose tip is an ancestor of the reviewed commit (`git merge-base --is-ancestor`).
3. Score = `git rev-list --count <tip>..<commit>`. Pick the lowest score.
4. No candidate, or a tie on the lowest score: block completion with `ambiguous or missing base: <list>; set metadata.base`.

Override `metadata.base`: must exist as `origin/<base>` and be an ancestor of the commit, else block (`base <x> is not an ancestor of <commit>; rebase or fix metadata.base`).

## Inputs / outputs

Config:

```yaml
ginflow:
  publish:
    provider: gitlab   # github | gitlab; the only field
```

Commands (argv, no shell):

- `git -C <ws> fetch origin`
- `git -C <ws> for-each-ref --format=%(refname:strip=3) refs/remotes/origin`
- `git -C <ws> merge-base --is-ancestor origin/<b> <commit>`
- `git -C <ws> rev-list --count origin/<b>..<commit>`
- auth: `gh auth status --hostname <host>` / `glab auth status --hostname <host>`
- existing: `gh pr list -H <branch> -B <base> --json url` / `glab mr list -s <branch> -t <base> -F json`
- create: `gh pr create -H <branch> -B <base> ...` / `glab mr create -s <branch> -b <base> ... --push=false --yes`

Output unchanged: `ginflow-publish: <url>` comment; MR body gains `Base: <base> (auto-detected|metadata.base)`.

## Constraints

- Old fields `target`, `remote`, `host`, `draft` are rejected as unknown (fail closed; no silent ignore).
- Startup routing auth check uses the derived host of the workspace `origin`.
- Base detection is a pure function over injected git results (testable without network); plugin does the git calls.
- No force push, no new dependencies, stdlib only.

## Acceptance criteria
- [ ] `publish_error` accepts `{provider}` only; rejects `target`/`remote`/`host`/`draft` and bad provider.
- [ ] Host derived from `git@h:g/p.git`, `https://h/g/p.git`, `ssh://git@h:22/g/p`, and SSH alias via `ssh -G`.
- [ ] `select_base` picks the fewest-ahead ancestor; excludes own branch and `HEAD`; blocks on tie or none.
- [ ] `metadata.base` override used when it is an ancestor; blocked when not or missing on origin.
- [ ] Existing-MR lookup filters by source and base; create uses detected base; body names base and how it was chosen.
- [ ] Hook test: two remote branches (`develop`, `feat/x` from develop) with worktree off `feat/x` gets MR to `feat/x`; tie case blocks; override works.
- [ ] Docs updated (`docs/guides/project-config.md`, `skills/ginflow/references/project-context.md`, `decision.md`).
- [ ] `make lint test` passes.

## Edge cases
- Base branch equal to commit (zero commits ahead): candidate with score 0 means nothing to merge; block `nothing to publish`.
- `git fetch` fails (offline): block completion with fetch stderr.
- Hermes removed the worktree after completion: post-step uses stored git dir (unchanged from MR-1); base is resolved in pre-step, not post.
