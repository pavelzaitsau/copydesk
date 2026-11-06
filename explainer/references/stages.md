# Stages of an explainer run

Every run passes ten stages and five stops. A stop writes `state.json` and waits for the user. This file says what each stage writes, how it is reviewed and when it gives up.

## The state file

`state.json` holds the stage, the SHA-256 of `brief.md`, the answers given at each stop, and the name of any file a stage waits for:

```json
{"stage": 3, "brief": "9f2c...", "waiting": "stop-3", "answers": {"0": "confirmed"}}
```

- The same brief hash resumes from the files. A finished stage is never run again; stage 8 keeps every voiced paragraph whose cache key matches.
- A different brief on the same topic writes `<topic>/v2/`, so an earlier run stays intact.
- A variant in the other language reuses this run's research: `sources.md`, `notes/`, `gaps.md` and the answers of stop 3. It runs no new scan. Its stop 0 asks only how many voices and which engine, and it starts at stage 4 in `<run>/<lang>/`. It writes its own `script.md` straight in its language, never a translation. Its own `claims.md` keeps the ids, claims and sources, with the values in the forms its script uses. A second scan finds other sources, and the two videos then state different facts.
- An interrupted stage restarts from its own start. A stop of 2 or 8 loses at most that stage.

## Eval mode

An eval runs without a person. It starts from a confirmed `brief.md`, reads the answers to stops 0 and 3 from `answers.json` beside it, and ends after stage 4, or after stage 6 when the eval asks for the slides; stage 6 then runs its reviews like a normal run, without a stop. Each answer counts as the user's for that stop only. The memory check and the model download of stop 0 are skipped, since the run ends before any voice. The evals in `evals/evals.json` run this way.

## The budget

The brief picks a level. It caps the scan and the research, stage 3a included. Voicing and recording sit outside it; the brief names their estimate from `demo-video`.

| Level | Scan and research | Agents |
| --- | --- | --- |
| Quick | about 30 minutes | up to 5 |
| Normal | 1 to 2 hours | up to 10 |
| Deep | up to 4 hours | up to 20 |

Stages 2, 4, 6 and 9 each have 3 rounds. When the rounds run out without a pass, the run stops and asks the user what to do.

A harness without subagents runs every role as a sequential pass of the same session. The client gate is the exception: `audience.md` says how it runs there.

## Stop 0: the brief

The brief records only what the user says. No source is read at this stop: in open mode, an internal text in the context before the web phase breaks the order in `research.md`.

`brief.md` holds:

- the topic, the audience (`personal`, `team` or `client`, with the client's name), and 5 to 10 questions the video answers;
- the viewer, in two lines: `Viewer knows:` and `Viewer does not know:`. Every researcher and every review in `prompts.md` gets both lines as its persona, so stop 0 does not pass without them. For a personal video, `Viewer knows:` names the user and what they took part in, such as "the user, who was in the meeting of 4 November"; the script may then say "you", and no reviewer flags it;
- the language, the number of voices and each speaker's engine, by the three questions below; the voices themselves come at stop 7;
- the mode: internal, the default, or open, which adds the open web (`research.md`);
- the budget level and the run folder;
- the local folders and repositories to read, and any connected source to start from: for each an id, a type, the owner (the user or client X) and the read tools allowed;
- the applications an insert may record, if any: an id, a URL, the owner, and whether it holds only demo data. An insert clicks in the application, so only an application with demo data qualifies.

Three settings have defaults, and the brief asks about each one as its own question through the harness's question tool where it has one, the default first and marked:

| Question | Default | The other options |
| --- | --- | --- |
| How many voices? | One host | A host and an expert |
| Which language? | English | Russian |
| Which engine? | The engine of `demo-video`'s default voice for that language (`assets/defaults.json`) | Another engine from `voices.mjs` for that language, each labelled with its licence |

Stop 0 does not pass until `brief.md` records an answer to all three.

At this stop the skill also checks the platform and the place of `demo-video`. It offers only engines with voices in the video's language, from `node <demo-video>/scripts/voices.mjs --lang <lang> --purpose <purpose>`. The candidates for stop 7 are the voices of the chosen engines that the purpose allows and that fit in memory. The skill downloads their models and Whisper now, while the network is open:

```bash
node <demo-video>/scripts/voices.mjs --lang <lang> --prefetch <voice>,<voice>
```

After the brief, `demo-video`'s scripts run with `HF_HUB_OFFLINE=1`, so a model missing from the cache stops the run instead of reaching the network.

## Stages 1 and 2: scan and research

Stage 1 scans: it lists candidate sources per question in `sources.md`, with a date, a type and an owner. Stage 2 reads them from a queue without duplicates. A researcher per question writes `notes/<question>.md`, and an opponent then marks each finding and looks for what the notes missed. Both prompts are in `prompts.md`. For a "how" question the researcher collects the mechanism, step by step, not only the list of its parts.

`research.md` says what each mode may touch; in open mode the web phase runs first. Each phase gets up to 3 rounds or the budget, whichever ends first.

## Stop 3: gaps

`gaps.md` lists every question without an answer, every contradiction between sources, and every source the skill could not read: a paywall, a page closed to robots, a video without a transcript. The stop also states the amount of material.

The user then:

- picks the length, from 5 to 15 minutes, pauses included;
- decides each gap: drop it, say it aloud as open, or grant a source;
- may grant more sources.

In open mode, a new web source after the internal phase is not read: it goes into the gaps.

## Stage 3a: reading what stop 3 granted

One pass over the new resources from the remaining budget. Stop 3 then repeats for the new gaps only.

## Stage 4: the script

The stage writes `outline.md` first, by `explaining.md`: the throughline, seven lines per chapter, and the problem-answer table. Then `script.md`, `claims.md`, `lexicon.<lang>.md` and the specification of each diagram: its parts and the order in which the voice names them. An insert gets its scenario now, from the template in `demo-video/references/slides.md`: it opens only an application from the brief and resets its data in `finally`.

| Check | Who |
| --- | --- |
| Sentence length, stop phrases, quotations, claim marks, the expert's share, the word count | `lint_script.py` |
| The outline and the rules in `explaining.md`; one idea per chapter, each term explained at its first use | A reviewer agent |
| Each sentence says no more than its claim | The claim fidelity review in `prompts.md` |
| What the audience may hear | The gate in `audience.md` |
| The viewer can explain the mechanism back | The explain-back reader in `prompts.md`, from `script.md` alone |

Each finding goes back into the script, and the checks run again: up to 3 rounds. The two reviews from `prompts.md` pass by their scores, as "How the reviews gate the run" there says.

## Stop 5: the script

The user reads `script.md` and the scenario of each insert. For a client, the disputed places from the gate come with them. A place the user answers "no" to is cut, and its paragraph is rewritten. A place with no answer keeps the run waiting.

## Stage 6: slides

The slides follow `SKILL.md` and `slides.md`. `check_slides.py` passes before the render. Check every PNG from `--render`: no text overflows a box, no font is smaller than 32 px, each state differs from the last one where the voice expects it. Then run the mute viewer and the sync reviewer from `prompts.md`; both pass by their scores before stop 7. For a client, the gate reads the slide text and the diagram labels; disputed places go into the summary at stop 10.

## Stop 7: the voice

`slides.mjs --audition` voices the first 2 paragraphs of the script with each candidate voice from the brief, at two tempos; `demo-video/references/slides.md` has the details. Each voice is labelled with its engine, its licence class and its licence name. Offer only voices `voices.mjs` marks `allowed` for the purpose: for a client, a voice marked "needs the user's yes" is offered only after the user agrees to its licence in so many words. In a dialogue, two clones of one identity are refused.

The user picks a voice per speaker and a tempo. Both go into `slides.json`.

## Stage 8: voicing

`slides.mjs --voice-only` voices every paragraph and checks each take with Whisper. A paragraph with no passing take stops the run with exit code 2 and its id. Rewrite it, or respell a word in the lexicon, at most 2 times; then ask the user. A rewritten paragraph passes the linter, the claim check and the gate again, and goes into the summary at stop 10.

## Stage 9: recording

`slides.mjs --record` writes the MP4, the VTT, the MP3 and the chapters. Then check:

- the length against the target: up to 20% off passes, more is a question to the user;
- the loudness check `mix.py join` prints; it exits with code 1 when the mix is out of its range;
- `sheet.jpg`: one frame per chapter, each showing its paragraph's state;
- the viewer rating in `prompts.md` scores the video from `script.md` and `sheet.jpg`. It needs 4 or more. Up to 3 rounds.

## Stop 10: summary and delivery

The final review in `audience.md` runs first. The summary then lists every change after stop 5: disputed places on slides and inserts, paragraphs rewritten at stages 8 and 9, and changes after the viewer's rating. Each change already passed the linter, the claim check and the gate.

The user confirms or rolls back each change. A rolled-back rewrite returns the original text with its best take, marked "check by ear" in `voice/takes.json`. The chapters a change touches are recorded again and pass the gate; a second summary lists only them.

Then the skill delivers the files from the table in `SKILL.md`, names the words to check by ear, and offers to delete `private/`.
