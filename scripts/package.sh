#!/usr/bin/env bash
# Package every skill as a .skill archive under dist/.
# Usage: scripts/package.sh [skill-name ...]   (default: all)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
targets=("$@")
if [ ${#targets[@]} -eq 0 ]; then
  targets=()
  for d in */; do
    [ -f "${d}SKILL.md" ] && targets+=("${d%/}")
  done
fi
for name in "${targets[@]}"; do
  name=${name%/}   # tab completion adds the slash
  [ -f "$name/SKILL.md" ] || { echo "$name: no SKILL.md" >&2; exit 1; }
  rm -f "dist/$name.skill"
  # Only what the repository tracks: a stray __pycache__ or .DS_Store stays out.
  git ls-files -z -- "$name" \
    | xargs -0 zip -q -X "dist/$name.skill"
  echo "dist/$name.skill"
done
