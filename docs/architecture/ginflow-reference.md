# Ginflow reference architecture

This document is an evidence-based companion to the editable Draw.io diagrams. It explains the current repository implementation and records gaps or external boundaries explicitly.

## What this repository is

Ginflow is a setup/integration repository for Hermes Agent work governance. It is not a product application and it does not own target-project business logic. Its purpose is to make ambiguous, risky, or multi-step work explicit enough to route, execute, verify, and complete without silently bypassing scope or evidence boundaries.

The repository addresses a recurring failure mode: a raw prompt does not by itself establish the target workspace, requirements, root cause, risk, canonical verification, or completion authority. New governed/autonomous work uses Discovery, Shaping, Execution, and Decision around Hermes.

## Runtime and ownership map

| Layer | Current responsibility | Evidence | Authority boundary |
|---|---|---|---|
| Hermes Agent | Profile/runtime lifecycle, skill loading, tools, Kanban, and execution | `skills/ginflow/SKILL.md` (core split and startup) | External runtime; this repo documents integration contracts |
| Ginflow skill | Workflow vocabulary, route/output rules, startup/close/restart guidance, artifact layout, and distributed harness validation | `skills/ginflow/SKILL.md`, `skills/ginflow/lib/harness_core.py` | Shared procedural guidance and validation code distributed to Hermes consumers |
| Ginflow routing core | Reusable routing primitives and structured workflow model | `core/ginflow-core/routing.py` | Library code packaged with installed plugins; target projects do not own its implementation |
| `ginflow-gate` plugin | Hermes integration hooks, routing context, completion validation, feedback/recovery helpers | `plugins/ginflow-gate/plugin.yaml`, `plugins/ginflow-gate/*.py` | Gate/context provider; not a semantic classifier or replacement runtime |
| Kanban card | Durable governed-work assignment: objective, scope, acceptance, workspace, assignee, status, concise link to the provider document, progress | `skills/ginflow/SKILL.md`; `plugins/ginflow-gate/` | Hermes Kanban is lifecycle authority |
| Provider document | One canonical governance record per Work Unit (`local`, `github`, or `linear`) with provider-neutral reference and `document_baseline` | `docs/adrs/0001-artifact-first-execution-packages.md`, `GLOSSARY.md` | Content authority; adapters hold credentials, the gate validates evidence only |
| Target project | Product code, local rules, tests, and canonical verification | `AGENTS.md` contract; `skills/ginflow/SKILL.md` | Target repository owns product delivery |
| Setup verification | Shared repository lint/test and integration health | `Makefile`, `skills/ginflow/scripts/validate-harness.py` | Proves setup/integration health, not target product behavior |
| Target verification | Product-native command selected by target repository | `skills/ginflow/SKILL.md` completion rules | Required evidence for the target change |

## Current user flow

1. **Startup** — confirm the real target workspace and read local `AGENTS.md`/`.hermes.md`.
2. **New Initiative** — Discovery captures problem and boundaries; Shaping approves one artifact-first package; Execution authorizes isolated immutable batches and blocked cards; Integration opens read-only Decision.
3. **Decision and completion** — human review consumes exact evidence, routes follow-up to Execution/Shaping/Discovery, and only `approved_for_mr` yields provider-neutral MR intent. Hermes Kanban remains lifecycle authority.
4. **Execution and verification** — workers change only selected workspaces and run target canonical checks. Setup checks remain separate evidence.
5. **Review and completion** — workers submit governed work with native `kanban_request_review` after canonical verification and linked-artifact finalization. Hermes Kanban owns review-state transitions and reviewer rework; `ginflow-gate` validates evidence, baseline, and drift at native transitions.

## Execution and verification

Workers change only the selected workspace and run target canonical checks. Setup checks remain separate evidence. Hermes owns card and lifecycle transitions; Ginflow validates contracts and evidence.

## Review and completion

Workers submit governed work with native `kanban_request_review` after canonical verification and linked-artifact finalization. Hermes owns review-state transitions and the reviewer rework loop. Reviewers call native `kanban_complete` or `kanban_request_changes`; `ginflow-gate` validates Ginflow evidence, linked artifact state, baseline commit, and drift.

The detailed branch model is in [`ginflow-flow.md`](./ginflow-flow.md), and the routing vocabulary is in [`../../skills/ginflow/SKILL.md`](../../skills/ginflow/SKILL.md).

## Dependency inventory

### Repository-local dependencies

| Dependency | Role | Evidence | Version/status |
|---|---|---|---|
| Python standard library | XML checks, scripts, skill/plugin implementation and tests | `skills/ginflow/lib/*.py`, `core/ginflow-core/*.py`, `plugins/ginflow-gate/*.py`, `skills/ginflow/scripts/*.py` | No package version pinned in this repository |
| POSIX shell utilities | Make targets, setup/install/verification scripts | `Makefile`, `scripts/*.sh` | Environment-provided; exact versions unknown |
| Make | Canonical setup verification entry point | `Makefile` | Environment-provided; exact version unknown |
| Draw.io XML format | Editable architecture diagrams | `docs/architecture/*.drawio` | File format; editor/runtime version unknown |
| Git | Baseline, diff, and artifact-drift evidence | `Makefile`, `skills/ginflow/SKILL.md` | Environment-provided; exact version unknown |

No committed `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, or requirements file was found during this investigation. Therefore this repository does not provide a pinned third-party dependency inventory; documentation must not invent one.

### External/runtime dependencies

| External dependency | Why it matters | What this repo guarantees | Unknowns / limits |
|---|---|---|---|
| Hermes Agent runtime | Loads skills, invokes tools, owns profiles and Kanban lifecycle | Ginflow instructions and plugin hooks target Hermes contracts | Internal implementation and version are external |
| Hermes native Kanban tools | Durable card state and completion authority | Card shape and native completion boundary are documented | Server/storage details are external |
| Current Hermes profile configuration | Locates installed skills/plugins and optional tools | Setup scripts and plugin manifest describe wiring points | Live machine configuration is not fully represented here |
| Optional CodeGraph/MCP tooling | Advisory workspace health and code navigation | `validate-harness.py` reports optional health without making it a blocker | Tool installation/connectivity/version are environment-specific |
| Target project's own toolchain | Product implementation and canonical verification | Ginflow requires the target command and reports it separately | Target project controls its dependencies and versions |

## Problems addressed

- **Ambiguous intent:** Discovery resolves problem, boundaries, and open questions rather than inventing requirements.
- **Wrong execution shape:** Shaping approves one artifact-first package before immutable batch authorization.
- **Workspace collisions:** require isolated workspaces and one active governed card per mutable workspace.
- **Premature execution:** require approved Shaping artifacts, immutable batch authorization, and fail closed on missing fields.
- **Weak completion claims:** require canonical verification and native completion-gate validation.
- **Artifact drift:** compare linked artifacts against a completion baseline and reject drift.
- **Boundary confusion:** keep Hermes, Ginflow core, plugin, skill, and target-project ownership distinct.

## Known gaps and architecture-vs-code inventory

| Finding | Classification | Evidence | User impact / next step |
|---|---|---|---|
| Hermes runtime and Kanban storage are not implemented here | Intentional external boundary | `skills/ginflow/SKILL.md` core split | Users need a working Hermes environment; this repo cannot prove every runtime detail |
| No committed package manifest pins Python or external tool versions | Confirmed gap | Repository file inventory; `Makefile` and scripts | Reproducibility depends on the host/profile environment; document or add a manifest only as separately approved work |
| Target-project verification is not universal | Intentional boundary | `skills/ginflow/SKILL.md` target verification rules | Each target repo must declare its own canonical command |
| Optional CodeGraph/MCP checks are advisory | Confirmed behavior | `skills/ginflow/scripts/validate-harness.py` and optional-tool design plan | Missing optional tooling should warn, not block core work |
| Draw.io and Markdown architecture views are maintained separately | Confirmed maintenance risk | `docs/architecture/ginflow-flow.md` states Draw.io is canonical | Diagram changes require updating derived Markdown; automated synchronization is not present |
| Profile/runtime identity is outside this repository's product scope | Intentional boundary | `AGENTS.md`, `skills/ginflow/SKILL.md` | Profile configuration changes require separate approval and must not be inferred from project docs |
| Exact transitive dependencies, deployment topology, and production SLOs are unknown | Explicit unknown | No committed manifest/deployment contract found | Do not present them as guarantees; investigate only with a separately scoped task |

## Pros and cons for users

### Pros

- Clear separation between Discovery, Shaping, Execution, and Decision.
- Evidence-oriented Kanban completion rather than chat-only status.
- Reusable workflow guidance across target repositories.
- Explicit ownership boundaries reduce accidental runtime/profile changes.
- Standard-library-heavy repository implementation keeps the setup layer small.
- Optional tooling can improve navigation without blocking core verification.

### Cons and trade-offs

- The workflow adds ceremony (Shaping, approved package, blocked cards) even for small changes.
- Users must understand both Hermes-native Kanban states and Ginflow logical states.
- Documentation and diagrams are distributed across skill, plugin, core, and target-project boundaries.
- The setup repository cannot guarantee target-project behavior; two verification commands may be necessary.
- Environment-specific Hermes, optional MCP, and target-toolchain dependencies reduce out-of-the-box reproducibility.
- The completion gate is intentionally strict: incomplete links, drift, or missing evidence stop completion rather than silently repairing claims.

## Reading order

1. [`../../README.md`](../../README.md) — project overview and commands.
2. [`ginflow-flow.md`](./ginflow-flow.md) — route and ownership flow.
3. [`ginflow-system.drawio`](./ginflow-system.drawio) — editable architecture source.
4. [`../../skills/ginflow/SKILL.md`](../../skills/ginflow/SKILL.md) — normative workflow contract.
5. [`../../plugins/ginflow-gate/`](../../plugins/ginflow-gate/) and [`../../core/ginflow-core/`](../../core/ginflow-core/) — implementation evidence.
6. [`../specs/GINFLOW-14.md`](../specs/GINFLOW-14.md) — this documentation task's contract.
