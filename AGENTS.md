# AGENTS.md

Rules for any agent working in this repository.

## What this repository is

The README says what this repository is. Each top-level directory holding a `<skill>/SKILL.md` is one skill, and this file says how to change one.

| Skill | Owns |
| --- | --- |
| `technical-writing` | How a document reads: reader-first decisions, where a fact lives, sentence rules, comment discipline, document templates |
| `docs-linter` | The machine half of the same rules: Vale config, rule files, config traps |
| `commit-messages` | Conventional Commits 1.0.0, ticket ids, breaking changes, the commit gate |
| `branch-names` | The branch name: type prefix, ticket id, slug, the length budget, the push gate |
| `markdown-formatting` | How a `.md` file is built: blank lines, headings, lists, fences, tables |

## Layout

```text
<skill>/SKILL.md          the skill, always present
<skill>/LICENSE.txt        the terms, so a packaged skill carries them
<skill>/references/*.md    detail loaded on demand, never on every trigger
<skill>/scripts/           executable code the skill ships
<skill>/assets/            configuration the skill ships
<skill>/evals/evals.json   test prompts, where the output is objectively checkable
.vale.ini                  the prose gate, pointed at the styles docs-linter ships
.markdownlint-cli2.jsonc   the structure gate, extending the config markdown-formatting ships
.claude/skills/            symlinks, so an agent here uses these skills on itself
.githooks/commit-msg       the gate from commit-messages, wired to this repository
.githooks/pre-push         the gate from branch-names, wired to this repository
.github/workflows/         the gates, on every push and pull request
scripts/gates.sh           runs both gates, the same way CI does
scripts/package.sh         builds dist/<skill>.skill
scripts/skill-reminder.js  PreToolUse hook that names the skill a tool call calls for
scripts/install.sh         links the skills into all three harness directories and registers the hook
```

## The skills apply to this repository first

An agent that writes here uses these skills on its own output. A skill that its own repository does not follow is advice, not a rule.

- **Any prose in any file** follows `technical-writing`. That covers every `<skill>/SKILL.md` body, `references/`, this file, the README and every comment in `assets/`.
- **Every commit message** follows `commit-messages`. The hook enforces the part a machine can check.
- **Every branch name** follows `branch-names`. The push hook enforces it, and lets `main` through.
- **Changes to a rule set** follow `docs-linter`: a new rule ships with a probe that it catches and a probe that it does not over-catch.
- **Every `.md` file** follows `markdown-formatting`. The structure gate below checks the part a machine can check.

Enable the hook once per clone:

```bash
git config core.hooksPath .githooks
```

Both gates, over everything:

```bash
scripts/gates.sh
```

Each gate needs its own binary and is configured at the root, so neither command takes an argument. Both root configs extend the shipped ones rather than copying them: the skill tells a consuming project to copy, this repository owns the originals, and a copy here would be the second home of every rule.

`.github/workflows/gates.yml` runs the same script on every push and pull request. Both gates run clean across this repository, and keeping them green is the point: a red gate on `main` teaches everyone to ignore it.

## Installing

`scripts/install.sh` writes the links and registers the hook. It is safe to re-run, and it never touches a name this repository does not own.

A skill is model-invoked: an agent reads a list of descriptions and decides whether to load one. That decision degrades as the list grows, and a subagent whose tool list omits `Skill` cannot load one at all. `scripts/skill-reminder.js` removes the decision for the cases a tool call identifies exactly. It runs on `PreToolUse`, names the skill once per category per session, and never blocks the call.

| Tool call | Skill named |
| --- | --- |
| Write or edit of a `.md` or `.mdx` file | `markdown-formatting` and `technical-writing` |
| Write or edit of `.vale.ini` or `styles/<Style>/<Rule>.yml` | `docs-linter` |
| A shell command that runs `vale` | `docs-linter` |
| A shell command that runs `git commit` | `commit-messages` |
| A shell command that creates or renames a branch | `branch-names` |

| Setting | Default | Effect |
| --- | --- | --- |
| `core.hooksPath` | unset | Set to `.githooks` to run the commit and branch gates |
| `ALLOW_SIGNOFF` | `0` | Set to `1` where the project runs DCO and needs `Signed-off-by` |
| `SKIP_BRANCH_CHECK` | `0` | Set to `1` for a push that has to go out under a non-conforming branch name |
| `CLAUDE_HOME` | `~/.claude` | Where `install.sh` writes the Claude Code links and the hook registration |
| `AGENTS_HOME` | `~/.agents` | Where `install.sh` writes the links Codex reads |
| `JUNIE_HOME` | `~/.junie` | Where `install.sh` writes the links Junie reads first |

| Symptom | Cause | Fix |
| --- | --- | --- |
| A commit is rejected for an attribution line | The agent adds one by default | Turn it off in the agent's settings |
| The commit gate never fires | `core.hooksPath` is unset in this clone | `git config core.hooksPath .githooks` |
| `vale: command not found` | Vale is a separate binary, not a package dependency | `brew install vale` |
| `markdownlint-cli2: command not found` | Same: a separate binary | `npx markdownlint-cli2`, or install it globally |
| An agent ignores the skills | Loading one is the model's decision, and a long skill list dilutes it | `scripts/install.sh`, which registers the reminder hook |
| A skill is missing from the list | The tool does not follow the symlinks in `.claude/skills` | Copy the directories instead of linking |
| The reminder hook never fires | It is registered but the session predates the registration | Start a new session; the hook is read at startup |
| A subagent ignores the skills | Its tool list omits `Skill`, so it cannot load one | Delegate that work to an agent that has `Skill` |
| A long dash reaches a file | Only the commit hook used to catch one | `vale --minAlertLevel=error --glob='!.claude/**' .` |

## Hard rules

- **English everywhere in files.** Code, prose, comments, commit messages. A chat reply follows the language the human used; a file never does.
- **Hyphen, never a long dash.** The commit hook rejects one in a message, and `Docs.LongDash` rejects one in any `.md` file the Vale gate reads.
- **No attribution line in a commit.** No `Co-Authored-By`, no `Generated with`, no session link. A coding agent adds these by default: turn that off in the agent's settings rather than letting the hook catch them every time.
- **An agent does not commit or push without permission for that task.** Prepare the change, then propose the message.

## Adding a skill

1. Create `<name>/SKILL.md`. The `description` states when to use the skill and, in one clause, when not to.
2. Keep the body under roughly 150 lines. Detail goes to `references/`, which loads only when the task needs it.
3. Ship executable code under `<name>/scripts/` and configuration under `<name>/assets/`. Copy `LICENSE` to `<name>/LICENSE.txt` and put the SPDX identifier in a `license:` field, so the packaged archive carries its terms.
4. Link it: `ln -s ../../<name> .claude/skills/<name>`.
5. Add a row to the table above, and a section to `SOURCES.md`.
6. Where the output is objectively checkable, add `<name>/evals/evals.json` with two or three realistic prompts and the assertions each one has to satisfy.
7. Package it: `scripts/package.sh <name>`.

One commit per skill. A commit that adds two skills says nothing useful in `git log --oneline`.

## Review before proposing a change

- The skill follows its own rules. A writing skill that hedges is evidence against itself.
- No fact is stated in two files. Where a copy is unavoidable, it says it is a copy and names the owner.
- Every added rule carries what breaks without it.
