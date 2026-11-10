# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Repository role

Ginflow is a Hermes Agent setup/integration repository, not a product application. It owns the shared Ginflow workflow, reusable routing/validation code, Hermes plugins, profile setup scripts, target-project templates, architecture docs, and deterministic integration tests. Target repositories own product code, local rules, product tests, and canonical product verification.

Keep this boundary intact: do not use this repository as a target-project workspace, and do not put target-project artifacts here unless the change explicitly modifies the global profile system.

## Architecture

- `skills/ginflow/` is the normative operational contract. It defines the Discovery → Shaping → Execution → Decision lifecycle, Execution Package and provider-document rules, Kanban card shape and lifecycle handoff, artifact layout, startup/completion rules, and the external harness validator.
- `core/ginflow-core/` contains reusable routing and execution-package primitives. Shared logic must stay independent of Hermes runtime details where possible.
- `plugins/ginflow-gate/` integrates with native Hermes hooks and enforces governed completion evidence. It supplies bounded routing context and validates card fields, verification metadata, linked artifacts, baseline commits, and drift; Hermes remains lifecycle authority.
- `plugins/ginflow-trace/` provides optional trace logging. Tracing is off by default and writes under the target workspace's `.ginflow/` paths when enabled.
- `scripts/` owns setup, installation, profile verification, and integration-test helpers. `templates/` supplies starter target-project context and governed artifact templates.
- `docs/` holds architecture and governed repository documentation. Editable Draw.io sources and derived explanations must remain consistent.

Hermes owns profiles, tools, Kanban state, assignments, and lifecycle transitions. Ginflow supplies routing and worker guidance; `ginflow-gate` validates evidence at native transitions. A target project remains authority for product behavior and its canonical verification command.

## Workflow constraints

Load and follow `skills/ginflow/SKILL.md` for target-project startup, task shaping, execution, completion, handoff, and setup-repo versus target-repo decisions. Before mutable target-project work, require a complete selected Kanban card from an approved Execution Package. Governed artifacts belong in the target repository and use the card's stable ID in their paths.

Read `INSTALL.md` before profile installation. Preserve profile-owned identity, secrets, authentication, memories, sessions, and runtime data. Do not edit generated/local state such as `.hermes/`, `.codegraph/`, `.ginflow/`, trace logs, or Python caches.

## Development commands

Run from repository root. The implementation uses Python standard library, POSIX shell tools, Make, Git, Draw.io XML, and PyYAML for checked tooling.

```bash
# Environment and optional dependency
make doctor
make doctor-deps                 # installs PyYAML only

# Static checks and canonical repository verification
make lint
make test                        # lint + core, lifecycle, plugin, and installer tests

# Individual checks
make lifecycle-test
make plugin-test
make trace-test
make install-test
python3 plugins/ginflow-gate/test_ginflow_gate.py
python3 plugins/ginflow-trace/test_ginflow_trace.py

# Setup/profile operations
make install PROFILES="<profile>"
make uninstall
make verify PROFILES="<profile>"
make verify-strict PROFILES="<profile>"


# Remove generated caches and local CodeGraph index
make clean
```

`make lint` runs `bash -n` over project shell scripts and `python3 -m py_compile` over project Python scripts. `make test` is the setup-repository check; it does not replace a target project's own canonical verification. Report target-project verification separately.

## Completion expectations

Keep diffs narrow and preserve unrelated worktree changes. For Ginflow work, record exact changed files, baseline/commit metadata, linked artifacts, verification commands/results, and blockers on the selected card. Before declaring setup-repository changes done, run `make lint && make test`; report exact failures and any checks blocked by missing external Hermes/profile context.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `ginn1111/ginflow`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout — `GLOSSARY.md` at repository root and ADRs under `docs/adrs/`. See `docs/agents/domain.md`.
