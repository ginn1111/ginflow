# Canonical project context

The first `/ginflow` skill load initializes `.ginflow.yaml` in the current project root:

First-load initialization is agent-procedural: `/ginflow` invokes the initializer and
collects the board choice. Runtime validation and persistence enforce the contract,
but no runtime hook or CLI silently initializes a project.

```yaml
version: 1
ginflow:
  board: <Kanban board slug>
  workspace: /absolute/path/to/project
  worker:
    profile: <worker Hermes profile>
    provider: <provider name>
    model: <model name>
  trace: false # optional; enables ginflow-trace function logging for this project
```

The resolved workspace is the target directory passed to verification. Board precedence is:

1. explicit runtime/API override;
2. `HERMES_KANBAN_BOARD`;
3. `ginflow.board` in `.ginflow.yaml`;
4. Hermes's active board.

The optional `worker` block stores repository-local dispatch defaults used when
Ginflow creates a governed Kanban card: `profile` maps to `assignee`, and
`provider`/`model` are passed as explicit overrides when present. Only `board`
and `workspace` are required; the worker block is recommended, not required.
When a field is missing, `/ginflow` shows the resolved fallback and asks whether
to configure the complete block before creating the card. Entered defaults are
validated, then atomically merged into the existing config, preserving board,
workspace, version, and unrelated keys. Skipping setup leaves the config
unchanged and uses the current Hermes profile, omitting provider/model
overrides so the worker profile's own configuration applies.

Worker dispatch resolution per field is:

1. explicit per-card user override;
2. `ginflow.worker.<field>` in `.ginflow.yaml`;
3. runtime fallback (current profile; provider/model unset).

A malformed `worker` block (wrong type, empty string, or unknown field) blocks
card creation but does not break read-only board/workspace routing.
`ginflow.trace` is an optional boolean. When `true`, the opt-in `ginflow-trace`
plugin records decorated plugin function calls (gate business functions and hook
entry points) under the configured working repo: `<ginflow.workspace>/.ginflow/logs/`
(errors under `<ginflow.workspace>/.ginflow/errors/`). Missing, malformed, relative,
or nonexistent workspace values disable that write without falling back to the setup repo. An
explicit `GINFLOW_LOG` environment value overrides the flag for a single
process: `GINFLOW_LOG=1` forces tracing on, any other value forces it off, and
an unset variable falls back to `ginflow.trace`. Defaults to off when omitted.

A valid existing config is used by Kanban reads when no override is supplied and is not overwritten during ordinary skill loading. If the file is missing, `/ginflow` asks whether to use the current/default board or create a new board. New-board selection requires a non-empty name and successful native board creation before persistence. Malformed, incomplete, or workspace-mismatched config fails closed and must be repaired or explicitly resolved by the user; it never causes a silent workspace or board switch. Verification reads this file but does not initialize or rewrite it.

Routing distinguishes a missing config from an invalid config. Both are mutation
blockers: missing context directs the agent to run `/ginflow`, while invalid context
directs it to repair `.ginflow.yaml`. A valid context with no cards for its workspace
is reported as a normal no-card work-shaping route.
