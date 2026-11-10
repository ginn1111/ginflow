# Ginflow artifact repository

Run commands from the repository root.

## Prerequisites

- Python 3
- POSIX shell
- Make
- Git

Optional:

- CodeGraph for workspace navigation and health reporting
- Hermes Agent if you want to consume the optional `skills/ginflow` skill or `plugins/ginflow-gate` adapter

The repository does not require a Hermes installation, Hermes profile, profile directory, profile manifest, or profile configuration.

## Validate the repository

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
# or: pip install hermes-agent
hermes --version
hermes doctor
```

Authoritative docs: <https://hermes-agent.nousresearch.com/docs/user-guide/profiles>

## 2. Install profile distributions natively

Profile package and identity stay in their original distribution repositories, not this setup repo.

```bash
hermes profile install github.com/owner/profile --alias
hermes profile list
hermes profile info <profile>
```

Local distribution directory also works:

```bash
hermes profile install /absolute/path/to/profile-distribution
```

Distribution root must contain `distribution.yaml`. Hermes previews manifest before installation unless `--yes` is supplied.

## 3. Plug setup integrations

```bash
make doctor
make community-update                         # optional
make install PROFILES="profile-a"
make verify PROFILES="profile-a"
```

### Install Ginflow skill and plugins

Use the dedicated installer. The skill is shared; the plugin goes into Hermes profiles:

```bash
make install                              # plugin into every Hermes profile
make install PROFILES="profile-a profile-b"   # plugin into selected profiles only
```

This copies `skills/ginflow`, including `lib/harness_core.py`, once to `~/.agents/skills/ginflow`, and copies `plugins/ginflow-gate` and `plugins/ginflow-trace` into `~/.hermes/profiles/<profile>/plugins/` for every profile that has a `config.yaml` (or only the profiles named in `PROFILES`). The gate loads every core module from `skills/ginflow/lib/` (repo checkout first, then `~/.agents/skills/ginflow/lib/`) via `plugins/ginflow-gate/skill_lib.py`. It does not modify profile config. Installer ownership is recorded in setup-repo-root `.ginflow-install.json`, which is gitignored.

Remove only installer-owned files with:

```bash
make uninstall
```

Uninstall restores installer backups and refuses to delete paths changed after installation. Resolve reported conflicts manually, then rerun `make uninstall`.

`scripts/setup.sh --apply <profile>` edits native profile config only and does not link the skill or plugins; run `make install` for those. Setup requires existing profiles. It adds only:

- setup-repo and optional community skill directories
- `ginflow-gate` plugin enablement (files come from `make install`)
- CodeGraph MCP and its toolset
- common CLI toolsets needed by harness/workflow

Setup preserves profile-owned `SOUL.md`, `distribution.yaml`, provider/model identity, secrets, memories, sessions, auth, cron, and release metadata.

Setup resolves profiles from `$HERMES_PROFILES_DIR` when set. Otherwise it uses `$HERMES_REAL_HOME/.hermes/profiles`, falling back to real user home. This avoids profile-session `$HOME` paths when wiring another profile.

Restart active sessions after apply.

## Update profiles

Use Hermes-native update against source recorded in profile manifest:

```bash
hermes profile update <profile>
```

Default update replaces distribution-owned `SOUL.md`, `skills/`, `cron/`, and `mcp.json`, while preserving local user data and `config.yaml` overrides. To intentionally accept distribution config changes:

```bash
hermes profile update <profile> --force-config
```

Profile update may replace integration links or config entries. Reapply kit:

```bash
make install PROFILES="<profile>"
make verify PROFILES="<profile>"
```

## Package profiles using Hermes-native format

Do this in profile distribution repo or with Hermes export. Do not copy package data into setup repo.

### Git distribution

Profile distribution root includes at minimum:

```text
distribution.yaml
SOUL.md
config.yaml          # optional native defaults
skills/              # optional distribution-owned skills
cron/                # optional distribution-owned jobs
mcp.json             # optional distribution-owned MCPs
```

Keep secrets and runtime data out: `.env`, auth, memories, sessions, state DB, logs, caches.

Install directly from Git:

```bash
hermes profile install github.com/owner/profile
```

### Archive distribution

```bash
hermes profile export <profile> -o <profile>.tar.gz
hermes profile import <profile>.tar.gz
```

## Verify and test

```bash
make test
make verify
```

`make test` runs lint plus core, lifecycle, plugin, and installer checks. `make verify` runs the Ginflow harness without requiring a target workspace or Hermes profile.

## Consume the artifacts

Use the repository directories directly or copy the required artifacts into another project or runtime:

- `skills/ginflow/lib/` — reusable routing and validation primitives
- `templates/` — target-project starter context and artifact templates
- `skills/ginflow/` — optional Hermes-compatible workflow skill
- `plugins/ginflow-gate/` — optional Hermes-compatible completion gate
- `skills/ginflow/scripts/` — portable validation and test helpers

For a target project, copy `templates/hermes.md` to `<target>/.hermes.md` and add `.hermes.md` to `<target>/.git/info/exclude` (never commit it, never write ginflow rules into `AGENTS.md`/`CLAUDE.md`, which teammates share). Adapt its local commands, boundaries, and canonical verification path.

## Optional Hermes integration

Hermes integration is deliberately outside this repository's runtime boundary. Install or configure Hermes using the official Hermes documentation, then consume the optional skill and plugin according to that runtime's integration mechanism.

This repository does not:

- discover or select Hermes profiles;
- mutate profile configuration;
- install or uninstall profile integrations;
- manage profile identity, secrets, sessions, memories, cron, or provider settings; or
- require Hermes to run its core validation suite.

## Target-project workflow

Do not implement product work in this repository. Agents should use the Ginflow workflow against the real target repository, with the target project's local rules and canonical verification command.

The target project owns:

- product code and tests;
- local `.hermes.md` rules (untracked) and any team `AGENTS.md`;
- Kanban-linked Spec, Plan, ADR, and Handoff artifacts; and
- product verification and delivery decisions.

The Ginflow skill and plugin remain optional adapters. They do not replace the target project's own toolchain or verification.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make` is missing | Install Make from your operating system toolchain |
| Python dependency error | Use Python 3 and rerun `make lint` |
| CodeGraph warning | Install and initialize CodeGraph only if workspace navigation is needed |
| Hermes integration needed | Configure Hermes separately, then consume the optional skill/plugin artifacts |
| Target verification is unknown | Add the canonical command to the target project's local rules |
