#!/usr/bin/env node
// A PreToolUse hook that names the skill to invoke at the moment it applies.
//
// Skills are model-invoked: an agent decides from the description list whether
// to load one. That decision degrades as the list grows, and a subagent whose
// tool list omits Skill cannot load one at all. This hook removes the decision
// for the cases a tool call identifies exactly.
//
// Install: scripts/install.sh
// Protocol: reads the hook payload on stdin, writes additionalContext on stdout.
// Exit code is always 0. A failing hook never blocks the tool call.

const fs = require('fs');
const os = require('os');
const path = require('path');

const EDIT_TOOLS = new Set(['Write', 'Edit', 'NotebookEdit']);

// A Vale style lives under styles/<Style>/<Rule>.yml below a .vale.ini. The path
// alone also matches a front-end theme, such as src/styles/theme/colors.yml.
// A rule file counts only where a .vale.ini sits in a parent directory.
const VALE_CONFIG = /(^|\/)\.?vale\.ini$/i;
const VALE_RULE = /(^|\/)styles\/[^/]+\/[^/]+\.ya?ml$/i;

function underValeConfig(file) {
  let dir = path.dirname(path.resolve(file));
  for (;;) {
    if (['.vale.ini', 'vale.ini'].some((n) => fs.existsSync(path.join(dir, n)))) return true;
    const up = path.dirname(dir);
    if (up === dir) return false;
    dir = up;
  }
}

// `git`, then any global option before the subcommand: `-C <dir>`, `-c <key=value>`
// with or without quotes, and long ones such as `--no-pager` or `--git-dir=<dir>`.
const GIT = String.raw`(^|[|&;\s])git(\s+(-[Cc]\s+([^\s"']|"[^"]*"|'[^']*')+|--[a-z-]+(=\S+)?))*\s+`;
// Creates or renames: `checkout -b`/`--orphan`, `switch -c`/`--create`/`--orphan`,
// `branch -m`/`-c`/`-f`, `branch <name>`, `worktree add`. A bare `git branch`
// or `branch -d` lists or deletes and names nothing.
const BRANCH = new RegExp(
  GIT +
    String.raw`(checkout\s+(-[bB]|--orphan)|switch\s+(-[cC]|--create|--force-create|--orphan)|branch\s+(-[mMcCf]|--move|--copy|--force|[A-Za-z])|worktree\s+add)`
);
const COMMIT = new RegExp(GIT + String.raw`commit(\s|$)`);

const RULES = [
  {
    id: 'markdown',
    applies: (tool, input) =>
      EDIT_TOOLS.has(tool) && /\.mdx?$/i.test(input.file_path || ''),
    context:
      'This is a Markdown file. Invoke the `markdown-formatting` skill for structure ' +
      '(blank lines around every block, heading levels, list markers, fenced code with ' +
      'a language, table cell counts) and the `technical-writing` skill for wording ' +
      '(where a fact belongs, sentence rules, vocabulary). Apply both to this edit and ' +
      'to every later Markdown edit in this session.',
  },
  {
    id: 'vale',
    applies: (tool, input) => {
      if (EDIT_TOOLS.has(tool)) {
        const file = input.file_path || '';
        return VALE_CONFIG.test(file) || (VALE_RULE.test(file) && underValeConfig(file));
      }
      return tool === 'Bash' && /(^|[|&;\s])vale(\s|$)/.test(input.command || '');
    },
    context:
      'This touches a Vale style gate. Invoke the `docs-linter` skill: it carries the ' +
      'config traps, the ready rule files, and the requirement that a new rule ships ' +
      'with a probe it catches and a probe it does not over-catch.',
  },
  {
    id: 'branch',
    applies: (tool, input) => tool === 'Bash' && BRANCH.test(input.command || ''),
    context:
      'A branch is being created or renamed. Invoke the `branch-names` skill and name it ' +
      '`<type>/[<ticket-id>-]<slug>`: lower case, one slash, 40 characters or fewer. ' +
      '`branch-names/scripts/branch-name.sh` builds the name and checks one.',
  },
  {
    id: 'commit',
    applies: (tool, input) => tool === 'Bash' && COMMIT.test(input.command || ''),
    context:
      'A commit is being prepared. Invoke the `commit-messages` skill and write the ' +
      'message to Conventional Commits 1.0.0 as that skill specifies.',
  },
];

// One reminder per category per session. A repeat costs tokens and says nothing new.
function alreadySent(sessionId, ruleId) {
  const session = String(sessionId || 'no-session').replace(/[^\w-]/g, '') || 'no-session';
  const dir = path.join(os.tmpdir(), 'claude-skill-reminder');
  const stamp = path.join(dir, `${session}.${ruleId}`);
  try {
    fs.mkdirSync(dir, { recursive: true });
    if (fs.existsSync(stamp)) return true;
    fs.writeFileSync(stamp, '');
  } catch {
    // An unwritable stamp costs a duplicate reminder, which is not worth failing over.
  }
  return false;
}

function main() {
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch {
    return;
  }

  const tool = payload.tool_name || '';
  const input = payload.tool_input || {};
  // Every matching rule, not the first: `git switch -c x && git commit` needs both.
  const due = RULES.filter((r) => r.applies(tool, input)).filter(
    (r) => !alreadySent(payload.session_id, r.id)
  );
  if (due.length === 0) return;

  process.stdout.write(
    JSON.stringify({
      suppressOutput: true,
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        additionalContext: due.map((r) => r.context).join('\n\n'),
      },
    })
  );
}

main();
