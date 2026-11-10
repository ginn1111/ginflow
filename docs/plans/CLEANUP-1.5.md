---
status: completed
scope: skills/ginflow/lib/project_config.py; test fixtures under skills/ginflow/scripts/ and plugins/ginflow-gate/; .ginflow.yaml, README.md, docs/guides/project-config.md, skills/ginflow/references/project-context.md
owner: ginb
---

# Plan — CLEANUP-1.5: Versionless .ginflow.yaml; stale version fails closed

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets are merged into `main` before this card starts and may have changed nearby code — re-read before editing. Ignore any umbrella-plan step about creating cards or closing the umbrella card. RED test first, then change, then `make lint test`.

## Step 1: C: drop `.ginflow.yaml` `version` and migration API

RED — `skills/ginflow/scripts/test-document-config.py`: replace whole migration block (from `# migration: preview, approval, ...` through the `stops(lambda: pc.apply_migration(...` line) with:
```python
    # top-level keys: only `ginflow`; stale `version` fails closed
    d = project()
    (d / ".ginflow.yaml").write_text(f"version: 1\nginflow:\n  board: b\n  workspace: {d}\n")
    assert "unknown top-level keys: version" in pc.context_error(d)
    stops(lambda: pc.set_documents(d, GH), "unknown top-level keys")
```
and line 22 fixture → `f"ginflow:\n  board: b\n  workspace: {d}\n{extra}"`. Run → fails (`version: 1` is currently valid; fixture without it currently invalid).

GREEN — `skills/ginflow/lib/project_config.py`:
- Delete `CONFIG_VERSION = 1`.
- In `context_error`, replace the version check with:
```python
    if not isinstance(data, dict):
        return "project config must be a mapping"
    unknown = set(data) - {"ginflow"}
    if unknown:
        return "project config has unknown top-level keys: " + ", ".join(sorted(unknown))
```
- `persist_context` payload → `{"ginflow": {"board": board, "workspace": str(workspace)}}`.
- Delete `preview_migration`, `_ensure_ignored`, `apply_migration`. `set_documents` docstring → `"""Save a valid documents block into a valid config, preserving other keys."""`.
- `__all__`: remove `"CONFIG_VERSION"`, `"preview_migration"`, `"apply_migration"`. Remove now-unused imports (`Callable` if unused: `grep -n "Callable" skills/ginflow/lib/project_config.py`).

Strip `version: 1\n` / `"version: 1\n"` from every fixture:
`skills/ginflow/scripts/test-project-reviewer.py:18`, `test-worktree-context.py:24`, `plugins/ginflow-gate/test_block_routing.py:84`, `test_ginflow_gate.py` (90, 101, 284, 360 — remaining ones after Task 2), `test_native_review_transition.py:58`, `test_publish_hook.py:55`, `test_reviewer_injection.py:25,28`. Find stragglers:
```bash
grep -rn 'version: 1' --include=*.py --include=*.sh . | grep -v '^./.ginflow/'   # expect no output
```
Config + docs: delete `version: 1` line in `.ginflow.yaml`, `README.md:58`, `docs/guides/project-config.md:6`, `skills/ginflow/references/project-context.md:10`; in `project-context.md:38` change "workspace, version, and unrelated keys" → "workspace, and unrelated keys". Add one sentence to `project-context.md` after the YAML block: "Only the `ginflow` top-level key is allowed; any other key (including a stale `version:`) fails closed — delete it."

Verify:
```bash
python3 skills/ginflow/scripts/test-document-config.py   # PASS: document config
make lint test; echo exit=$?                               # exit=0
grep -rn "CONFIG_VERSION\|apply_migration\|preview_migration\|ginflow/migrations" . --include=*.py --include=*.md | grep -v '^./.ginflow/'   # no output
```
Commit `refactor(ginflow): drop .ginflow.yaml version and migration API`.