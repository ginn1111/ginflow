---
status: draft
scope: skills/ginflow/lib/execution_package.py, card_creation.py, execution_batch.py, provider_document.py and their tests; plugins/ginflow-gate/gate.py (comment only)
owner: ginb
---

# Plan — CLEANUP-1.4: Versionless Execution Package and provider document

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets may have already changed nearby code — re-read before editing. RED test first, then change, then `make lint test`.

## Step 1: A: remove `workflow_version`

RED — `skills/ginflow/lib/test_execution_package.py`: remove `"workflow_version": 2,` from `PACKAGE`, and append to `test_shaping_and_approval_are_single_package_operations`:
```python
    assert "workflow_version" not in draft
```
Run `cd skills/ginflow/lib && python3 test_execution_package.py` — expect failure (`workflow_version must be 2` / assertion).

GREEN:
- `skills/ginflow/lib/execution_package.py`: delete `"workflow_version": 2,` in `shape_package`; delete the two lines `if package.get("workflow_version") != 2: errors.append(...)`; module docstring `"""Deterministic validation seam for minimal Ginflow execution packages."""`; `validate_package` docstring `"""Return stable validation result for one approved package.`
- `skills/ginflow/lib/card_creation.py`: delete `if package.get("workflow_version") != 2: raise ValueError(...)`; docstring `"""Build blocked Kanban cards from an approved Ginflow package."""`.
- `skills/ginflow/lib/execution_batch.py:1`: `"""Immutable AFK execution batch authorization around execution cards."""`.
- Tests: remove `"workflow_version": 2,` from `test_card_creation.py` (lines 13, 42→`package = {"contract": {"state": "draft"}}`, 65) and `test_execution_batch.py:23`. Rename `test_create_batch_delegates_legacy_card_creator` → `test_create_batch_delegates_card_creator` (def + call).
- Header of `test_execution_package.py`: `"""Tests for minimal Ginflow execution package seam."""`.

Verify: `make core-test; echo exit=$?` → 0; `grep -rn workflow_version --include=*.py .` → no output. Commit `refactor(ginflow): drop workflow_version from execution packages`.

## Step 2: E: require provider document on every unit

RED — `skills/ginflow/lib/test_execution_package.py`, append:
```python
def test_unit_without_document_is_invalid():
    unit = {k: v for k, v in PACKAGE["units"][0].items() if k != "document"}
    result = validate_package({**PACKAGE, "units": [unit]})
    assert result["valid"] is False and "unit UNIT-1.document is required" in result["errors"]
```
and call it in `__main__`. Also add `"document": REF` to `PACKAGE["units"][0]` (move `REF` definition above `PACKAGE`). Run → fails (missing-document package currently passes).

GREEN — `skills/ginflow/lib/execution_package.py` `_document_errors`: delete
```python
    if not any("document" in u for u in mappings):
        return []
```
and docstring → `"""Validate provider-neutral `document` refs; every unit needs exactly one."""`.

Fix fixtures that now lack documents:
- `test_card_creation.py` first test unit: add `"document": {"provider": "local", "id": "UNIT-1", "path_or_url": "docs/work-units/UNIT-1.md"}`. If it asserts on `links` from `package["links"]` for unit cards, update the assertion to the document path.
- `test_execution_batch.py` `package()` unit `U`: add `"document": {"provider": "local", "id": "U", "path_or_url": "docs/work-units/U.md"}`. Any test that clones the unit with a new `key` must also set a matching `document` (`id` = key, path ends `/<key>.md`); otherwise expect `does not match unit` / `duplicates` errors.
- `test_initiative_workflow.py` reuses `batch_package()` → covered.
- `card_creation._links`: unit branch keeps document path; delete unit-plan fallback (`if unit: plans = ...` block) since every unit now has a document. Integration card still uses `package["links"]` contract/spec.
- `execution_batch.create_batch` docstring: `"""Authorize, then create blocked unit and integration cards with batch lineage metadata."""`.
- `plugins/ginflow-gate/gate.py` `_document_error`: change comment only: `return None  # card links no provider document (spec/plan card)` (D2).

Verify: `make core-test; echo exit=$?` → 0. Commit `refactor(ginflow): require provider document per execution unit`.

## Step 3: F: drop `provider_document/v1` schema tag

RED — `skills/ginflow/lib/test_provider_document.py:27` → 
```python
    assert body.startswith("---\nprovider: local\nwork_unit: UNIT-1\n---\n")
```
plus after `doc = ...`: `assert "schema" not in doc["metadata"]`. Run → fails.

GREEN — `skills/ginflow/lib/provider_document.py`: delete `SCHEMA = ...`; frontmatter string → `f"---\nprovider: local\nwork_unit: {key}\n---\n"`; metadata → `{"provider": provider, "work_unit": key}`.

Verify: `python3 skills/ginflow/lib/test_provider_document.py && python3 plugins/ginflow-gate/test_document_baseline.py` both exit 0 (`ls docs/work-units` → none exist, so no stored hashes change). Commit `refactor(ginflow): drop provider_document schema tag`.