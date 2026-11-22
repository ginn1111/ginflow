---
status: proposed
scope: Inbox v1 card-event delivery
owner: ginb
---
# Plan — INBOX-2a

Source: https://github.com/ginn1111/ginflow/issues/46. Start after INBOX-1a is done and review the landed client contract.

1. Inspect `plugins/ginflow-gate/__init__.py`, `block_routing.py`, existing hook tests, and Inbox client. Write failing tests for blocked/review/completed events, stable envelope and idempotency key.
2. Add `plugins/ginflow-gate/inbox.py` and register the three hooks. Verify bounded quoted text, disabled behavior, and no file attachments with focused tests.
3. Persist per-card thread/message/question/cursor state under `.ginflow/inbox-state.json` with file locking. Test simultaneous distinct cards.
4. Implement Inbox → notify target → card comment fallback without raising or changing transition results. Test exit 1, timeout, and missing binary; rerun existing block-routing tests.
5. Run `make lint && make test`, record exact results and changed files on the card before review.
