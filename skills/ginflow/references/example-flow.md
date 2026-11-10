# Example: one card, start to finish

Project `app`, work key `APP-9`.

1. Startup: `.ginflow.yaml` exists, board `app`. Read `.hermes.md`. No card selected, so route to Discovery/Shaping.
2. Shaping: draft `docs/specs/APP-9.md` and `docs/plans/APP-9.md` (frontmatter `status: draft`).
3. Create card blocked, assigned to current profile, links future artifacts:

```text
Objective: Add CSV export to report page
Scope:
- src/reports/
Acceptance:
- Export button downloads valid CSV
Links:
- docs/specs/APP-9.md
- docs/plans/APP-9.md
```

   Hermes returns `t_ab12`. Use `t_ab12` for Kanban tools, `APP-9` in titles and paths.
4. Commit artifacts, run baseline verification, run harness candidate check, unblock.
5. Work inside scope. Run `make test` from target repo. Quote command and exact result on card.
6. Set specs/plans `status: completed`, commit.
7. `kanban_request_review(task_id='t_ab12', summary='CSV export done', metadata={'verification_result': {'commit': 'abc123', 'command': 'make test', 'result': 'passed'}, 'artifact_baseline': {'commit': 'abc123', 'paths': ['docs/specs/APP-9.md', 'docs/plans/APP-9.md']}})`
8. Reviewer validates, calls `kanban_complete` with same metadata. Gate passes.
