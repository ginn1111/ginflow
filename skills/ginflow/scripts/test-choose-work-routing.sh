#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
TARGET="$(mktemp -d /tmp/ginflow-choose-work-XXXXXX)"
OUTPUT="$(mktemp /tmp/ginflow-choose-work-output-XXXXXX)"
KEEP_TMP="${KEEP_TMP:-0}"

cleanup() {
  status=$?
  if [[ "$status" -ne 0 || "$KEEP_TMP" == 1 ]]; then
    printf 'choose-work target retained: %s\n' "$TARGET"
    printf 'agent output retained: %s\n' "$OUTPUT"
  else
    rm -rf "$TARGET" "$OUTPUT"
  fi
  exit "$status"
}
trap cleanup EXIT

git init -q "$TARGET"

prompt="You are in the confirmed target workspace $TARGET, a real git repo with no Kanban cards. Load and follow ginflow. Do not create or modify files. Report the routing decision only. Explain which work mode applies when cause is unclear, when requirements are clear, and when requirements are unclear. Mention brainstorming or read-only work shaping for unclear requirements. State that no implementation starts before card selection."
PROFILE="${HERMES_TEST_PROFILE:-default}"
(
  cd "$TARGET"
  env -u TERMINAL_CWD hermes -p "$PROFILE" -s ginflow -z "$prompt"
) >"$OUTPUT"

# Prove agent received plugin-owned choose-work context and did not mutate target.
grep -Eiq 'investigation' "$OUTPUT"
grep -Eiq 'cause( is)?[[:space:]]+unclear' "$OUTPUT"
grep -Eiq 'implementation' "$OUTPUT"
grep -Eiq 'requirements (are )?clear' "$OUTPUT"
grep -Eiq 'brainstorming|work shaping' "$OUTPUT"
grep -Eiq 'requirements (are )?unclear' "$OUTPUT"
grep -Eiq 'before explicit Kanban card selection|before .*card selection' "$OUTPUT"
test -z "$(git -C "$TARGET" status --short)"
test -z "$(find "$TARGET" -path "$TARGET/.git" -prune -o -type f -print -quit)"

echo "real agent choose-work routing test passed"
rm -f "$OUTPUT"
