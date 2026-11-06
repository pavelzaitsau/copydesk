---
name: explainer
description: "Turns a topic into a narrated explainer video podcast of 5 to 15 minutes, with one host by default, or a host and an expert: research from local files and connected sources (internal mode, the default) or also from the open web, a fact-checked script, slides with diagrams, an offline voice, subtitles and chapters, plus the sources and gaps behind every claim. English or Russian, on an Apple Silicon Mac. Use only when the user asks for an explainer video or podcast on a topic, with no script yet; invoke it explicitly. Do NOT use it to record a running application or slides with a finished script, which belong to demo-video, or to write an article."
license: MIT-0
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Agent
---

# explainer: a narrated explainer video on a topic

An explainer here is a research project that ends in a video. The skill owns the brief, the research, the script and its claims, the audience gate and the slides. `demo-video` owns the voice, the recording and the MP4; the skill hands it `slides.json` and the slide page and never records itself.

| File | Role |
| --- | --- |
| `references/stages.md` | Every stage: what it writes, how it is reviewed, when it stops |
| `references/research.md` | Internal and open mode, what each may read, cloning, untrusted content |
| `references/audience.md` | What each audience may hear, the gate, the final review |
| `references/explaining.md` | The outline, its throughline and problem-answer table, and the rules that make the script explain |
| `references/slides.md` | What a slide is for, and which type draws which content |
| `references/prompts.md` | The prompt of every researcher and reviewer agent, and how the reviews gate the run |
| `scripts/lint_script.py` | The script's measurable rules, the claim check and the length estimate |
| `scripts/check_slides.py` | Every figure on a slide is in `claims.md`; at most 30% of the states only print text |
| `scripts/build_deck.py` | The paragraphs of `slides.json` from `script.md` and `lexicon.<lang>.md` |
| `assets/theme.css`, `assets/slides-template.html` | The neutral theme and one example of each slide type |
| `assets/stop-phrases.<lang>.txt` | Openers without content, which the linter refuses |

`<skill-dir>` below is the directory that holds this file.

## Before the brief

- **The machine.** An Apple Silicon Mac: `sysctl -n hw.optional.arm64` prints 1. On any other machine say the skill does not run there, and stop.
- **demo-video.** Look for it in this order: `$DEMO_VIDEO_DIR`, the folder beside this skill, `~/.claude/skills/`, `~/.agents/skills/`, `~/.junie/skills/`. Without it, say how to install it, and stop.
- **Its setup.** The MLX environment with Whisper and Playwright in `demo-video/` (`npm install` there once). `node <demo-video>/scripts/voices.mjs --lang <lang> --purpose <purpose>` lists the voices this machine can run.

## The run

Ten stages and five stops. At a stop, write `state.json` (stage, the brief's hash) and wait for the user; never decide in their place. `references/stages.md` has every stage in detail.

| # | Stage | Writes |
| --- | --- | --- |
| 0 | Stop: the brief | `brief.md`: topic, audience, what the viewer knows and does not know, 5 to 10 questions; voices, language and engine, one host, English and the engine of `demo-video`'s default voice unless the user picks otherwise; budget, run folder, mode, sources and applications. Every model the run needs downloads now |
| 1-2 | Research: local and connected sources; the web too in open mode | `sources.md`, `web/`, `repos/`, `private/`, `notes/<question>.md` |
| 3 | Stop: gaps | `gaps.md`, the amount of material; the user picks the length, from 5 to 15 minutes, and may grant more resources |
| 3a | Reading what stop 3 granted | One pass from the remaining budget, then stop 3 again for the new gaps only |
| 4 | Script | `outline.md`, `script.md`, `claims.md`, `lexicon.<lang>.md`, the diagrams' specification |
| 5 | Stop: the script | The user reads `script.md`; for a client, the disputed places too |
| 6 | Slides | `slides.html`, `slides.json`, `slides.pdf` |
| 7 | Stop: the voice | An audition of 2 paragraphs per voice at two tempos, each voice labelled with its engine and licence |
| 8-9 | Voice and record | Through `demo-video`: `slides.mjs --voice-only`, then `--record` |
| 10 | Stop: summary and delivery | Every change after stop 5, then the files |

The run folder is the brief's, `~/explainer/<topic>/` by default. Resolve it first with `python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' <path>`, which works before the folder exists, so a symbolic link cannot hide where it points. Then refuse a folder inside a git repository with a remote, and a synced folder: `~/Desktop`, `~/Documents`, `~/Library/Mobile Documents/`, `~/Library/CloudStorage/`, `~/Dropbox/`. `references/stages.md` says how a run resumes.

## The script

`script.md` is written for the ear, straight in the target language, never translated:

```text
# Title

lang: ru

## Chapter title

[host] One paragraph, one voice line. A fact carries the mark of its claim [c3].

[expert] The next paragraph.
```

- **Explain, do not list** (`references/explaining.md`): one throughline, a hook from the research, a mechanism for every "how" question, a worked example with real numbers. One idea per chapter, every term explained at its first use, and the date of the research said at the start.
- **Every fact** carries a mark `[cN]` with a row in `claims.md`: id, claim, source, and the values (names, numbers, dates) the claim rests on, separated by `;`. The linter matches a value literally, so list every form the script uses, such as each case form of a Russian name.
- **Length** comes from the brief's target: words = (minutes minus pauses) x the language's pace, about 140 words a minute in English and 120 in Russian. Up to 20% off is fine.
- **Copyright**: retell sources; at most one quotation of up to 25 words per source, with its author. Draw diagrams anew; take no picture from the web.
- In a dialogue the host asks the listener's questions and sums up; the expert explains and speaks 60 to 80% of the words.

Run the linter after every draft; errors stop the stage:

```bash
python3 <skill-dir>/scripts/lint_script.py script.md claims.md --target-minutes 12 --outline outline.md --known CI,PR
```

`--known` takes every name, tool and acronym on the brief's `Viewer knows:` line, such as `CI,PR,Jira`: they cost the viewer nothing. The load budget is in `references/explaining.md`.

A reviewer agent then checks what the linter cannot, against `references/explaining.md`. The claim fidelity and explain-back reviews in `references/prompts.md` follow and gate the stage by their scores, with the audience gate in `references/audience.md`.

## The slides

Pick each type by `references/slides.md`: every chapter gets a diagram, and a slide never prints what the voice says. Copy the types from `assets/slides-template.html` into `slides.html` and inline `assets/theme.css`. Every state is a `<section class="slide">` of 1920x1080 with its own id; a slide that holds the screen longer than 40 seconds gets states, which light up one part of a diagram while the voice names it. Names and terms on a slide stay as written in the source; the lexicon changes only what the voice says.

Write `slides.json` without paragraphs. Before stop 7 picks the voices, `speakers` holds the default voice of the brief's engine as a placeholder, since `--render` checks it: `html`, `title`, `name`, `lang`, `purpose`, `speakers`, `tempo`, and `states`, each with its `id`, `slide`, `para` and an optional `anchor`. A paragraph's id is `c<chapter>p<n>`, two digits each: the third paragraph of chapter 2 is `c02p03`. An insert adds `apps` and `inserts`. Then fill the paragraphs:

```bash
python3 <skill-dir>/scripts/build_deck.py script.md lexicon.<lang>.md slides.json
python3 <skill-dir>/scripts/check_slides.py slides.html claims.md     # figures from claims; exit 1 on a problem
node <demo-video>/scripts/slides.mjs slides.json <run> --render      # PNGs and slides.pdf; check each one
```

`build_deck.py` also sets `version` and applies the lexicon to each anchor, keeping the written form in `anchorText`; to change an anchor later, edit `anchor`, and the next run takes it. An anchor is a phrase of the paragraph's text, without numbers, ordinals included, and in Russian without Latin. "One", "second" and a lexicon form such as "F R two" all fail, so anchor on the word beside them. `--render` refuses a state whose content overflows it. The mute viewer and the sync reviewer in `references/prompts.md` then read the PNGs. `demo-video/references/slides.md` has the format, inserts included.

## Voice and recording

```bash
node <demo-video>/scripts/slides.mjs slides.json <run> --audition <voice>,<voice>   # stage 7
node <demo-video>/scripts/slides.mjs slides.json <run> --voice-only             # stage 8
node <demo-video>/scripts/slides.mjs slides.json <run> --record                 # stage 9
```

`purpose` in `slides.json` is the audience: `personal`, `team` or `client`. At stage 8 a paragraph Whisper heard too far from its text stops the run with exit code 2 and its id. Stages 8 and 9, with their limits and the viewer's rating, are in `references/stages.md`.

## Delivery

The final review runs first: `references/audience.md`. Then stop 10 shows the summary of every change after stop 5; the user confirms or rolls back.

| File | Personal, team | Client |
| --- | --- | --- |
| `<name>.mp4`, `.vtt`, `.mp3`, `chapters.txt`, `slides.pdf` | Yes | Yes |
| `script.md` without marks | Yes | Yes |
| `claims.md`, `gaps.md` | Yes | No |
| `sources.md` | Yes | Public and the client's own only |
| `credits.txt`, when a voice asks for it | Yes | Yes |

Words to check by ear: names, terms, numbers and Russian stress. Publish nothing: the user does.
