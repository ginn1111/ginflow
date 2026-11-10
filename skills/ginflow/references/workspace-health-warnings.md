# Workspace health warnings

Review target workspace immediately before completion. Report findings under `Workspace warnings` on Kanban card and in completion report.

## Decision rule

Warnings do not block completion by default. Promote a finding to blocker only when it affects acceptance, canonical verification, security, privacy, data integrity, or restartability.

For each finding, record:
- severity: warning or blocker
- concrete path or code evidence without exposing secret values
- affected completion condition
- smallest next action

Use `Workspace warnings: none` when review finds nothing. Do not invent findings.

## Review areas

- **Missing runtime config contract** — code reads config absent from committed examples or docs. Keep as warning when safe defaults preserve startup and acceptance; block when deployment or restart can fail.
- **Secret or privacy exposure** — tracked credential files or credible sensitive data are blockers. Never print values. Require safe removal and authorized rotation or review.
- **Unrelated workspace changes** — preserve and report out-of-scope edits. Keep as warning when card work neither reads nor overwrites them and evidence remains clear.
- **Error suppression anti-pattern** — broad catches, ignored failures, or success state after failed external work. Block when acceptance or data integrity can be false.
- **Manifest/generated drift** — block only when build, runtime, verification, or restartability is affected.
- **Debug residue and unresolved TODOs** — warn unless they affect scoped behavior or completion conditions.

## Route healing requests

When the user asks to fix, heal, or clear workspace warnings, route each finding before changing files:

1. Confirm concrete evidence, affected paths, selected card, and current card status. If no complete card is selected, permit read-only inspection and task shaping only. Do not invent findings or start execution.
2. Classify impact:
   - **Current blocker** — finding affects selected card acceptance, canonical verification, security, privacy, data integrity, or restartability. Keep fix on selected active card, block completion, add regression coverage when behavior changed, then rerun canonical verification and workspace review. Do not create a follow-up merely to move a blocker away.
   - **Optional in-scope warning** — finding is bounded to selected card but does not block completion. Preserve completion readiness. If user intent does not say whether to expand current scope, ask whether to fix now on selected card or create a linked follow-up. If approved now, change only warning source and rerun relevant verification.
   - **Unrelated warning** — finding is outside selected card scope. Preserve unrelated edits and keep selected card unblocked when evidence remains clear. Shape a separate linked follow-up and require that complete card to be selected before implementation or dispatch.
   - **Completed-card warning** — treat repair as new intent. Create and select a linked follow-up; leave completed card and `artifact_baseline` unchanged. Reopen completed card only when finding changes its completed scope or acceptance.
3. Record route and next action on selected card. Never silently expand scope, modify unrelated work, or advance a completed baseline.

For broad requests such as “fix all workspace warnings,” group findings into one card only when they share workspace, objective, acceptance, and verification path. Otherwise split by independent scope or risk.

Do not copy this policy into target repo. Do not add scanner or policy files there. Use project-native tools and direct inspection; suggest follow-up work only when worthwhile.
