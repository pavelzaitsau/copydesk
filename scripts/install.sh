#!/usr/bin/env bash
# Link these skills into every harness directory, and register the reminder hook.
# Usage: scripts/install.sh [--dry-run]
#
# Symlinks, not copies: an edit in this repository takes effect in the next
# session with no reinstall. Re-running the script is safe.
#
# Three directories, because three harnesses look in different places:
#   ~/.claude/skills   Claude Code
#   ~/.agents/skills   Codex, and Junie as its last fallback
#   ~/.junie/skills    Junie, which reads this one first
# Linking one and not the others is how a skill goes missing from one harness
# and nowhere else. Override a root with CLAUDE_HOME, AGENTS_HOME or JUNIE_HOME.
#
# The reminder hook is a Claude Code hook and is registered under CLAUDE_HOME only.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
claude="${CLAUDE_HOME:-$HOME/.claude}"
agents="${AGENTS_HOME:-$HOME/.agents}"
junie="${JUNIE_HOME:-$HOME/.junie}"
dry=0
[ "${1:-}" = "--dry-run" ] && dry=1

say() { printf '%s\n' "$*"; }
run() { [ "$dry" -eq 1 ] && say "would: $*" || "$@"; }

node_bin="$(command -v node || true)"
if [ -z "$node_bin" ]; then
  say "node not found on PATH; the hook needs it" >&2
  exit 1
fi

# Skills, into each root in turn. A root holding other skills keeps them: the loop
# only ever touches a name this repository owns. Under such a name it replaces a
# link and nothing else. A real directory there is a copy someone made on purpose,
# for a harness that does not follow symlinks, and it may hold their edits.
linked=0
skipped=0
kept=0
for root in "$claude/skills" "$agents/skills" "$junie/skills"; do
  run mkdir -p "$root"
  for dir in "$repo"/*/; do
    name="$(basename "$dir")"
    [ -f "$dir/SKILL.md" ] || continue
    link="$root/$name"
    current="$([ -L "$link" ] && readlink "$link" || echo '')"
    if [ "$current" = "${dir%/}" ]; then
      skipped=$((skipped + 1))
      continue
    fi
    if [ -L "$link" ]; then
      run rm -f "$link"
    elif [ -e "$link" ]; then
      say "kept $link: not a link; delete it to link this skill instead"
      kept=$((kept + 1))
      continue
    fi
    run ln -s "${dir%/}" "$link"
    [ "$dry" -eq 1 ] || say "linked $link"
    linked=$((linked + 1))
  done
done
verb=linked
[ "$dry" -eq 1 ] && verb="to link"
say "skills: $linked $verb, $skipped already in place, $kept kept as they are"

run mkdir -p "$claude/hooks"
hook="$claude/hooks/skill-reminder.js"
if [ "$([ -L "$hook" ] && readlink "$hook" || echo '')" = "$repo/scripts/skill-reminder.js" ]; then
  say "hook: already linked"
else
  if [ -e "$hook" ] || [ -L "$hook" ]; then
    run rm -f "$hook"
  fi
  run ln -s "$repo/scripts/skill-reminder.js" "$hook"
  [ "$dry" -eq 1 ] || say "hook: linked"
fi

# Registration in settings.json. Node edits the file so jq is not a dependency.
settings="$claude/settings.json"
if [ "$dry" -eq 1 ]; then
  say "would: register the PreToolUse hook in $settings"
  exit 0
fi
[ -f "$settings" ] || printf '{}\n' > "$settings"
NODE_BIN="$node_bin" HOOK_PATH="$hook" SETTINGS="$settings" node <<'JS'
const fs = require('fs');
const file = process.env.SETTINGS;
const command = `"${process.env.NODE_BIN}" "${process.env.HOOK_PATH}"`;
const before = fs.readFileSync(file, 'utf8');
const settings = JSON.parse(before);

settings.hooks ||= {};
const entries = settings.hooks.PreToolUse || [];

// Drop any earlier registration, including one written under the old file name.
const stale = /skills?-reminder\.js/;
const kept = entries
  .map((entry) => ({
    ...entry,
    hooks: (entry.hooks || []).filter((h) => !stale.test(h.command || '')),
  }))
  .filter((entry) => entry.hooks.length > 0);

kept.push({
  matcher: 'Write|Edit|NotebookEdit|Bash',
  hooks: [{ type: 'command', command, timeout: 5 }],
});
settings.hooks.PreToolUse = kept;

// A re-run that changes nothing writes nothing. The backup then keeps the file
// as it was before the last real change, not a copy of the current one.
const after = JSON.stringify(settings, null, 2) + '\n';
if (after === before) {
  console.log('settings: hook already registered');
} else {
  fs.writeFileSync(`${file}.bak`, before);
  fs.writeFileSync(file, after);
  console.log(`settings: hook registered (backup at ${file}.bak)`);
}
JS
