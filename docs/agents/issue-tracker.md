# Issue tracker: GitHub

Issues and specs for this repository live in GitHub Issues at `ginn1111/ginflow`. Use `gh` for all operations.

## Conventions

- Create: `gh issue create --title "..." --body-file <file>`
- Read: `gh issue view <number> --json number,title,body,labels,comments`
- List: `gh issue list --state open --json number,title,body,labels,comments`
- Comment: `gh issue comment <number> --body "..."`
- Label: `gh issue edit <number> --add-label "..."`
- Close: `gh issue close <number> --comment "..."`
- Infer repository from Git remote while inside this clone.
- Pull requests are not a triage request surface.

## Publishing

When a skill says to publish to the issue tracker, create a GitHub issue.

When a skill says to fetch a ticket, read that GitHub issue and its labels and comments.
