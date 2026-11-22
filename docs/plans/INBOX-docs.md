---
status: proposed
scope: Inbox v1 documentation and live check
owner: ginb
---
# Plan — INBOX-docs

Source: https://github.com/ginn1111/ginflow/issues/48. Start after INBOX-2a and INBOX-2b land.

1. Inspect landed hook, client, sync, and cron code plus existing references. Compare actual config/commands with spec; resolve drift before writing.
2. Update `skills/ginflow/` references, `docs/architecture/integration-status.md`, and `docs/guides/inbox.md` with the observed v1 flow, fallback, limits, and troubleshooting. Check links and terminology against code.
3. Use an isolated scratch board and enabled Inbox to block a card and answer its own question. Run one sync; record command/output evidence of exactly one comment and unblock on the card. Report an honest blocker if live transport is unavailable.
4. Run `make lint && make test`; record exact results, changed files, and live-check evidence before review.
