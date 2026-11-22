---
status: approved
scope: Ginflow actionable Kanban block notifications and delivery retry
owner: ginflow setup repo
---

# Design — Alert when a card needs human action

## Goal and boundary

Gin should learn promptly when an explicit Kanban block prevents unattended progress. This version handles explicit `kanban_block` events only; it does not infer stalled `running` cards. An ordinary dependency wait and the first recoverable transient failure do not send an alert. Notification is independent of `ginflow.trace` and `GINFLOW_LOG`; trace remains optional diagnostics.

## Decisions and routes

The `kanban_task_blocked` observer evaluates the current card and recovery decision. `needs_input` and `capability` notify immediately. A first `transient` block attempts existing auto-recovery without notification; no reviewer, failed recovery, or exhausted retry (`triage`) escalates to a human. If reassignment or unblock fails, the card remains blocked and requires notification rather than merely a comment. Do not notify for dependency waits. Keep the block transition independent of delivery failures.

One alert corresponds to a card and a required human action. Persist it before trying to send, then attempt delivery immediately. The default destination is `ginflow.notify.target` from `.ginflow.yaml`. If missing or delivery fails, try `hermes send --to telegram` to Hermes's configured Telegram home channel. No Telegram credential or duplicate destination is stored in Ginflow configuration. A card-specific subscription may remain a supported route only if its precedence is made explicit; it must not replace the Telegram fallback. A failed send leaves the alert pending and records a diagnostic card comment; a comment does not count as notification.

## Message

Use one or two lines: severity, card ID or link when available, short safe error, whether the agent can fix it (`Yes`, `No`, or `Unknown`), and a concrete human action. Do not guess fixability or fabricate an action; if the reason lacks one, say that input is needed to decide the next step. Keep the message bounded and sanitize control characters and sensitive data. Example:

> [HIGH] APP-9 blocked — deployment credentials rejected. Agent can fix: No. Card: <link>
> Your action: Update the credential, then unblock the card.

Severity is `HIGH` for human-action blocks; an exhausted recovery with no clear action can use `MEDIUM` and say what information is needed. Do not include raw command output or secrets.

## Durable retry and lifecycle

Maintain a per-board durable alert outbox with atomic writes and concurrency protection. A stable key for card plus required action suppresses duplicate hook invocations. Store only minimal state: card ID, action fingerprint, bounded message, state (`pending`, `delivered`, `cancelled`), attempt count, next attempt time, and timestamps. No credentials. If the action changes, it becomes a new alert; do not flood on repeated events with the same action.

`ginflow init` ensures exactly one board-scoped Hermes cron job running a no-agent retry command every minute; re-running init does not create duplicates. Cron is a health-checked safety net, not the primary notifier and does not consume LLM tokens. Each tick checks due pending alerts, re-reads card state, cancels alerts for cards no longer blocked or in triage, and retries delivery only when due. Use backoff after failed attempts: 1, 5, then 15 minutes (15-minute cap), continuing until delivery succeeds or the card is unblocked. A successful `hermes send` marks the alert delivered and stops retries. The job remains while the board is active and is removed with its owning integration on uninstall. A stopped or missing scheduler is a notification-health failure, never evidence of delivery.

Use a lock or claim to prevent the hook and cron from sending the same alert concurrently. If a send succeeds but its confirmation is lost, an occasional duplicate is preferable to a silently missed alert. Do not resend an already confirmed delivery. Do not hold a board-state lock across the network send; use a bounded in-flight lease or equivalent to recover after process death. Retry command output should be quiet when nothing happened.

## Verification

Test immediate notification with trace off; `notify.target` success; missing/failed target falling back to Hermes Telegram home; both routes failing and later recovering; retry after worker restart; duplicate hook suppression; concurrent hook/tick claim; new action on the same card; unblocking before delivery; first transient recovery versus failed recovery and triage; dependency wait; absent credentials/destination; and scheduler init idempotence. Assert exact short message fields and no secret leakage. Test delivery failure without changing Kanban transition results. For this design review, run `make lint` only. Implementation verification remains subject to the repository's required checks.

## Deferred

Stalled-running-card detection, digests, multi-platform broadcasts, and notification via Inbox are separate work. This design does not require a product-repo workspace or a selected target-project card until implementation is assigned.
