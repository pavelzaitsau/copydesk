# Audiences, the gate and the final review

The brief names the audience. The audience decides what the video may say, which voices it may use and which files leave the run.

| Audience | What the video may say | `purpose` |
| --- | --- | --- |
| Personal | Anything | `personal` |
| Team | Internal detail. People and clients by name, with facts about them: what was said, decided, built or measured. A decision or a fact carries its source, never a verbatim quotation from an internal source. No personal assessment and no opinion, as below | `team` |
| Client | Only this client's own data and public data. No judgement of a person or a decision, no price, no other client, no internal dispute, no plan | `client` |

A team video names people and clients and states facts about them. A fact is what a person said, decided or built, or what happened on a client's project. The video carries no personal assessment and no opinion:

- No judgement of a person: of their skill, effort, speed or character, in praise or in blame. "Anna wrote the check" is a fact; "Anna is the only one who understands the check" is a judgement.
- No judgement of a decision or a piece of work, and no opinion the narrator states as its own: "a poor design", "the right call".
- A person's position on the subject stays when the script attributes it and a claim carries it. "Anna says the check belongs in a nightly job" stays; a position about another person does not.

Without this line, a video that names people turns into a performance review that the people named never see coming.

`purpose` also picks the voices: `demo-video/references/purpose.md` owns that rule.

## The gate for a client

The gate reads everything that leaves the run: the script, the slide text and diagram labels, the frames and voice lines of inserts, the VTT, `chapters.txt` and `sources.md`.

A separate agent reads those files and lists the disputed places, each with its file, its line and the rule it may break. `stages.md` says what stops 5 and 10 do with them.

The agent gets only the run's files and this table. It does not get the conversation, so it judges the output and not the intent. Its prompt is in `prompts.md`, "Client gate", together with the command for a harness without subagents.

**Without subagents.** The gate runs in a new session, and the skill stops until the user runs the command. `state.json` waits for `gate.jsonl`. A file without the last line `{"done": true}` is a failed gate, not a clean one: the run keeps waiting.

## The final review

The source rules in `research.md` are instructions, and an injected text can get around them. The final review checks the output instead: it does not trust the process.

At stop 10 a separate agent reads every file the audience gets (the table in `SKILL.md`) and searches for what must not be there:

- a judgement of a person or of a decision, or an opinion the narrator states as its own;
- a price, a rate or a contract term;
- in a client video, another client's name;
- an internal dispute or plan;
- a verbatim quotation from an internal source;
- the name of a private folder, channel or repository.

For `personal` the review only lists what it finds. For `team` and `client` each finding goes into the summary at stop 10, and the user decides.

When the user names a file of words that must never appear, one per line, the review also searches the delivered files for each, as a whole word, ignoring case. Each hit is a finding.

Accepted risk: the review catches what reached the output, not what went to the network during the run.
