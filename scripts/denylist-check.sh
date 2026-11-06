#!/bin/sh
# Checks text against the private denylist of names this public repository must
# never contain. The list lives outside the repository, because a list inside it
# would itself name what it guards against.
#
#   scripts/denylist-check.sh --staged      check the lines a commit adds, and its paths
#   scripts/denylist-check.sh FILE          check a file, such as a commit message
#
# The list is ~/.config/copydesk/denylist.txt, or the file COPYDESK_DENYLIST names:
# one word or phrase per line, matched case-insensitively as a whole word; lines
# starting with # are comments. Without the list the check warns and passes.
list=${COPYDESK_DENYLIST:-$HOME/.config/copydesk/denylist.txt}
if [ ! -f "$list" ]; then
  echo "denylist: $list not found; the check did not run" >&2
  exit 0
fi
patterns=$(mktemp)
text=$(mktemp)
trap 'rm -f "$patterns" "$text"' EXIT
# A list saved with Windows line endings would match nothing, so drop the carriage returns.
tr -d '\r' < "$list" | grep -v '^[[:space:]]*#' | grep -v '^[[:space:]]*$' > "$patterns"
[ -s "$patterns" ] || exit 0

if [ "$1" = "--staged" ]; then
  # Plain output whatever the user's diff settings: colour, an external diff or a
  # textconv filter would hide the added lines from grep. --text reads binary files too.
  {
    git diff --cached --name-only --diff-filter=ACMR
    git diff --cached -U0 --no-color --no-ext-diff --no-textconv --text --diff-filter=ACMR \
      | grep -a '^+' | grep -a -v -e '^+++ b/' -e '^+++ /dev/null'
  } > "$text"
else
  # A message file: stop at the scissors line, below which `commit -v` puts the diff.
  # Comment lines stay, because `commit -m` keeps them in the commit.
  cc=$(git config --get core.commentString 2>/dev/null || git config --get core.commentChar 2>/dev/null || true)
  case "$cc" in ''|auto) cc='#' ;; esac
  awk -v cc="$cc" '$0 == cc " ------------------------ >8 ------------------------" { exit } { print }' "$1" > "$text"
fi
# grep -w counts "_" as part of a word, so a name inside snake_case would slip through.
# A NUL in a binary file separates words the same way a newline does.
hits=$(tr '\000_' '\n ' < "$text" | grep -a -i -w -o -F -f "$patterns" | sort -u)
if [ -n "$hits" ]; then
  echo "denylist: the commit contains names from $list:" >&2
  printf '  %s\n' "$hits" >&2
  exit 1
fi
exit 0
