#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APPLY=0
if [[ "${1:-}" == "--apply" ]]; then APPLY=1; shift; fi

info() { printf 'ℹ️  %s\n' "$*"; }
ok() { printf '✅ %s\n' "$*"; }
die() { printf '❌ %s\n' "$*" >&2; exit 1; }
command -v hermes >/dev/null || die "Missing: hermes"
command -v python3 >/dev/null || die "Missing: python3"

REAL_HOME="${HERMES_REAL_HOME:-$(python3 -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)')}"
PROFILES_DIR="${HERMES_PROFILES_DIR:-$REAL_HOME/.hermes/profiles}"
export HOME="$REAL_HOME"
unset HERMES_HOME

existing="$(hermes profile list 2>/dev/null || true)"
if [[ "$#" -eq 0 ]]; then
  active="$(grep -Eo '◆[[:space:]]*[A-Za-z0-9][A-Za-z0-9._-]*' <<<"$existing" | head -n1 | sed 's/◆[[:space:]]*//')"
  [[ -n "$active" ]] || { printf 'Usage: %s [--apply] <profile> [profile ...]\n' "$0" >&2; exit 2; }
  set -- "$active"
fi
for profile in "$@"; do
  [[ "$profile" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "$profile: invalid profile name"
  grep -qw "$profile" <<<"$existing" || die "$profile: profile missing; install it first with 'hermes profile install <distribution> --name $profile'"
  profile_dir="$PROFILES_DIR/$profile"
  config="$profile_dir/config.yaml"
  [[ -f "$config" ]] || die "$profile: native config missing at $config"

  echo
  info "Integrating $profile (SOUL.md and distribution.yaml remain profile-owned)"
  if [[ "$APPLY" == 0 ]]; then
    info "$profile: would not copy files; run make install for skill and plugins"
    info "$profile: would add repo skill dirs, CodeGraph MCP, toolsets, and plugin enablement to native config"
    continue
  fi

  python3 - "$config" "$ROOT" <<'PY'
import sys
from pathlib import Path
import yaml
path, root = Path(sys.argv[1]), Path(sys.argv[2])
config = yaml.safe_load(path.read_text()) or {}

def mapping(key):
    value = config.get(key)
    if not isinstance(value, dict):
        value = {}
        config[key] = value
    return value

def list_value(parent, key):
    value = parent.get(key)
    if not isinstance(value, list):
        value = []
        parent[key] = value
    return value

external = list_value(mapping("skills"), "external_dirs")
for candidate in (str(root / "skills"), str(root / "community/mattpocock-skills/skills")):
    if Path(candidate).is_dir() and candidate not in external:
        external.append(candidate)
cli = list_value(mapping("platform_toolsets"), "cli")
for toolset in ("code_execution", "delegation", "file", "kanban", "memory", "session_search", "skills", "terminal", "todo", "vision", "web", "mcp-codegraph"):
    if toolset not in cli:
        cli.append(toolset)
mapping("mcp_servers")["codegraph"] = {
    "command": "codegraph", "args": ["serve", "--mcp"],
    "timeout": 120, "connect_timeout": 60, "enabled": True,
}
enabled = list_value(mapping("plugins"), "enabled")
if "ginflow-gate" not in enabled:
    enabled.append("ginflow-gate")
backup = path.with_name(path.name + ".bak.integration")
if not backup.exists():
    backup.write_text(path.read_text())
path.write_text(yaml.safe_dump(config, sort_keys=False))
PY
  ok "$profile: config integrations applied (run make install for skill/plugins); native identity and distribution untouched"
done

if [[ "$APPLY" == 1 ]]; then
  echo
  ok "Integration complete. Restart profile sessions, then run: ./scripts/verify.sh $*"
else
  echo
  info "Dry-run complete. Run: make apply PROFILES=\"$*\""
fi
