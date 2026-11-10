# Getting started

Zero to first governed task. About 10 minutes.

## 1. Prerequisites

You need `git`, `python3`, `make`, and [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/profiles) with at least one profile that has a `config.yaml`.

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash   # or: pip install hermes-agent
hermes --version
hermes profile install github.com/owner/profile --alias
hermes profile list
```

If no profile exists, the installer exits before writing anything.

## 2. Install

```bash
curl -fsSL https://raw.githubusercontent.com/ginn1111/ginflow/main/install.sh | bash
```

Prefer to read first:

```bash
curl -fsSLo install.sh https://raw.githubusercontent.com/ginn1111/ginflow/main/install.sh
less install.sh && bash install.sh
```

The script clones to `~/.ginflow`, runs `make doctor`, and runs `make install`. That copies:

- skill `skills/ginflow` to `~/.agents/skills/ginflow` (shared)
- plugins `ginflow-gate` and `ginflow-trace` to `~/.hermes/profiles/<profile>/plugins/` for each profile

Profile config, identity, secrets, memories, and sessions are never touched.

| Variable | Default | Purpose |
|---|---|---|
| `PROFILES` | every profile with `config.yaml` | Space-separated profile names, e.g. `PROFILES="a b"` |
| `GINFLOW_DIR` | `~/.ginflow` | Clone location |
| `GINFLOW_REF` | `main` | Branch, tag, or commit |

An existing clone with local changes aborts the install untouched.

## 3. Enable the plugin

```bash
hermes plugins enable ginflow-gate
hermes plugins list
```

Restart active Hermes sessions afterward.

Optional: `scripts/setup.sh --apply <profile>` also adds the CodeGraph MCP server and common toolsets to profile config. It needs PyYAML (`make doctor-deps`) and edits the profile's `config.yaml` (backup kept as `config.yaml.bak.integration`).

## 4. Verify

```bash
cd ~/.ginflow
make verify
```

## 5. Prepare a target project

In the target repository, not this one:

```bash
cp ~/.ginflow/templates/hermes.md .hermes.md
echo .hermes.md >> .git/info/exclude
```

Edit `.hermes.md` and set the project's canonical verification command. Never commit it and never copy these rules into `AGENTS.md` or `CLAUDE.md`. See [project-config.md](project-config.md) for `.ginflow.yaml`.

## 6. First task

1. Open Hermes in the target repository.
2. Run `/ginflow`. On first load it asks which Kanban board to use and writes `.ginflow.yaml`.
3. State your goal. Ginflow runs Discovery, then Shaping, and asks you to approve one Execution Package.
4. Execution runs the resulting Kanban cards. Workers finish with `kanban_request_review`; `ginflow-gate` checks evidence at that call and at `kanban_complete`.

Lifecycle detail: [ginflow-flow.md](../architecture/ginflow-flow.md).

## Update

```bash
curl -fsSL https://raw.githubusercontent.com/ginn1111/ginflow/main/install.sh | bash
```

`hermes profile update <profile>` may replace integration links; rerun the installer afterward.

## Uninstall

```bash
make -C ~/.ginflow uninstall
```

Restores installer backups. Refuses to delete paths changed after install; resolve the reported conflicts, then rerun.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no Hermes profiles found` | Install a profile (step 1). |
| `has local changes` | Commit or stash changes in `~/.ginflow`, or set `GINFLOW_DIR`. |
| `backup already exists` | Run `make -C ~/.ginflow uninstall`, or resolve the named `.bak.ginflow-install` path. |
| `/ginflow` not found | Confirm `~/.agents/skills/ginflow/SKILL.md` exists; restart Hermes. |
| CodeGraph warning from `make doctor` | Ignore unless you want workspace navigation. |
