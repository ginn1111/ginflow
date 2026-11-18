---
status: in_progress
scope: macOS installer test path portability
owner: ginb
---
# GINFLOW-INSTALL-2 — Fix macOS installer test path assertion

Replacement for [GINFLOW-INSTALL-1](GINFLOW-INSTALL-1.md), whose dispatcher runs timed out because the card was created with a zero-second runtime limit. The original diagnosis and acceptance remain valid.

The installer resolves profile paths to physical paths. On macOS, `mktemp -d` may return `/var/...` while the same directory resolves to `/private/var/...`. The test must compare canonical paths so its per-profile `ginflow init --project` assertions verify behavior rather than the spelling of a symlinked temp root.

Scope: `scripts/test-install.sh` only. Preserve the installer implementation and all existing assertions, including one init call per profile with the expected project and board arguments.

Acceptance: reproduce the current line-90 failure, then pass `bash scripts/test-install.sh` and canonical `make lint && make test` on macOS. Do not alter Inbox implementation or unrelated worktree changes.
