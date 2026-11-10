#!/usr/bin/env bash
set -euo pipefail
# community-setup.sh — Clone/pull community skill repos.
# Usage: ./scripts/community-setup.sh [--apply]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

info()  { printf 'ℹ️  %s\n' "$*"; }
ok()    { printf '✅ %s\n' "$*"; }
warn()  { printf '⚠️  %s\n' "$*" >&2; }
die()   { printf '❌ %s\n' "$*" >&2; exit 1; }

COMMUNITY_DIR="$ROOT/community"

# Repositories: name → git-url
declare -A REPOS=(
  [mattpocock-skills]="https://github.com/mattpocock/skills.git"
)

for name in "${!REPOS[@]}"; do
  url="${REPOS[$name]}"
  target="$COMMUNITY_DIR/$name"
  if [[ -d "$target/.git" ]]; then
    info "$name: already cloned at $target"
    if [[ "$APPLY" == "1" ]]; then
      (cd "$target" && git pull --ff-only) && ok "$name: updated" || warn "$name: pull failed"
    else
      info "$name: would git pull (--apply)"
    fi
  else
    info "$name: cloning from $url"
    if [[ "$APPLY" == "1" ]]; then
      mkdir -p "$COMMUNITY_DIR"
      git clone "$url" "$target"
      chmod -R a-w "$target"
      ok "$name: cloned"
    else
      info "$name: would clone $url → $target (--apply)"
    fi
  fi
done

echo ""
if [[ "$APPLY" == "1" ]]; then
  ok "Community assets ready."
else
  info "Dry-run. Run with --apply to clone/update."
fi
