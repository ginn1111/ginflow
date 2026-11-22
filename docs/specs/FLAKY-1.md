---
status: completed
card: FLAKY-1
assignee: ginb
blocked_by: []
scope: plugins/ginflow-gate/test_ginflow_gate.py, plugins/ginflow-trace/test_ginflow_trace_integration.py
owner: ginb
---

# Spec — FLAKY-1: Live-hermes tests clean up their temp home reliably

Content rules: `references/artifact-content-guide.md` in `ginflow`.

## Problem

Three tests run the real `hermes` CLI against a throwaway Hermes home made with `tempfile.TemporaryDirectory`:

- `plugins/ginflow-gate/test_ginflow_gate.py` — `test_live_tmp_project_card` (prefix `ginflow-gate-home-`, line ~216) and the TMP-2 live test (line ~255)
- `plugins/ginflow-trace/test_ginflow_trace_integration.py` — `test_full_kanban_lifecycle_traced` (prefix `ginflow-trace-home-`, line ~59)

The test bodies pass, but removal of the temp home sometimes raises:

```
OSError: [Errno 39] Directory not empty: '.../ginflow-gate-home-XXXX/cache'
```

Seen on 2026-11-22: gate test failed 2 of 3 runs (`test_live_tmp_project_card`); trace test failed once in a full `make lint test` (`trace-test`). Something keeps writing into `<home>/.../cache` after the `hermes` subprocess returns (suspect: a detached/background child or a cache writer outliving the CLI call). Failure is more likely when several suites run at once.

## Root cause (B1, resolved)

The writer is the detached `python -I -c ... runpy.run_module('hermes_cli.default_plugins')` child started by `default_plugins.spawn_install()` from the boot step `step_install_default_plugins`. Its failure path calls `memory_provider_migration._note_failure`, which recreates `<home>/cache/left-core-default-plugins.failed` after the CLI returned (even after a successful rmtree). Evidence: leftover homes held only that file; `pgrep -af default_plugins` showed live children after a run. Fix: `HERMES_DISABLE_LAZY_INSTALLS=1` was tried and rejected (fresh-home `hermes kanban init` exits 1: no dependency environment). Instead `_temp_hermes_home` waits (up to 120 s) for any process whose `/proc/<pid>/environ` points into the temp home to exit, then rmtrees; bounded-retry rmtree stays as a backstop.

## Desired behavior

- B1. Find and record the late writer (process name and how it was identified).
- B2. Each of the three tests removes its temp Hermes home without raising on this race: either the writer is stopped/awaited before removal, or removal retries a bounded number of times (short sleeps, total ≤ ~5 s) before failing.
- B3. A real assertion failure inside the test body is still reported as that failure, never masked by cleanup.
- B4. After a passing run, nothing matching `ginflow-*-home-*` is left under `$TMPDIR`.

## Constraints

- Test code only; no changes to plugin runtime code or Hermes.
- Do not use `ignore_cleanup_errors=True` alone (it leaves junk behind and violates B4).
- Shared helper only if both plugin test files can already import a common module; otherwise a small local helper in each.

## Acceptance criteria

- [ ] Root cause (B1) noted on the card with evidence
- [ ] Cleanup per B2 in all three tests; B3 holds
- [ ] No `ginflow-*-home-*` left in `$TMPDIR` after a passing run
- [ ] `python3 plugins/ginflow-gate/test_ginflow_gate.py` and `make trace-test` pass 5 runs in a row
- [ ] `make lint test` passes

## Edge cases

- `hermes` not on PATH: tests already skip/handle this; keep that behavior.
- Writer still running past the retry budget: fail with a clear message naming the leftover path.
