# Ginflow glossary

- **Spec** — `docs/specs/<KEY>.md`: behavior and contract for one card.
- **Plan** — `docs/plans/<KEY>.md`: execution order for one card.
- **Work Unit** — one card executing one spec/plan pair. Parallel mutation requires isolated worktrees or workspaces.
- **Change Group** — behavior-oriented review unit mapping acceptance to changed paths.
- **Artifact baseline** — `artifact_baseline`: completion commit plus exact linked paths; the gate compares only those paths for drift.

## Authority boundaries

Hermes remains identity, Kanban, assignment, dispatch, lifecycle, and persistence authority. Ginflow core validates pure records and derives routing. `ginflow-gate` validates evidence at native transitions and publishes the PR after reviewer completion. Target repositories remain authority for product behavior and canonical verification.
