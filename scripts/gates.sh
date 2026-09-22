#!/usr/bin/env bash
# Both gates over this repository, the same way CI runs them.
# Usage: scripts/gates.sh
#
# Neither binary is a dependency of this repository: Vale is a Go binary and
# markdownlint-cli2 an npm package, and each is installed separately. Both
# configs live at the repository root, so neither command takes an argument.
#
# `.claude/` holds symlinks back into this repository. Linting it reports every
# file twice. The Markdown config excludes it; Vale has no directory exclusion
# in its config file, so the glob goes here.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

if command -v vale >/dev/null 2>&1; then
  vale --minAlertLevel=error --glob='!.claude/**' . || fail=1
else
  echo "vale not found; install it with: brew install vale" >&2
  fail=127
fi

if command -v markdownlint-cli2 >/dev/null 2>&1; then
  markdownlint-cli2 || fail=1
else
  npx --yes markdownlint-cli2@0.23.2 || fail=1
fi

exit "$fail"
