---
status: draft
scope: scripts/install.sh; scripts/test-install.sh
owner: ginb
---

# Plan — CLEANUP-1.6: Versionless install manifest

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets may have already changed nearby code — re-read before editing. RED test first, then change, then `make lint test`.

## Step 1: D: drop install manifest versioning

RED — `scripts/test-install.sh`, after `[[ -f "$GINFLOW_INSTALL_MANIFEST" ]]` add:
```bash
python3 - "$GINFLOW_INSTALL_MANIFEST" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1]))
assert set(manifest) == {"source_root", "skill", "plugins"}, sorted(manifest)
PY
```
Run `bash scripts/test-install.sh` → AssertionError (`version` present).

GREEN — `scripts/install.sh`: delete `VERSION = 2`; manifest literal → `{"source_root": str(ROOT), "skill": {}, "plugins": {}}`; in `managed_entries` delete the `for name, item in manifest.get("profiles", {})...` loop (4 lines) and docstring → `"""(label, path, hash, backup) for every managed entry."""`.

Verify: `bash scripts/test-install.sh` → `install/uninstall tests passed`. Commit `refactor(install): drop manifest version and v1 profile entries`.