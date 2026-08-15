# Sources

What each skill is built on, and where a rule came from when it was not invented here.

Every link was checked on 2026-08-14.

## technical-writing

| Source | What it gave |
| --- | --- |
| [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/), ASD, Brussels, Issue 9 (2025) | The sentence rules: active voice, one fact per sentence, present tense, sentence length, no hidden verbs. The specification's approved dictionary of roughly 900 words is deliberately not used, because it is aerospace vocabulary and bans most software terms. |
| [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), IETF, 1997 | The obligation keywords, and the rule that they are uppercase. |
| [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174), IETF, 2017 | The clarification that only the uppercase form carries the special meaning. |
| Michael Nygard, [Documenting Architecture Decisions](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions), 2011 | The ADR: context, decision, consequences, and the rule that an accepted record is superseded rather than edited. |
| [Mermaid](https://mermaid.js.org/) | The text diagram format the templates assume. |

The reader-first section, the one-home-per-fact rule, the comment tables, the README and runbook templates and the review checklist are not from a published source. They come from practice, and each carries the consequence of ignoring it rather than an appeal to authority.

## docs-linter

| Source | What it gave |
| --- | --- |
| [Vale](https://vale.sh/), documentation at [docs.vale.sh](https://docs.vale.sh) | The linter itself, the style and vocabulary layout, and the rule extension points used by the shipped rules. |
| [RE2](https://github.com/google/re2/wiki/Syntax) | The regular expression dialect Vale uses, which is why no rule may use lookahead or lookbehind. |

The config traps section is not documented upstream. Each entry was found by hitting it.

## commit-messages

| Source | What it gave |
| --- | --- |
| [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) | The message structure, the specification rules, breaking-change marking with `!` and the footer, and the rule that a change fitting two types is two commits. |
| [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) | The mapping from type to release: `feat` to minor, `fix` to patch, a breaking change to major. |
| [Angular commit convention](https://github.com/angular/angular/blob/main/contributing-docs/commit-message-guidelines.md) | The type list that Conventional Commits leaves open: `build`, `ci`, `docs`, `perf`, `refactor`, `test`, `chore`. |
| Tim Pope, [A Note About Git Commit Messages](https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html), 2008 | The 50-character target for the subject and the blank line before the body. |
| [commitlint](https://commitlint.js.org/) | The gate for the structural half of the rules. The shipped config extends `@commitlint/config-conventional`. |
| [Developer Certificate of Origin 1.1](https://developercertificate.org/) | Why `Signed-off-by` is the one attribution line worth keeping, and why the hook makes it opt-in rather than banning it outright. |

The ticket-id placement, the no-wrap body rule, the squash-merge rules and the attribution ban are local decisions, not part of any specification.

## branch-names

| Source | What it gave |
| --- | --- |
| [git check-ref-format](https://git-scm.com/docs/git-check-ref-format), git documentation | The characters and forms git itself refuses, which the skill defers to rather than copying. |
| [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) | The type list the prefix comes from, by way of the `commit-messages` skill. |
| [RFC 1035, section 2.3.1](https://www.rfc-editor.org/rfc/rfc1035#section-2.3.1), IETF, 1987 | The 63-character DNS label limit, which is what truncates a branch-derived preview environment name. |
| [Trunk Based Development](https://trunkbaseddevelopment.com/), Paul Hammant | The short-lived branch model the one-branch-one-ticket rule assumes. |

The length budget, the type prefix as a folder, the ticket-id placement and the ban on an owner prefix are local decisions. The case rule comes from hitting it: a case-insensitive filesystem collapses two names into one ref.

## markdown-formatting

<!-- vale Docs.Hedging = NO -->
<!-- A cited title is reproduced verbatim, so the hedge rule does not apply to it. -->

| Source | What it gave |
| --- | --- |
| [Basic writing and formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax), GitHub | The syntax the rules target, and the anchor-generation rule that makes a renamed heading break every link to it. |
| [Organizing information with tables](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-tables), GitHub | The table requirements: three hyphens per column, the blank line before the table, alignment colons, and escaping a literal pipe. |
| [markdownlint rules](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md), David Anson | The rule numbers and aliases behind every section, including MD055, MD056 and MD058 for tables. |
| David Anson, [A few common Markdown mistakes](https://gist.github.com/DavidAnson/006a6c2a2d9d7b21b025) | The failure list the skill is organised around: inconsistent heading style, missing blank lines around lists and fences, a fence with no language, and reversed link syntax. |

<!-- vale Docs.Hedging = YES -->

Turning MD013 and MD060 off, and the rule about when a table is the wrong shape, are local decisions.

## This repository

Written with the skills it publishes. `AGENTS.md` states the rule; the commit history is the evidence.
