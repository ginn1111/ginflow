---
status: draft
scope: skills/ginflow/lib/decision.py; skills/ginflow/lib/project_config.py
owner: ginb
---

# Plan — CLEANUP-1.7: Remove never-called duplicate helpers

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets may have already changed nearby code — re-read before editing. RED test first, then change, then `make lint test`.

## Step 1: Delete never-called duplicates (gated on Gin's option; default option 1)

- `skills/ginflow/lib/decision.py`: delete `_notification_context` (exact duplicate of `_decision_context` logic, zero callers).
- `skills/ginflow/lib/project_config.py`: delete `context_mismatch` and its `__all__` entry (zero callers, zero tests, not documented).
- Verify `grep -rn "_notification_context\|context_mismatch" --include=*.py .` → no output; `make lint test` exit 0.
- Commit `chore(ginflow): remove never-called duplicate helpers`.

Skip if Gin picks "report only". If Gin picks "delete everything unwired", stop and re-plan (large; touches SKILL.md Decision docs).