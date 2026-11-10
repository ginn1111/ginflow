#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/home/.hermes/profiles/gintary" "$TMP/home/.hermes/profiles/ginb"
printf '{}\n' > "$TMP/home/.hermes/profiles/gintary/config.yaml"
printf '{}\n' > "$TMP/home/.hermes/profiles/ginb/config.yaml"
cat > "$TMP/bin/hermes" <<'EOF'
#!/usr/bin/env bash
printf 'Profile  Model\n  gintary  model\n ◆ginb  model\n'
EOF
chmod +x "$TMP/bin/hermes"

output="$(HERMES_PROFILES_DIR="$TMP/home/.hermes/profiles" PATH="$TMP/bin:$PATH" make -s -C "$ROOT" setup PROFILES=)"
grep -q 'Integrating ginb' <<<"$output"
if grep -q 'Integrating gintary' <<<"$output"; then
  printf 'default setup must not integrate inactive profile\n' >&2
  exit 1
fi
grep -q 'Run: make apply PROFILES="ginb"' <<<"$output"

printf 'skills:\n  external_dirs:\nplugins:\n  enabled:\n' > "$TMP/home/.hermes/profiles/gintary/config.yaml"
HERMES_PROFILES_DIR="$TMP/home/.hermes/profiles" PATH="$TMP/bin:$PATH" make -s -C "$ROOT" apply PROFILES=gintary >/dev/null
python3 - "$TMP/home/.hermes/profiles/gintary/config.yaml" "$ROOT" <<'PY'
import sys
from pathlib import Path
import yaml
config = yaml.safe_load(Path(sys.argv[1]).read_text())
assert str(Path(sys.argv[2]) / "skills") in config["skills"]["external_dirs"]
assert "ginflow-gate" in config["plugins"]["enabled"]
PY
printf 'setup active-profile default and null config test ok\n'
