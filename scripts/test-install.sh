#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'chmod -R u+w "$TMP" 2>/dev/null || true; rm -rf "$TMP"' EXIT

HOME_ROOT="$TMP/home"
PROFILES="$HOME_ROOT/.hermes/profiles"
SKILL="$HOME_ROOT/.agents/skills/ginflow"
mkdir -p "$PROFILES/alpha/plugins" "$PROFILES/beta"
printf 'skills:\n  external_dirs:\n    - keep-me\nplugins:\n  enabled:\n    - keep-plugin\n' > "$PROFILES/alpha/config.yaml"
cp "$PROFILES/alpha/config.yaml" "$PROFILES/beta/config.yaml"
mkdir -p "$PROFILES/not-a-profile"   # no config.yaml: must be ignored

export HERMES_REAL_HOME="$HOME_ROOT"
export HERMES_PROFILES_DIR="$PROFILES"
export GINFLOW_INSTALL_MANIFEST="$TMP/.ginflow-install.json"

# No profile arguments: skill goes to ~/.agents/skills, plugin to every profile.
bash "$ROOT/scripts/install.sh" install
[[ -f "$SKILL/SKILL.md" ]]
[[ -f "$SKILL/lib/harness_core.py" ]]
for profile in alpha beta; do
  [[ -f "$PROFILES/$profile/plugins/ginflow-gate/plugin.yaml" && ! -e "$PROFILES/$profile/plugins/ginflow-gate/lib" ]]
  [[ -f "$PROFILES/$profile/plugins/ginflow-trace/plugin.yaml" ]]
  [[ ! -e "$PROFILES/$profile/plugins/with-chatgpt" ]]
  [[ ! -e "$PROFILES/$profile/skills/ginflow" ]]
done
[[ ! -e "$PROFILES/not-a-profile/plugins" ]]
[[ -f "$GINFLOW_INSTALL_MANIFEST" ]]
python3 - "$GINFLOW_INSTALL_MANIFEST" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    manifest = json.load(f)
assert set(manifest) == {"source_root", "skill", "plugins", "bin"}, sorted(manifest)
PY

# Copied gate package loads from a profile: every core module from ~/.agents/skills/ginflow/lib.
python3 -I - "$PROFILES/alpha/plugins/ginflow-gate" <<PY
import importlib.util, sys
from pathlib import Path
gate = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("copied_gate", gate / "__init__.py", submodule_search_locations=[str(gate)])
module = importlib.util.module_from_spec(spec)
sys.modules["copied_gate"] = module
spec.loader.exec_module(module)
lib = gate.resolve().parents[4] / ".agents/skills/ginflow/lib"
assert sys.modules["copied_gate.skill_lib"].LIB == lib, sys.modules["copied_gate.skill_lib"].LIB
for name in ("harness_core", "project_config", "routing", "publish"):
    assert Path(sys.modules[f"ginflow_lib_{name}"].__file__).parent == lib, name
PY

python3 - "$PROFILES/alpha/config.yaml" <<'PY'
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
assert "keep-me" in text
assert "keep-plugin" in text
PY

[[ -L "$HOME_ROOT/.local/bin/ginflow" && -x "$SKILL/scripts/ginflow.py" ]]

# Reinstall is idempotent.
bash "$ROOT/scripts/install.sh" install >/dev/null
[[ -f "$SKILL/SKILL.md" && -f "$PROFILES/beta/plugins/ginflow-trace/plugin.yaml" ]]

bash "$ROOT/scripts/install.sh" uninstall >/dev/null
[[ ! -e "$SKILL" && ! -L "$HOME_ROOT/.local/bin/ginflow" ]]
[[ ! -e "$PROFILES/alpha/plugins/ginflow-trace" && ! -e "$PROFILES/beta/plugins/ginflow-trace" ]]
[[ -f "$PROFILES/alpha/config.yaml" ]]
[[ ! -e "$GINFLOW_INSTALL_MANIFEST" ]]

# Explicit profile list limits the plugin install; unknown profile fails with no changes.
bash "$ROOT/scripts/install.sh" install alpha >/dev/null
[[ -f "$PROFILES/alpha/plugins/ginflow-trace/plugin.yaml" && ! -e "$PROFILES/beta/plugins/ginflow-trace" ]]
bash "$ROOT/scripts/install.sh" uninstall >/dev/null
if bash "$ROOT/scripts/install.sh" install alpha missing >/dev/null 2>&1; then
  echo "expected failure for unknown profile" >&2
  exit 1
fi
[[ ! -e "$SKILL" && ! -e "$GINFLOW_INSTALL_MANIFEST" ]]

# PROJECT runs `ginflow init --project <path>` once per profile with that profile's HERMES_HOME.
printf '#!/bin/sh\necho "$HERMES_HOME $*" >> "%s/init.log"\n' "$TMP" > "$TMP/stub"
chmod +x "$TMP/stub"
mkdir "$TMP/proj"
PROJECT="$TMP/proj" GINFLOW_BIN="$TMP/stub" GINFLOW_INIT_ARGS="--board b" bash "$ROOT/scripts/install.sh" install >/dev/null
[[ "$(wc -l < "$TMP/init.log")" == 2 ]]
grep -qx "$PROFILES/alpha init --project $TMP/proj --board b" "$TMP/init.log"
grep -qx "$PROFILES/beta init --project $TMP/proj --board b" "$TMP/init.log"
bash "$ROOT/scripts/install.sh" uninstall >/dev/null
printf '#!/bin/sh\nexit 1\n' > "$TMP/stub"
if PROJECT="$TMP/proj" GINFLOW_BIN="$TMP/stub" bash "$ROOT/scripts/install.sh" install >/dev/null 2>&1; then
  echo "expected install failure when init fails" >&2
  exit 1
fi
bash "$ROOT/scripts/install.sh" uninstall >/dev/null
[[ ! -e "$SKILL" && ! -e "$GINFLOW_INSTALL_MANIFEST" ]]

# Bootstrap one-liner: clones, installs into the selected profile only, rerun is idempotent, dirty clone aborts.
BOOT="$TMP/boot"
export GINFLOW_REPO="$ROOT" GINFLOW_DIR="$BOOT" GINFLOW_REF=HEAD
unset GINFLOW_INSTALL_MANIFEST
PROFILES="alpha" bash "$ROOT/install.sh" >/dev/null
[[ -f "$SKILL/SKILL.md" && -f "$PROFILES/alpha/plugins/ginflow-gate/plugin.yaml" && ! -e "$PROFILES/beta/plugins/ginflow-gate" ]]
PROFILES="alpha" bash "$ROOT/install.sh" >/dev/null
echo dirty > "$BOOT/dirty.txt"
if bash "$ROOT/install.sh" >/dev/null 2>&1; then echo "expected failure on dirty clone" >&2; exit 1; fi
rm "$BOOT/dirty.txt"
make -C "$BOOT" uninstall >/dev/null
[[ ! -e "$SKILL" && ! -e "$PROFILES/alpha/plugins/ginflow-gate" ]]
unset GINFLOW_REPO GINFLOW_DIR GINFLOW_REF
export GINFLOW_INSTALL_MANIFEST="$TMP/.ginflow-install.json"

# Failure mid-install restores every prior path; conflicts and profile state survive.
if [[ "$(id -u)" != "0" ]]; then
  A="$PROFILES/alpha"
  mkdir -p "$A/plugins/ginflow-trace" "$A/sessions" "$A/memories"
  printf 'prior-plugin\n' > "$A/plugins/ginflow-trace/prior.txt"
  printf 'secret\n' > "$A/.env"
  printf 'auth\n' > "$A/auth.json"
  printf 'session\n' > "$A/sessions/s.txt"
  printf 'memory\n' > "$A/memories/m.md"
  mkdir -p "$PROFILES/beta/plugins"
  chmod 555 "$PROFILES/beta/plugins"
  if bash "$ROOT/scripts/install.sh" install >/dev/null 2>&1; then
    chmod 755 "$PROFILES/beta/plugins"
    echo "expected install failure" >&2
    exit 1
  fi
  chmod 755 "$PROFILES/beta/plugins"
  [[ ! -e "$GINFLOW_INSTALL_MANIFEST" ]]
  [[ "$(cat "$A/plugins/ginflow-trace/prior.txt")" == "prior-plugin" ]]
  [[ ! -e "$SKILL/SKILL.md" && ! -e "$A/plugins/ginflow-trace/plugin.yaml" ]]
  [[ ! -e "$PROFILES/beta/plugins/ginflow-trace" ]]
  [[ -z "$(find "$HOME_ROOT" -path '*/.ginflow-install-backups/*' -mindepth 1)" ]]

  bash "$ROOT/scripts/install.sh" install alpha >/dev/null
  [[ -f "$A/plugins/ginflow-trace/plugin.yaml" ]]
  # Backup of the prior plugin lives outside plugins/, so Hermes never loads it as a second plugin.
  [[ -f "$A/.ginflow-install-backups/ginflow-trace/prior.txt" ]]
  [[ -z "$(find "$A/plugins" -mindepth 2 -maxdepth 2 -name plugin.yaml -not -path '*/ginflow-gate/*' -not -path '*/ginflow-trace/*')" ]]
  printf 'local edit\n' > "$A/plugins/ginflow-trace/extra.txt"
  if bash "$ROOT/scripts/install.sh" uninstall >/dev/null 2>&1; then
    echo "expected uninstall conflict" >&2
    exit 1
  fi
  [[ -f "$A/plugins/ginflow-trace/extra.txt" && -f "$GINFLOW_INSTALL_MANIFEST" ]]
  rm "$A/plugins/ginflow-trace/extra.txt"
  bash "$ROOT/scripts/install.sh" uninstall >/dev/null
  [[ "$(cat "$A/plugins/ginflow-trace/prior.txt")" == "prior-plugin" ]]
  [[ "$(cat "$A/.env")" == "secret" && "$(cat "$A/auth.json")" == "auth" ]]
  [[ "$(cat "$A/sessions/s.txt")" == "session" && "$(cat "$A/memories/m.md")" == "memory" ]]
fi

echo "install/uninstall tests passed"
