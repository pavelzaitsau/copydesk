# copydesk

Five writing skills for coding agents, each shipping the gate that enforces it: documentation, Markdown, code comments, commit messages and branch names.

| Skill | Owns |
| --- | --- |
| `technical-writing` | How a document reads: where a fact lives, sentence rules, comment discipline |
| `markdown-formatting` | How a `.md` file is built: blank lines, headings, lists, fences, tables |
| `commit-messages` | Conventional Commits 1.0.0, ticket ids, breaking changes, the commit gate |
| `branch-names` | The type prefix, the ticket id, the slug, the length budget, the push gate |
| `docs-linter` | The Vale gate behind the writing rules: config, rule files, the traps |

Nothing here is tied to a product, a language or a codebase, and nothing here writes for you. A skill shapes what an agent produces; it does not produce it.

## Install

```bash
scripts/install.sh
```

The script symlinks every skill into the directories Claude Code, Codex and Junie read, then registers a hook that names the right skill as you work. `scripts/package.sh <name>` builds `dist/<name>.skill` instead, for a harness that installs from an archive.

## More

- [AGENTS.md](AGENTS.md) - the install detail, the gates, and the rules for changing a skill.
- `<skill>/SKILL.md` - each skill, standalone.
- [SOURCES.md](SOURCES.md) - the specification or article each skill is built on.
- [LICENSE](LICENSE) - MIT-0. Copy it, vendor it, sell it; no attribution required.
