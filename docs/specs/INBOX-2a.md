---
status: proposed
scope: Inbox v1 card-event delivery
owner: ginb
---
# INBOX-2a — Card events to Inbox

Source: https://github.com/ginn1111/ginflow/issues/46. Depends on INBOX-1a (#45).

The ginflow-gate plugin sends fixed-template messages for blocked cards, review requests, and completions. It does not send claimed events. Each message includes board, card ID, title, assignee/profile, run ID, and event type. Agent-authored content is quoted and the body is capped near 4 KB; no attachments or file contents are sent. Threads use `<board>/<card-id> · <title>`; idempotency keys use `<card>:<run_id>:<event>`.

After a successful send, persist card-to-thread/message/question/cursor state under `.ginflow/inbox-state.json` with locking. On send failure, attempt the existing notify target, then record a card comment. Hooks never raise or change Kanban transitions. When Inbox is absent or disabled, existing routing behavior stays unchanged.

Acceptance: fake-transport tests cover three events, stable dedupe, bounded quoted text, no attachment of secret-like paths, fallback on exit 1/timeout/missing binary, disabled behavior, and independent concurrent card state. Run `make lint && make test`. Approval gates and Pi/Telegram migration are outside v1.
