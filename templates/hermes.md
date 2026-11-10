# Project rules

Local-only file: keep it in .git/info/exclude; never commit it and never copy these rules into AGENTS.md or CLAUDE.md (shared with teammates).

This project uses globally installed Hermes profiles sourced from your setup repo.
Global profile behavior lives there. Local project behavior lives here.
Shared workflow, Kanban lifecycle, verification evidence, and optional handoff rules come from `ginflow`.

## Build
- Run project-native verification before claiming done.
- Prefer existing scripts (`make`, `npm`, `pnpm`, `pytest`, etc.) over ad-hoc commands.

## Style
- Keep diffs small.
- Match existing code style and project structure.
- Do not add dependencies without need.

## Ginflow workflow
- Load and follow `ginflow` for target-project startup, task shaping, execution, completion, and handoff. `ginflow` is an external skill: discover it through normal skill-discovery (scan available skills, read its SKILL.md) rather than expecting its instructions to be duplicated here.
- If the `ginflow` skill cannot be located in the current environment, stop before any mutable target-project work and report this as a blocker. Do not proceed ungated.
- Before mutable work, require one selected Kanban card (Hermes Kanban) with objective, scope, acceptance, workspace, status, assignee, and a link to its provider document. Stop when missing or incomplete.
- If requirement is clear: build.
- If cause is unclear: investigate first.
- If requirement is unclear: shape options first.

## Verification
- Declare one canonical project-specific command below. Ginflow runs it from project root.
- Leave real command output or concrete verification evidence.
- If verification is blocked, say exact blocker.
- Ginflow harness stays external and must not be copied into this project.

## Drift detection
- Name the local rules and task artifacts that are authoritative for this project.
- Document generated outputs and the source files or schemas that regenerate them.
- When drift is found, update the authority first, regenerate dependents, rerun the canonical verification command, and record unresolved drift on the selected Kanban card.
- Keep setup-profile verification and the external Ginflow harness out of this project.
- Completed cards must record a Git completion commit and exact linked local artifact paths in `artifact_baseline`. Path-scoped drift blocks use of that card as authority until a human chooses linked versioned docs plus a follow-up card, reopens and reconciles the card, or explicitly approves an editorial baseline advance. Unrelated work remains unblocked; do not use per-file hash fallback.

## Local notes
- Add project-specific build/test/run commands below.
- Add architecture constraints, forbidden areas, and deployment rules below.
- Add key directories, file/git conventions, and project-specific completion requirements below.
- Replace the drift-detection placeholders with this project's authorities and generated-file relationships.

### Example additions
- `make test`
- `pnpm test`
- `pytest -q`
- `cargo test`
- `go test ./...`
- never edit generated files under `dist/`
- ask before production deploy
