# Testcase Matrix

`make test` runs the repository’s deterministic checks in a single canonical
chain. `lifecycle-test` is the canonical ginflow full-flow integration test and
replaces the former separate flow-slice tests; it runs the whole ginflow
lifecycle in one flat sequence with per-step PASS/FAIL reporting.

One-line commands:

```bash
make test          # canonical full scenario (lint + setup + lifecycle + plugin + install)
make lifecycle-test  # ginflow full-flow integration test only
```

| Test case | Related modules / package files | Behavior and flow | Expected output |
|---|---|---|---|
| `lint` | `scripts/*.sh`, `scripts/*.py`, `skills/ginflow/scripts/*.sh`, `skills/ginflow/scripts/*.py` | Runs shell syntax checks, then Python compilation checks. | No syntax errors. `lint ok` |
| `lifecycle-test` | `skills/ginflow/scripts/test-ginflow-lifecycle.py`, `skills/ginflow/lib/harness_core.py`, `skills/ginflow/lib/project_config.py`, `skills/ginflow/scripts/validate-harness.py`, `plugins/ginflow-gate/gate.py` | Canonical ginflow full-flow integration, one flat sequence with per-step PASS/FAIL: (1) init-context — persist/validate `.ginflow.yaml` board + abs workspace; (2) select-card — parse card body + required-field selection; (3) startup-gate — `harness_core.startup_gate` → `ready_to_start`; (4) harness-validate — `validate-harness.py` over the selected card, all subsystems pass; (5) optional-tools — codegraph/mcp health probes (non-blocking warnings); (6) completion-gate — `ginflow-gate.validate_completion` + `pre_tool_call` allow/block; (7) drift-guard — `artifact_gate` baseline, unrelated-change pass, linked-artifact change → blocker. | `RESULT: ALL PASS`, one `PASS`/`FAIL` row per step. |
| `plugin-test` | `plugins/ginflow-gate/routing.py`, `plugins/ginflow-gate/gate.py`, `plugins/ginflow-gate/blocker_reporting.py`, `plugins/ginflow-gate/recovery_policy.py`, `plugins/ginflow-gate/recovery.py`, `plugins/ginflow-trace/` | Routing determinism, completion-gate rejection, blocker reporting, recovery policy, and trace lifecycle. | `ginflow routing test passed`, `ginflow gate rejection test passed`, `blocker reporting contract passed`, `bounded recovery policy passed`, `blocked recovery policy passed`, `PASS: ginflow trace`, `PASS: ginflow trace integration` |
| `install-test` | `scripts/install.sh`, `plugins/ginflow-gate/`, `core/ginflow-core/`, `skills/ginflow/` | Tests installation, config preservation, idempotent reinstall, conflict protection, and clean uninstall. | `install/uninstall tests passed` |

## Result

```text
make test: PASSED
exit code: 0
```

The suite covers the ginflow core library and lifecycle, routing core, the
completion gate, blocker/recovery package, trace, documentation assets, and
setup/install scripts. The former separate flow-slice tests
(`harness-core-test`, `artifact-guidance-test`, `kanban-board-isolation-test`,
`project-config-test`, `kanban-harness-test`, `guidance-test`,
`status-transition-test`, and `test-post-tool-hook.py`) were consolidated into
`lifecycle-test`.
