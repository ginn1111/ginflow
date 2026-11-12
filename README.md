# Ginflow

[![test](https://github.com/ginn1111/ginflow/actions/workflows/test.yml/badge.svg)](https://github.com/ginn1111/ginflow/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Ginflow: a workflow, routing, and completion-gate layer around [Hermes Agent](https://hermes-agent.nousresearch.com/) Kanban.** It makes autonomous agent work scoped, restartable, and evidence-backed.

> **Status: early.** Contracts may change.

Hermes is an agent runtime with profiles and a native Kanban board. Ginflow adds shared documents, routing, and gates so a card cannot be completed without proof.

## Features

- **Spec-first flow** that settles ambiguity before code is touched.
- **Spec + plan per card** (`docs/specs`, `docs/plans`); Kanban cards stay short and link to them.
- **Completion gates** (`ginflow-gate`) check card fields, verification evidence, linked artifacts, baseline commits, and drift at native Hermes transitions.
- **Reusable core** (`skills/ginflow/lib/`): routing and publish primitives, independent of Hermes.
- **Optional tracing** (`ginflow-trace`), off by default.

| Step | Outcome |
|---|---|
| Shape | `docs/specs/<KEY>.md` + `docs/plans/<KEY>.md` |
| Cards | Blocked Kanban cards linking the artifacts |
| Execute | Worker implements in card scope, runs canonical verification |
| Review | `kanban_request_review` then reviewer `kanban_complete`; gate auto-publishes the PR |

Hermes stays the authority for cards, assignments, and lifecycle state. Target repositories keep their own code, rules, and canonical verification.

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/ginn1111/ginflow/main/install.sh | bash
hermes plugins enable ginflow-gate     # then restart Hermes sessions
```

Needs `git`, `python3`, `make`, and Hermes with at least one installed profile. The installer clones to `~/.ginflow`, installs the skill to `~/.agents/skills/ginflow`, and installs `ginflow-gate` and `ginflow-trace` into each profile. It never edits profile config, identity, secrets, or sessions.

```bash
PROFILES="a b" curl -fsSL .../install.sh | bash   # limit to selected profiles
```

Full walkthrough, with a read-before-run option, update, uninstall, and troubleshooting: [docs/guides/getting-started.md](docs/guides/getting-started.md).

## Usage

In your target repository (not this one):

```bash
cp ~/.ginflow/templates/hermes.md .hermes.md
echo .hermes.md >> .git/info/exclude
```

Set the project's canonical verification command in `.hermes.md`, open Hermes there, and run `/ginflow`. It creates `.ginflow.yaml` and walks shape → cards → execute → review → PR. Workers finish with `kanban_request_review`; `ginflow-gate` validates evidence there and at `kanban_complete`.

Minimal `.ginflow.yaml` (written for you; shown for reference):

```yaml
ginflow:
  board: <Kanban board slug>
  workspace: /absolute/path/to/project
  worker:
    profile: <worker Hermes profile>
```

More options and the evidence rules: [docs/guides/project-config.md](docs/guides/project-config.md).

## How it works

| Path | Role |
|---|---|
| `skills/ginflow/` | Normative workflow contract and harness validator |
| `skills/ginflow/lib/` | Harness, config, routing, and publish primitives |
| `plugins/ginflow-gate/` | Hermes hooks: routing context and completion enforcement |
| `plugins/ginflow-trace/` | Optional trace logging |
| `templates/` | Starter target-project rules and artifact templates |
| `scripts/` | Install, setup, verify, and test helpers |

## Not yet supported

- Gateway notification transport and subscriptions
- Provider-specific merge request publication

## Documentation

- [Getting started](docs/guides/getting-started.md)
- [Project config and evidence](docs/guides/project-config.md)
- [Workflow contract](skills/ginflow/SKILL.md)
- [Ginflow flow](docs/architecture/ginflow-flow.md)
- [System diagram](docs/architecture/ginflow-system.drawio) and [reference architecture](docs/architecture/ginflow-reference.md)
- [Glossary](GLOSSARY.md)

## Contributing

Open an issue on [GitHub Issues](https://github.com/ginn1111/ginflow/issues) before large changes. Before a pull request:

```bash
make lint && make test
```

Keep diffs narrow. This repository holds setup and integration code only; target-project artifacts belong in the target repository.

## License

[MIT](LICENSE)
