---
status: draft
scope: core/ginflow-core/publish.py, plugins/ginflow-gate (gate.py, publish.py, routing.py), skills/ginflow/lib/project_config.py, docs
owner: cindy
---

# Spec — GINFLOW-MR-1 auto-publish MR on reviewer completion

## Problem

Ginflow stops at a provider-neutral `merge_request_intent`. Nobody opens the MR/PR, so the loop "review pass -> MR -> human reads evidence" never closes. Worktree cards also cannot complete: `gate.validate_completion` rejects any non-`dir:` workspace.

## Desired behavior

Opt-in per repo. When `.ginflow.yaml` has `ginflow.publish`, and the configured reviewer profile calls `kanban_complete` on a worktree card that passes the gate, `ginflow-gate` pushes the reviewed branch and opens an MR/PR without asking a human. Gin's standing approval (2026-11-10) covers this push. Merge stays human.

Without `ginflow.publish`, behavior is unchanged.

## Inputs / outputs

Config:

```yaml
ginflow:
  publish:
    provider: github   # github | gitlab (required)
    target: develop    # target branch (required)
    remote: origin     # optional, default origin
    draft: false       # optional, default false
```

Card inputs: `workspace_kind=worktree`, `workspace_path`, `branch_name`, title, id; `verification_result.commit` from completion metadata.

Commands (built by pure `core/ginflow-core/publish.py`, never via shell):

- push: `git -C <worktree> push <remote> <commit>:refs/heads/<branch>`
- github: `gh pr create -H <branch> -B <target> -t <title> -b <body> [--draft]`
- gitlab: `glab mr create -s <branch> -b <target> -t <title> -d <body> [--draft] --push=false --yes`
- existing check: `gh pr list -H <branch> --json url -q '.[0].url'` / `glab mr list -s <branch> -F json`
- auth: `gh auth status` / `glab auth status`

Output: MR/PR URL recorded as Kanban comment `ginflow-publish: <url>`; failures recorded as `ginflow-publish failed: <cmd>: <stderr>`.

## Constraints

- Never force-push; refuse refs starting with `-`, non-hex commits, unknown providers.
- Publish only for the configured `ginflow.reviewer.profile` (active profile == reviewer) and only on `kanban_complete`.
- Auth precheck fails closed: reviewer `kanban_complete` blocked while CLI unauthenticated or `branch_name` missing, so a card never reaches done without an MR.
- Post-completion publish is observer-only: errors never raise, they become a card comment. Rerun is idempotent (existing MR/PR detected, URL re-recorded).
- Startup check: when `publish` is configured, `pre_llm_call` routing reports unauthenticated CLI as a blocker (`mutation_allowed=False`).
- Stdlib only. No new dependencies.

## Acceptance criteria
- [ ] `build_push_argv` / `build_create_argv` return exact argv for github and gitlab, incl. `--draft`; guards reject bad provider, `-`-prefixed refs, non-hex commit.
- [ ] `validate_completion` accepts `worktree:<path>` workspaces.
- [ ] `ginflow.publish` validated by `project_config.publish_error`; malformed block reported, absent block = None.
- [ ] Reviewer `kanban_complete` blocked when publish CLI auth fails; allowed when it passes; non-reviewer and no-publish paths untouched.
- [ ] `post_tool_call` on successful reviewer `kanban_complete` runs push + create via fake `gh`/`glab` on PATH and comments URL; existing MR skips create; failure comments error and does not raise.
- [ ] Routing context includes publish-auth blocker when configured CLI unauthenticated.
- [ ] `make lint test` passes.

## Edge cases
- `dir:` workspace card with publish configured: no publish (no branch), no block.
- Tool result reports error: no publish.
- Worktree removed by Hermes cleanup after completion: Hermes removes a worktree only when every commit is reachable from a remote ref, so a missing worktree path means already pushed; skip push, still create MR. Worktree path is captured in `pre_tool_call`.
