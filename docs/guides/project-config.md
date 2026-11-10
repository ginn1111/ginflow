# Project context and completion evidence

Each target project keeps optional Ginflow context in `.ginflow.yaml` at its repository root. The `/ginflow` skill creates it on first load; do not hand-write it unless repairing.

```yaml
version: 1
ginflow:
  board: <Kanban board slug>
  workspace: /absolute/path/to/project
  worker:
    profile: <worker Hermes profile>
    provider: <provider name>
    model: <model name>
  reviewer:
    profile: <installed Hermes profile>   # optional
  trace: false
```

Optional `ginflow.reviewer.profile` must name an installed Hermes profile; unknown or malformed values fail closed before governed card creation. When valid, `ginflow-gate` injects it as the `reviewer` of native `kanban_request_review` (a `modify` directive) unless the caller passes one; Hermes has no default-reviewer setting. When absent, Hermes keeps the current assignee.

`board` and `workspace` are required. Board resolution uses explicit runtime override, `HERMES_KANBAN_BOARD`, this file, then Hermes active board. Missing context sends work to `/ginflow`; malformed, incomplete, or workspace-mismatched context fails closed. Ordinary verification reads config but does not initialize or rewrite it. The optional `worker` block supplies governed-card dispatch defaults; explicit card values win.

Set `ginflow.trace: true` to enable optional `ginflow-trace` logging under `<workspace>/.ginflow/logs/` (errors under `.ginflow/errors/`). `GINFLOW_LOG=1` enables tracing for one process; any other set value disables it. Trace defaults off and never falls back to setup-repo paths.

## Completion evidence

Evidence stays split:

- **Project verification:** the target repo's exact canonical command, such as `make verify` or `./verify.sh`, run from target root. Proves product behavior and blocks completion when unavailable or failing.
- **Ginflow harness:** external setup/deployed-skill check against target and selected card. Validates card fields, workspace, acceptance, completion evidence, linked paths, `artifact_baseline`, and linked-artifact drift. Reported separately; harness unavailability does not replace project verification.
- **Profile installation:** setup-repo `make verify`, when checking installed profile wiring.

For completed cards, baseline metadata records one Git commit plus exact linked artifact paths. `ginflow-gate` validates this metadata and drift during native `kanban_request_review` and `kanban_complete`; later edits, missing paths, unavailable commits, or path-list mismatch block the affected lifecycle call. It does not silently repair drift or replace target verification.

## Dependencies and limits

Python standard library, POSIX shell, Make, Git, and Draw.io XML. PyYAML is needed only for `scripts/setup.sh --apply` and checked tooling (`make doctor-deps`). No third-party versions are pinned.

External boundaries: Hermes Agent (Kanban, tools, profiles), installed plugin/skill wiring, optional CodeGraph/MCP (advisory, never blocking), and each target project's own toolchain and verification. Ginflow cannot guarantee Hermes internals, target-project behavior, or deployment topology.

Trade-offs: governed work has more ceremony than prompt-and-edit; strict validation rejects missing links, drift, or weak evidence instead of repairing them; setup and product verification are separate results.
