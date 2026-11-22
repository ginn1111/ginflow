---
status: proposed
scope: Inbox v1 documentation and live check
owner: ginb
---
# INBOX-docs — Document and validate v1

Source: https://github.com/ginn1111/ginflow/issues/48. Depends on INBOX-2a and INBOX-2b.

Update Ginflow references to describe card-event hooks, Inbox → configured push → card-comment fallback, reply-to-card-comment sync, and the answered-question unblock rule. Say explicitly that silence never advances a card and that the Inbox is not an approval authority in v1. Update `docs/architecture/integration-status.md` with wired hooks, sync command, and cron job. Extend `docs/guides/inbox.md` with enable/init/block/answer/comment/unblock walkthrough and troubleshooting for Inbox down, paused job, or missing `plannotator`.

Acceptance: docs match actual command/config/job behavior; a scratch board with enabled Inbox shows one blocked card answered, commented, and unblocked within one sync, with manual evidence on the card. Run `make lint && make test`. Do not claim a live check based on fakes.
