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
# only ever touches a name this repository owns.
linked=0
skipped=0
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
    if [ -e "$link" ] || [ -L "$link" ]; then
      run rm -rf "$link"
    fi
    run ln -s "${dir%/}" "$link"
    say "linked $link"
    linked=$((linked + 1))
  done
done
say "skills: $linked linked, $skipped already in place"

# Hook.
run mkdir -p "$claude/hooks"
hook="$claude/hooks/skill-reminder.js"
if [ "$([ -L "$hook" ] && readlink "$hook" || echo '')" = "$repo/scripts/skill-reminder.js" ]; then
  say "hook: already linked"
else
  if [ -e "$hook" ] || [ -L "$hook" ]; then
    run rm -f "$hook"
  fi
  run ln -s "$repo/scripts/skill-reminder.js" "$hook"
  say "hook: linked"
fi

# Registration in settings.json. Node edits the file so jq is not a dependency.
settings="$claude/settings.json"
if [ "$dry" -eq 1 ]; then
  say "would: register the PreToolUse hook in $settings"
  exit 0
fi
[ -f "$settings" ] || printf '{}\n' > "$settings"
cp "$settings" "$settings.bak"
NODE_BIN="$node_bin" HOOK_PATH="$hook" SETTINGS="$settings" node <<'JS'
const fs = require('fs');
const file = process.env.SETTINGS;
const command = `"${process.env.NODE_BIN}" "${process.env.HOOK_PATH}"`;
const settings = JSON.parse(fs.readFileSync(file, 'utf8'));

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

fs.writeFileSync(file, JSON.stringify(settings, null, 2) + '\n');
JS
say "settings: hook registered (backup at $settings.bak)"
