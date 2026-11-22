# Ginflow glossary

- **Spec** — `docs/specs/<KEY>.md`: behavior and contract for one card.
- **Plan** — `docs/plans/<KEY>.md`: execution order for one card.
- **Work Unit** — one card executing one spec/plan pair. Parallel mutation requires separate Workspaces.
- **Repository** — one target GitHub repo as Ginflow holds it: its clone and its board, one each. Never mutated directly; `ginflow.workspace` holds its path. _Avoid_: project, workspace.
- **Workspace** — one git worktree of a Repository holding at most one active card or one shaping run. _Avoid_: repo, clone, project root.
- **Issue** — a GitHub issue that requests work. Shaping one Issue yields one or more Work Units; the Issue has no spec or plan of its own. An Issue may be shaped again; new Work Units continue its card numbering and completed ones are never re-shaped. _Avoid_: ticket, epic, parent spec.
- **Issue key** — `<REPO>-<number>` (e.g. `SHOP-42`): names an Issue, never a card or artifact.
- **Card key** — `<Issue key>.<n>` (e.g. `SHOP-42.1`), always suffixed, even when an Issue yields one card. Names the card and its spec/plan. _Avoid_: task id (that is Hermes's `t_…`).
- **Feedback card** — `<Card key>-fb<n>`: a card that addresses PR review on an existing card's branch. It fixes that card's scope; new scope comes from re-shaping the Issue instead.
- **Change Group** — behavior-oriented review unit mapping acceptance to changed paths.
- **Artifact baseline** — `artifact_baseline`: completion commit plus exact linked paths; the gate compares only those paths for drift.
- **Actionable block** — a card block that needs human intervention because the worker cannot proceed or automatic recovery has failed. _Avoid_: failure, notification.

## Authority boundaries

Hermes remains identity, Kanban, assignment, dispatch, lifecycle, and persistence authority. Ginflow core validates pure records and derives routing. `ginflow-gate` validates evidence at native transitions and publishes the PR after reviewer completion. Target repositories remain authority for product behavior and canonical verification.
