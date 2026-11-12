---
status: completed
scope: Makefile (lint target)
owner: cindy
---
# LINTFIX-1 — make lint compiles scripts/*.py under POSIX sh

## Problem

`Makefile` lint used `compgen -G 'scripts/*.py'`. Make runs recipes with `/bin/sh` (dash on Ubuntu CI), which has no `compgen`: CI logs `compgen: not found`, the `if` is false, and `py_compile scripts/*.py` never runs.

## Behavior

`set -- scripts/*.py; if [ -e "$1" ]; then python3 -m py_compile "$@"; fi` — POSIX glob test; unmatched glob stays literal and fails `-e`.

## Acceptance criteria

- [x] `make SHELL=/bin/dash lint`: no `compgen: not found`, `lint ok`
- [x] Syntax-broken `scripts/*.py` fails lint (rc=2); valid one passes
- [x] `make lint test` passes; CI green on the PR

## Notes

No `scripts/*.py` exist today, so nothing was missed yet; guard matters once one lands.
