# copydesk

Six skills that teach a coding agent to write documentation, Markdown, commits and branch names to one standard, and to record a demo video.

## Use it

```bash
scripts/install.sh
```

The script symlinks every skill into the directories that Claude Code, Codex and Junie read. It then registers a hook that names the right skill as you work. `scripts/package.sh <name>` builds `dist/<name>.skill` instead, for a harness that installs from an archive.

## What it does not do

- It does not write a document or a commit. The writing skills shape what an agent produces. Two skills ship scripts that produce output: `branch-names` builds a branch name, and `demo-video` records the video.
- It does not install Vale or `markdownlint-cli2`. Each gate needs its own binary.
- It does not enforce anything in another repository until that repository wires the hooks and the CI steps the skills describe. A skill alone is advice to the agent.

## Configuration

| Setting | Default | Effect |
| --- | --- | --- |
| `core.hooksPath` | unset | Set to `.githooks` to run the commit and branch gates |
| `ALLOW_SIGNOFF` | `0` | Set to `1` where the project runs DCO and needs `Signed-off-by` |
| `SKIP_BRANCH_CHECK` | `0` | Set to `1` for a push that has to go out under a non-conforming branch name |
| `CLAUDE_HOME` | `~/.claude` | Where `install.sh` writes the Claude Code links and the hook registration |
| `AGENTS_HOME` | `~/.agents` | Where `install.sh` writes the links Codex reads |
| `JUNIE_HOME` | `~/.junie` | Where `install.sh` writes the links Junie reads first |

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| A commit is rejected for an attribution line | The agent adds one by default | Turn it off in the agent's settings |
| The commit gate never fires | `core.hooksPath` is unset in this clone | `git config core.hooksPath .githooks` |
| `vale: command not found` | Vale is a separate binary, not a package dependency | `brew install vale` |
| `markdownlint-cli2: command not found` | Same: a separate binary | `markdown-formatting/scripts/lint-markdown.sh`, which falls back to a pinned `npx`, or install it globally |
| An agent ignores the skills | Loading one is the model's decision, and a long skill list dilutes it | `scripts/install.sh`, which registers the reminder hook |
| A skill is missing from the list | The tool does not follow the symlinks in `.claude/skills` | Copy the directories instead of linking |
| The reminder hook never fires | It is registered but the session predates the registration | Start a new session; the hook is read at startup |
| A subagent ignores the skills | Its tool list omits `Skill`, so it cannot load one | Delegate that work to an agent that has `Skill` |
| A long dash reaches a file | An editor's autocorrect or a model wrote it, and only the commit hook checked messages | `vale --minAlertLevel=error --glob='!.claude/**' .` |

## More

- [`technical-writing`](technical-writing/SKILL.md) - how a document reads: where a fact lives, sentence rules, comment discipline. Read it before writing prose into any file.
- [`markdown-formatting`](markdown-formatting/SKILL.md) - how a `.md` file is built: blank lines, headings, lists, fences, tables. Read it before writing or fixing Markdown.
- [`docs-linter`](docs-linter/SKILL.md) - the Vale gate behind the writing rules: config, rule files, the traps. Read it before adding the gate to a repository or tuning a rule.
- [`commit-messages`](commit-messages/SKILL.md) - Conventional Commits 1.0.0, ticket ids, breaking changes, the commit gate. Read it before writing or squashing a commit.
- [`branch-names`](branch-names/SKILL.md) - the type prefix, the ticket id, the slug, the length budget, the push gate. Read it before creating or renaming a branch.
- [`demo-video`](demo-video/SKILL.md) - a scripted Playwright demo of a web application, recorded to MP4 with an optional offline voice-over. Read it before recording a demo.
- [AGENTS.md](AGENTS.md) - the gates, the reminder hook, and the rules for changing a skill. Read it before changing anything here.
- [SOURCES.md](SOURCES.md) - the specification or article each skill is built on. Read it when a rule looks arbitrary.
- [LICENSE](LICENSE) - MIT-0. Copy it, vendor it, sell it; no attribution required.
