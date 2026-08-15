# AGENTS.md

Rules for any agent working in this repository.

## What this repository is

The README says what this repository is, and its More list names each skill with what it owns. Each top-level directory holding a `<skill>/SKILL.md` is one skill, and this file says how to change one.

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
.github/workflows/         the gates, on every push to main and every pull request
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

Each gate needs its own binary and is configured at the root, so neither command needs a config path. The root `.markdownlint-cli2.jsonc` extends the shipped config rather than copying it. Vale has no `extends`, so the root `.vale.ini` points `StylesPath` at the shipped styles and repeats the shipped settings, and says that it is a copy.

`.github/workflows/gates.yml` runs the same script on every push to `main` and every pull request. On a pull request it also runs the commit and branch hooks over what the pull request brings, because a clone without `core.hooksPath` skips them. Both gates run clean across this repository, and keeping them green is the point: a red gate on `main` teaches everyone to ignore it.

## Installing

`scripts/install.sh` writes the links and registers the hook. It is safe to re-run, and it never touches a name this repository does not own.

`scripts/skill-reminder.js` runs on `PreToolUse`, names the skill once per category per session, and never blocks the call. Its header says why a hook is needed at all.

| Tool call | Skill named |
| --- | --- |
| Write or edit of a `.md` or `.mdx` file | `markdown-formatting` and `technical-writing` |
| Write or edit of `.vale.ini`, or of `styles/<Style>/<Rule>.yml` below one | `docs-linter` |
| A shell command that runs `vale` | `docs-linter` |
| A shell command that runs `git commit` | `commit-messages` |
| A shell command that creates or renames a branch | `branch-names` |

The settings and the troubleshooting table are in `README.md`.

## Hard rules

- **English everywhere in files.** Code, prose, comments, commit messages. A chat reply follows the language the human used; a file never does.
- **Hyphen, never a long dash.** The commit hook rejects one in a message, and `Docs.LongDash` rejects one in any `.md` file the Vale gate reads.
- **No attribution line in a commit.** No `Co-Authored-By`, no `Generated with`, no session link. A coding agent adds these by default; `commit-messages/references/enforcement.md` says how to stop it.
- **An agent does not commit or push without permission for that task.** Prepare the change, then propose the message.

## Asking the human

This section is a copy. The owner is the maintainer's personal `~/.claude/CLAUDE.md`, which Codex and Junie do not read. Change both together.

Ask only when the answer changes what happens next. A question in jargon, or one with no options, costs the human a round trip to work out what the agent wants. An open question invites an answer the agent cannot act on.

- Write the question in plain language, in the language the human writes in. No jargon, no internal identifiers, and no file path unless the choice is about that file.
- One decision per question.
- Offer 2 to 4 answer options. Each one is a short label plus one sentence on what happens if the human picks it. Put the recommended option first and mark it.
- Use the harness's question tool where one exists, such as `AskUserQuestion` in Claude Code. Otherwise number the options, so a reply of one digit is a complete answer.

## Adding a skill

1. Create `<name>/SKILL.md`. The `description` states when to use the skill and, in one clause, when not to.
2. Keep the body under 160 lines. The body loads on every trigger, so each extra line costs tokens in every session that uses the skill. Detail goes to `references/`, which loads only when the task needs it.
3. Ship executable code under `<name>/scripts/` and configuration under `<name>/assets/`. Copy `LICENSE` to `<name>/LICENSE.txt` and put the SPDX identifier in a `license:` field, so the packaged archive carries its terms.
4. Link it: `ln -s ../../<name> .claude/skills/<name>`.
5. Add a line to the More list in `README.md`, and a section to `SOURCES.md`.
6. Where the output is objectively checkable, add `<name>/evals/evals.json`. Give it two or three realistic prompts, each with the assertions it has to satisfy.
7. Package it: `scripts/package.sh <name>`. The script packs only the files git tracks, so `git add` them first.

One commit per skill. A commit that adds two skills says nothing useful in `git log --oneline`.

## Review before proposing a change

- The skill follows its own rules. A writing skill that hedges is evidence against itself.
- No fact is stated in two files. Where a copy is unavoidable, it says it is a copy and names the owner.
- Every added rule carries what breaks without it.
