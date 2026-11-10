# Optional session handoff export

Command: `/hermes handoff export`. Only when the user wants a portable Markdown snapshot. Never replaces Kanban.

1. Ask the user which Kanban card. Never auto-select.
2. Read selected card and only cards it links. No recursion.
3. Read spec/plan links on the card.
4. In target repo read `git config user.name` and `git config user.email`.
5. Render `templates/session-handoff.md` preview.
6. Placeholders: `Not recorded on Kanban card.`, `Not linked from selected Kanban card.`, `Not configured in Git.`
7. Ask the user to approve content and output path (project convention).
8. Write only after approval.

Never infer missing facts from status, chat, OS identity, commit history, or unrelated cards. Never mutate card status, assignee, links, or content.
