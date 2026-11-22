---
status: proposed
scope: Inbox reply sync and scheduled reconciliation
owner: ginb
---
# Plan — INBOX-2b

Source: https://github.com/ginn1111/ginflow/issues/47. Start after INBOX-2a; inspect its landed state format.

1. Confirm Hermes cron script/no-agent invocation, script location, and empty-output behavior. Record findings on the card before implementation.
2. Inspect client, state schema, and CLI. Write failing fake Inbox/Kanban tests for per-card replies, cursor replay, answer-gated unblock, and cross-card isolation.
3. Add locked `ginflow inbox sync --board` logic. Test done/missing threads, disabled and outage paths, and concurrent invocation.
4. Add idempotent cron reconciliation to `ginflow init`, `ginflow inbox sync --reconcile`, and doctor. Test enabled/disabled/repeated init and command mismatch in a temporary Hermes home.
5. Run `make lint && make test`; record exact evidence, changed files, and risks on the card before review.
