---
status: draft
scope: plugins/ginflow-gate/*.py; plugins/ginflow-trace/test_ginflow_trace_integration.py; skills/ginflow/scripts/test-ginflow-lifecycle.py
owner: ginb
---

# Plan — CLEANUP-1.2: ginflow-gate loads as one package with relative imports

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets are merged into `main` before this card starts and may have changed nearby code — re-read before editing. Ignore any umbrella-plan step about creating cards or closing the umbrella card. RED test first, then change, then `make lint test`.

## Step 1: Dedupe ginflow-gate import fallbacks

Tests first (they must import via package before fallbacks go). In each file below, replace the `spec_from_file_location(...gate.py | routing.py ...)` block with:
```python
import importlib, sys
sys.path.insert(0, str(ROOT / "plugins"))
gate = importlib.import_module("ginflow-gate.gate")        # or .routing / package "ginflow-gate"
```
Files and the variable each must bind:
| File | Current loader | Bind |
|---|---|---|
| `plugins/ginflow-gate/test_ginflow_gate.py:16` | routing.py | `module = importlib.import_module("ginflow-gate.routing")` |
| `plugins/ginflow-gate/test_ginflow_gate.py:~438` | gate.py | `module = importlib.import_module("ginflow-gate.gate")` |
| `plugins/ginflow-gate/test_ginflow_gate.py:~618` | `__init__.py` | `package = importlib.import_module("ginflow-gate")` |
| `plugins/ginflow-gate/test_document_baseline.py:13` | gate.py | `gate = ...("ginflow-gate.gate")` |
| `plugins/ginflow-gate/test_native_review_transition.py:load_gate` | gate.py | `return importlib.import_module("ginflow-gate.gate")` |
| `plugins/ginflow-gate/test_reviewer_injection.py:8` | gate.py | `gate = ...("ginflow-gate.gate")` |
| `plugins/ginflow-gate/test_recovery_policy.py:load` | by name | `return importlib.import_module(f"ginflow-gate.{name}")` |
| `skills/ginflow/scripts/test-ginflow-lifecycle.py:170` | gate.py | `gate = importlib.import_module("ginflow-gate.gate")` (insert `ROOT / "plugins"` on `sys.path` in `_syspath_insert`) |
| `plugins/ginflow-trace/test_ginflow_trace_integration.py:_load_gate_module` | gate.py | insert `ROOT.parent` on `sys.path`; `return importlib.import_module("ginflow-gate.gate")` |

Run `make test; echo exit=$?` → 0 (fallbacks still present; proves tests work via package).

Then delete fallbacks:
- `plugins/ginflow-gate/gate.py`: replace the three `try/except ImportError` blocks (trace_adapter, publish, skill_lib) with
```python
from .trace_adapter import trace
from . import publish as _publish
from . import skill_lib
```
- `routing.py`: same three (trace_adapter, skill_lib, publish).
- `publish.py`, `block_routing.py`: `from . import skill_lib`.
- `recovery_policy.py`: `from .blocker_reporting import MAX_ATTEMPTS, NON_RECOVERABLE_KINDS` (drop fallback).
- Remove `import importlib.util` where now unused: `grep -n "importlib" plugins/ginflow-gate/{gate,routing,publish,block_routing}.py` → no output.
- Keep `trace_adapter.py`'s loader (cross-plugin load of `ginflow-trace`, legitimate) and `skill_lib.py` (single core loader).

Also dedupe `routing._normalize_task` onto core:
```python
@trace
def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Adapt live task fields for the shared Ginflow startup validator."""
    card = _core.normalize_card({"task": task})
    if not card["workspace"]:
        card["workspace"] = task.get("workspace") or task.get("workspace_path") or ""
    return card
```
(`normalize_card` with no `runs` adds nothing else; fallback keeps old behavior for tasks without `workspace_kind`.)

Verify:
```bash
grep -n "spec_from_file_location" plugins/ginflow-gate/*.py | grep -v test_   # only skill_lib.py and trace_adapter.py
make lint test; echo exit=$?    # exit=0
```
Commit `refactor(ginflow-gate): use package relative imports; reuse core normalize_card`.