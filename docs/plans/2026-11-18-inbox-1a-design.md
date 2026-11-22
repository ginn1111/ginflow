---
status: proposed
scope: INBOX-1a design for Ginflow setup integration
owner: cindy
---

# INBOX-1a — Inbox configuration and client design

Issue: https://github.com/ginn1111/ginflow/issues/45

## Boundary

This change supplies the optional configuration and transport foundation for the Inbox v1 flow. Card-event delivery and reply sync belong to #46 and #47. The Inbox is for notifications and blocking questions, not an approval authority; Kanban remains the source of truth. No Pi or Telegram migration is included.

## Configuration

Extend `skills/ginflow/lib/project_config.py` with `inbox_error(context)` beside `notify_error()`, invoked by `context_error()`. Accept only `ginflow.inbox.enabled` (boolean) and `ginflow.inbox.data_dir` (absolute path when present). Reject unknown fields, malformed mappings, wrong types, and relative paths. A missing block is disabled. `configured_inbox(workspace)` returns validated settings for an enabled block and `None` when absent or disabled; callers must not treat invalid config as a valid disabled state.

## Transport

Add `skills/ginflow/lib/inbox_client.py` as a small subprocess boundary with `send_message`, `read_thread`, and `resolve_message`. Use `plannotator inbox call --session ginflow-<board> <action> <json>` and set `PLANNOTATOR_DATA_DIR` when a shared `data_dir` is configured. Parse stdout JSON. Return a consistent structured result or an error carrying a kind and diagnostic; classify exit 1 as unavailable/refused, exit 2 as bad usage, and distinguish timeout (10 seconds), invalid JSON, and other process failures. Expected operational failures do not raise into callers, so the later integrations can choose their fallback. Do not make this module responsible for Kanban state or policy.

## Doctor and guide

Add a read-only `ginflow doctor` command to `skills/ginflow/scripts/ginflow.py`; the existing `ginflow init` behavior remains unchanged. When the Inbox block exists, doctor validates it, checks the `plannotator` binary, and runs `plannotator inbox status --json` to report reachability. Without the block, the Inbox adds no doctor output. Doctor makes no config or installation changes.

Add `docs/guides/inbox.md` for opt-in configuration, shared `data_dir`, manual installation, and Linux/remote access. Explain that the service binds to `127.0.0.1` and remote use requires a secure tunnel, not public exposure. Document only the #45 behavior until later issues land.

## Verification

Test config validation for unknown fields, non-boolean `enabled`, relative `data_dir`, and missing/disabled blocks. Put a fake `plannotator` first on `PATH` to assert exact argv, environment, JSON parsing, exit codes 1 and 2, timeout, and malformed output. Exercise doctor with absent config, missing binary, and unreachable service. Confirm the disabled path leaves Ginflow unchanged. Run `make lint && make test` before requesting review.

## Execution gate

This is a design artifact, not implementation. Before code changes, select a Kanban card with the objective, scope, acceptance, workspace, status, assignee, and links required by Ginflow; use an isolated workspace and record verification evidence on that card.
