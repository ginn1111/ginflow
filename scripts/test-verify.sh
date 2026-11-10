#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$(mktemp)"
trap 'rm -f "$output"' EXIT

python3 "$ROOT/skills/ginflow/scripts/validate-harness.py" --setup-repo "$ROOT" --json >"$output" 2>&1
python3 "$ROOT/skills/ginflow/scripts/validate-harness.py" --setup-repo "$ROOT" --json >"$output" 2>&1
printf 'verify behavior ok\n'
