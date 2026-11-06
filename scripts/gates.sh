#!/usr/bin/env bash
# The gates over this repository, the same way CI runs them.
# Usage: scripts/gates.sh
#
# Neither binary is a dependency of this repository: Vale is a Go binary and
# markdownlint-cli2 an npm package, and each is installed separately. Both
# configs live at the repository root, so neither command needs a config path.
#
# `.claude/` holds symlinks back into this repository. Linting it reports every
# file twice. `_notes/` holds working drafts that git ignores. The Markdown config
# excludes both; Vale has no directory exclusion in its config file, so the glob
# goes here.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

if command -v vale >/dev/null 2>&1; then
  vale --minAlertLevel=error --glob='!{.claude,_notes}/**' . || fail=1
else
  echo "vale not found; install it with: brew install vale" >&2
  fail=127
fi

# A missing Vale keeps its 127; a lint failure only sets a status not yet set.
# The npx pin is a copy of the one in markdown-formatting/scripts/lint-markdown.sh,
# which ships with the skill and owns it.
if command -v markdownlint-cli2 >/dev/null 2>&1; then
  markdownlint-cli2 || { [ "$fail" -ne 0 ] || fail=1; }
else
  npx --yes markdownlint-cli2@0.23.2 || { [ "$fail" -ne 0 ] || fail=1; }
fi

# demo-video's generated voice list and docs, and its default voices: each default must be
# in the list and run on an engine whose licence is 'clean'.
python3 demo-video/scripts/fit_votes.py --check || { [ "$fail" -ne 0 ] || fail=1; }

# demo-video's unit tests: no model and no browser, only Python's stdlib and node.
# Quiet when they pass; the full report when one fails.
out=$(python3 -m unittest discover -s demo-video/tests -t demo-video/tests 2>&1) || { echo "$out" >&2; [ "$fail" -ne 0 ] || fail=1; }
out=$(node --test demo-video/tests/*.test.mjs 2>&1) || { echo "$out" >&2; [ "$fail" -ne 0 ] || fail=1; }

# explainer's unit tests: its linter and deck builder, Python's stdlib only.
out=$(python3 -m unittest discover -s explainer/tests -t explainer/tests 2>&1) || { echo "$out" >&2; [ "$fail" -ne 0 ] || fail=1; }

exit "$fail"
