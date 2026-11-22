---
status: proposed
scope: Inbox reply sync and scheduled reconciliation
owner: ginb
---
# INBOX-2b — Reply sync and cron

Source: https://github.com/ginn1111/ginflow/issues/47. Depends on INBOX-1a and INBOX-2a state format.

`ginflow inbox sync --board <board>` reads project config and exits silently with 0 when disabled. With a file lock, it reads tracked cards after each cursor, posts only new human replies to the matching card as `[inbox]` comments, and advances the cursor after each card. A second concurrent run exits. Only unblock if the card is still blocked, its saved blocking question reads `sent`, and the answer came from that card's thread. Plain replies are comments only. Resolve and drop done/archived cards; warn and drop missing threads without unblocking. Inbox outages return nonzero with one line and preserve the cursor. Print only meaningful activity.

`ginflow init` ensures exactly one `ginflow-inbox-sync:<board>` script/no-agent cron job every five minutes; resume when enabled, pause when disabled. Preserve an existing matching job and fail on command mismatch. `ginflow inbox sync --reconcile` changes only pause/resume state. Doctor reports missing or mismatched job state.

Acceptance: fake Inbox/Kanban tests cover once-only comments, answer-gated unblock, cross-card isolation, cleanup, disabled/outage/lock behavior, and cron idempotence/mismatch. Verify actual Hermes cron script/no-agent behavior and empty-output delivery before coding. Run `make lint && make test`. Approval gates are excluded.
