---
status: draft
scope: plugins/ginflow-gate/routing.py; plugins/ginflow-gate/test_ginflow_gate.py; skills/ginflow/lib/routing.py
owner: ginb
---

# Plan — CLEANUP-1.3: Routing context without legacy v1 guidance

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets may have already changed nearby code — re-read before editing. RED test first, then change, then `make lint test`.

## Step 1: B: remove legacy v1 routing guidance

RED — `plugins/ginflow-gate/test_ginflow_gate.py`, in `test_ginflow_skill_active`, replace

```python
            assert "Legacy compatibility guidance is withheld" in result["context"]
```
with
```python
            assert "Legacy" not in result["context"] and "legacy" not in result["context"]
```
Run `python3 plugins/ginflow-gate/test_ginflow_gate.py` — expect `AssertionError` (context still says "Legacy ... withheld").

GREEN — `plugins/ginflow-gate/routing.py`:
- Delete `WORK_MODE_SKILLS`, `WORK_MODES`, `WORK_SIZES`, `_DEFAULT_OUTPUTS`, `format_work_guidance`, `_configured_output_overrides`, `_is_legacy_v1_card` (lines ~65–200 in current file; keep `_parse_skill_list`, `_ginflow_loaded`, `_route`).
- In `_routing_context`, `no_cards_for_workspace` branch becomes exactly:

```python
    if route_name == "no_cards_for_workspace":
        context += (
            "Report workspace to orchestrator; no Kanban card exists for workspace. "
            "For new governed/autonomous work, create or select one initiative record "
            "and follow Discovery → Shaping → Execution → Decision. Discovery resolves "
            "ambiguity; Shaping approves the artifact-first package; do not mutate product "
            "code or dispatch cards before approved Shaping."
        )
```
- Delete the trailing block `if selected_task and _is_legacy_v1_card(selected_task) and route_name in {...}: context += " " + format_work_guidance(...)`.
- `selected_task` is then used only by those removed blocks → delete its assignment too. Check: `grep -n selected_task plugins/ginflow-gate/routing.py` → no output.
- Update `_route` docstring to `"""Inject Hermes cwd into core routing policy."""`.

Tests — `plugins/ginflow-gate/test_ginflow_gate.py`: delete lines `_is_legacy_v1_card = ...`, `format_work_guidance = ...`; delete functions `test_legacy_v1_detection_requires_explicit_card_metadata`, `test_work_guidance_maps_modes_to_bounded_skills`, `test_work_guidance_routes_known_failure_and_unknown_separately`, `test_work_guidance_rejects_risk_and_preserves_canonical_outputs`, `test_explicit_legacy_card_gets_legacy_guidance` and their calls in `__main__` / module level.

`skills/ginflow/lib/routing.py`: delete the `_route` "Contract alias" function (no callers: `grep -rn "_routing_core._route\|routing._route(" --include=*.py .` → none).

Verify:
```bash
python3 plugins/ginflow-gate/test_ginflow_gate.py   # expect "ginflow routing test passed" ... "ginflow gate rejection test passed"
grep -rn "legacy_v1\|format_work_guidance\|GINFLOW_OUTPUT_" --include=*.py --include=*.md . | grep -v '^./.ginflow/'   # expect no output
make lint test; echo exit=$?   # exit=0
git commit -am "refactor(ginflow-gate): remove legacy v1 work-mode routing"
```