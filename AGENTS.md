# Setup-repo rules

Ginflow is a setup and integration repository for Hermes Agent. It owns Ginflow workflow assets, reusable routing code, Hermes plugins, profile setup scripts, target-project templates, and deterministic integration tests. It is not a product application; target repositories own product code, tests, local rules, and product verification.

## Ginflow
- Load and follow `ginflow` for target-project startup, task shaping, execution, completion, and handoff. The repo copy is `skills/ginflow/SKILL.md`; discover/load it through normal skill discovery.
- If `ginflow` cannot be located, stop before mutable target-project work and report a blocker.
- Do not use this setup repo as target-project workspace.
- Before mutable target-project work, require a selected Kanban card with objective, scope, acceptance, workspace, status, assignee, and links.

## Boundaries and layout
- `skills/ginflow/` — workflow contract, templates, references, validator, tests
- `skills/ginflow/lib/` — single home for core modules (harness, config, routing, publish, Execution Package primitives) and their tests
- `plugins/ginflow-gate/` — completion policy plugin and tests
- `plugins/ginflow-trace/` — optional trace plugin and tests
- `scripts/` — setup, installation, verification, and test helpers
- `templates/` — target-project starter context
- `docs/` — architecture, specs, plans, and reports
- `.hermes/`, `.codegraph/`, `__pycache__/`, `.ginflow/`, and trace logs are generated/local state
- Do not edit profile distribution identity, secrets, runtime state, or generated `__pycache__/` files.

## Dev environment
- Run commands from repository root.
- Implementation uses Python standard library, POSIX shell tools, Make, Git, and Draw.io XML. No committed `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, or requirements file exists.
- `doctor` checks `hermes`, `codegraph`, Python, Git, and PyYAML. Install the only checked Python dependency with `make doctor-deps` (`python3 -m pip install pyyaml`). CodeGraph is advisory for core repository checks.
- Read `INSTALL.md` before profile installation. Setup requires existing Hermes profiles and preserves profile-owned identity, secrets, auth, memories, sessions, and runtime data.

## Build, test, lint
- `make lint` — `bash -n` all shell scripts and `python3 -m py_compile` project Python scripts.
- `make test` — canonical repository verification: `lint`, `core-test`, `lifecycle-test`, `plugin-test`, and `install-test`.
- `make lifecycle-test` — canonical Ginflow flat-flow integration test.
- `make plugin-test` — Ginflow gate tests plus trace tests.
- `make install-test` — installer test.
- `make verify` — validate installed integrations via the Ginflow harness.
- `make lint && make test` before declaring setup-repo changes done.
- Run target-project verification from target repo; never substitute setup verification for product checks.

## Setup commands
- `make doctor`
- `make install` / `make uninstall` — install or remove installer-owned Ginflow integrations.
- `make clean` removes Python caches and `.codegraph`; do not use it to discard source changes.

## Conventions and completion
- Preserve setup-repo versus target-repo ownership. Target-project artifacts belong in target repos, not here, unless changing the global profile system.
- Use project-native scripts and existing Make targets. Keep changes narrow; preserve unrelated worktree changes.
- Local authorities: `AGENTS.md`, `Makefile`, `README.md`, `INSTALL.md`, and `skills/ginflow/SKILL.md`.
- For Ginflow Kanban work, record verification evidence, changed files, commit/baseline metadata, linked artifacts, and blockers on the selected card. `ginflow-gate` validates required fields, evidence, baseline commit, and artifact drift at native completion transitions.
- Do not commit credentials, `.env`, profile identity, or runtime state. Do not push without explicit approval.
- If verification fails on non-owned code or required context is missing, report a blocker; do not fix silently or invent requirements.

## Git conventions
- `make lint` must pass before commit.
- `make test` must pass before push.
- Keep generated paths in `.gitignore`; current generated paths include `__pycache__/`, `.ginflow/`, `.codegraph/`, `.hermes/`, trace logs, and `.ginflow-install.json`.
- Completion status must be truthful: report exact commands/results, changed files, known limitations, and clear `done` or `blocked` status.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `ginn1111/ginflow`, managed with `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix` — applied as GitHub issue labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `GLOSSARY.md` at repository root and ADRs under `docs/adrs/`. See `docs/agents/domain.md`.
