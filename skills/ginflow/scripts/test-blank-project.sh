#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$SKILL_DIR/../.." && pwd)"
TARGET="$(mktemp -d /tmp/ginflow-blank-XXXXXX)"
CARD="$(mktemp -t ginflow-card)"
OUTPUT="$(mktemp -t ginflow-output)"
KEEP_TMP="${KEEP_TMP:-0}"

cleanup() {
  status=$?
  if [[ "$status" -ne 0 || "$KEEP_TMP" == 1 ]]; then
    printf 'blank project retained: %s\n' "$TARGET"
    printf 'agent output retained: %s\n' "$OUTPUT"
  else
    rm -rf "$TARGET"
  fi
  rm -f "$CARD"
  [[ "$KEEP_TMP" == 1 || "$status" -ne 0 ]] || rm -f "$OUTPUT"
  exit "$status"
}
trap cleanup EXIT

git init -q "$TARGET"
python3 - "$SKILL_DIR/scripts/fixtures/card.json" "$CARD" "$TARGET" <<'PY'
import pathlib, sys
source, target, workspace = map(pathlib.Path, sys.argv[1:])
target.write_text(source.read_text().replace("{{WORKSPACE}}", str(workspace)))
PY

task="$(printf '%s\n' 'slugify CLI' 'line counter CLI' 'JSON key sorter CLI' | shuf -n 1)"
prompt="The blank target git repo is exactly $TARGET. Load and follow ginflow. The agent's configured working directory may differ; do not ask for another repo. Run every file and git operation against $TARGET using cd $TARGET or absolute paths. Test card TEST-001 requests: $task. Copy the canonical template from $ROOT/templates/hermes.md to $TARGET/.hermes.md, add .hermes.md to $TARGET/.git/info/exclude, never create or edit AGENTS.md or CLAUDE.md, then tailor only local sections and retain ginflow routing. Before doing anything else, add this exact standalone line to .hermes.md: Canonical verification command: ./verify.sh. This line is mandatory in .hermes.md, not only in the local task artifacts. Create docs/specs/TEST-001.md. Implement a small standard-library-only solution and tests. Create executable verify.sh using set -eu; document ./verify.sh as canonical verification. Do not create spec or plan unless needed. Do not create session handoff. Before final report verify that .hermes.md contains the exact canonical-command line, run $TARGET/verify.sh, and run git -C $TARGET status --short. Report only this repo's files and fresh canonical output."

PROFILE="${HERMES_TEST_PROFILE:-default}"
(cd "$TARGET" && env -u TERMINAL_CWD hermes -p "$PROFILE" -s ginflow -z "$prompt") >"$OUTPUT"

test -f "$TARGET/.hermes.md"
test ! -e "$TARGET/AGENTS.md"
test ! -e "$TARGET/CLAUDE.md"
grep -qx ".hermes.md" "$TARGET/.git/info/exclude"
test -z "$(git -C "$TARGET" status --short .hermes.md)"
test -f "$TARGET/docs/specs/TEST-001.md"
test -f "$TARGET/verify.sh"
test ! -e "$TARGET/session-handoff.md"
grep -q 'come from `ginflow`' "$TARGET/.hermes.md"
chmod +x "$TARGET/verify.sh"
(cd "$TARGET" && ./verify.sh)
git -C "$TARGET" config user.name 'Ginflow Blank Project Test'
git -C "$TARGET" config user.email 'ginflow-blank-test@example.invalid'
git -C "$TARGET" add -A
if ! git -C "$TARGET" diff --cached --quiet; then
  git -C "$TARGET" commit -qm 'verified blank project fixture'
fi
python3 - "$CARD" "$TARGET" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

card_path, target = map(Path, sys.argv[1:])
card = json.loads(card_path.read_text())
commit = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
card.update({
    "status": "done",
    "links": ["docs/specs/TEST-001.md"],
    "artifact_baseline": {
        "commit": commit,
        "paths": ["docs/specs/TEST-001.md"],
    },
})
card_path.write_text(json.dumps(card, indent=2) + "\n")
PY
python3 "$SKILL_DIR/scripts/validate-harness.py" --setup-repo "$ROOT" --target "$TARGET" --card "$CARD"

echo "random task: $task"
echo "blank project harness test passed"
