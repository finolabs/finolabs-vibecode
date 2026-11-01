#!/usr/bin/env bash
# Build the two plugins used by the interview parity evals from the current skills.
# Usage: scripts/build-parity-plugins.sh <path to a checkout of mattpocock/skills>
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
upstream="${1:?path to a mattpocock/skills checkout}"
build() {
  local dest="$1" with_grilling="$2"
  rm -rf "$dest"
  mkdir -p "$dest/.claude-plugin" "$dest/skills" "$dest/references"
  printf '{\n  "name": "finolabs-vibecode",\n  "version": "0.0.0-parity"\n}\n' > "$dest/.claude-plugin/plugin.json"
  cp -R "$root/skills/fnl-setup-instructions" "$dest/skills/"
  cp "$root/references/interview.md" "$dest/references/"
  if [ "$with_grilling" = yes ]; then
    cp -R "$upstream/skills/productivity/grilling" "$dest/skills/grilling"
  fi
}
build "$root/evals/parity-interview-ours/plugins/ours" no
build "$root/evals/parity-interview-with-grilling/plugins/with-grilling" yes
echo "built parity plugins"
