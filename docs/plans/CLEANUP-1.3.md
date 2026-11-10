---
status: completed
scope: plugins/ginflow-gate/routing.py; plugins/ginflow-gate/test_ginflow_gate.py; skills/ginflow/lib/routing.py
owner: ginb
---

# Plan — CLEANUP-1.3: Routing context without legacy v1 guidance

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets are merged into `main` before this card starts and may have changed nearby code — re-read before editing. Ignore any umbrella-plan step about creating cards or closing the umbrella card. RED test first, then change, then `make lint test`.

## Step 1: Remove obsolete route-specific handling

Update `plugins/ginflow-gate/routing.py` so the no-card route provides only four-phase Initiative guidance: Discovery → Shaping → Execution → Decision. Remove metadata-dependent route guidance and related environment-based output customization. Remove unused compatibility aliases from core routing.

In `plugins/ginflow-gate/test_ginflow_gate.py`, assert no legacy wording appears in no-card context. Remove tests specific to retired detector and formatter; verify selected cards with old version metadata receive identical context to ordinary cards.

Verify with `make lint test`; inspect changed files and confirm removed symbols and environment variables have no remaining code or documentation references.