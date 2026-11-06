# Explaining

A viewer who does not know the topic watches the video once and can then explain its mechanism back. The rules here serve that goal. Past runs failed it in two ways. The video listed facts where it had to explain a mechanism, and the chapters read as separate notes with no line that tied them together.

## The outline carries the explanation

Write `outline.md` before the script. It opens with the throughline: one sentence that every chapter serves. Without it, the chapters read as separate notes, and the viewer cannot tell which fact matters. Each chapter then gets seven lines:

```text
Throughline: A queue lets a shop accept every order of a sale, even when its workers cannot keep up.

## Why a sale breaks the shop
- Question: Why does a shop fail on its busiest day?
- Moves the throughline: shows the gap between the orders that arrive and the orders that are done.
- Problem: one server takes each order and finishes it before the next, so a spike times out.
- Picture: chart - orders a minute by day, with the sale day lit
- Example: the sale of March 2025, at 1,200 orders a minute (c2)
- New terms: spike
- Takeaway: The shop fails because it finishes each order before it takes the next.
```

- **Question** is in the viewer's words, not the source's.
- **Moves the throughline** says what this chapter adds to the throughline. A chapter that adds nothing to it is cut or merged.
- **Problem** is what goes wrong without the thing the chapter explains.
- **Picture** is the one diagram that carries the chapter, by type from `slides.md` (this folder). A chapter with no picture has no structure yet.
- **Example** is a real case from the research, with its values in `claims.md`.
- **New terms** are the coined terms in plain words that the chapter introduces, such as "gate" or "fold plan". The linter cannot find them, so it reads this line. It finds names, acronyms and identifiers itself, and counts them against the same budget. The budget is about 1.5 a minute over the whole video, and at most 4 in a chapter. Figures and dates have their own budget: about 1 a minute, at most 3 in a chapter. A 10-minute video then holds about 15 terms and names and 10 figures. Over budget is an error. Describe a name the video uses once instead of naming it, and keep only the figures the mechanism needs. In a past run, three scripts held 18 to 21 terms and names, and every reviewer scored their load lowest of all axes.
- **Takeaway** is one sentence the viewer keeps.

After the chapters, `outline.md` holds the problem-answer table. Each problem the video raises gets a row: the chapter that raises it, what answers it, the chapter that answers it, and the status.

```text
| Problem | Raised in | Answered by | In | Status |
| --- | --- | --- | --- | --- |
| A spike times out orders | chapter 1 | the queue holds them | chapter 2 | solved |
| A failed order is lost | chapter 1 | retries and dead letters | chapter 3 | partly |
| The warehouse packs too slowly | chapter 1 | nothing yet | chapter 3 | not built |
```

The status is `solved`, `partly`, `not built`, `pending` (in a change not merged yet) or `open question` (the people involved disagree). When it is not `solved`, the script says so in the chapter that presents the fix. Without the table, a viewer assumes that the new thing fixes every problem raised before it.

Two chapters earn their place in most videos. A results chapter says what the thing achieved where it was used, with numbers from the claims: "refining an epic took up to three weeks, now two or three days, by the team's own estimate". When nothing is measured yet, the chapter says so plainly. A closing chapter gives three things to keep, one sentence each, which the `summary` slide shows. In a past run, the version the user preferred had both.

## Rules for the script

Use a hypothetical case to run a mechanism that the claims describe on the running example: "Say someone deletes the epic tag from FR-1." Start it with "Say" or "Suppose", and give it no mark. The fact it rests on carries the mark in the next sentence. The claim fidelity reviewer does not flag the hypothetical itself.

These add to the rules in `SKILL.md`, "The script".

1. **A hook in the first two paragraphs.** The opening puts the viewer in the problem, then states a concrete, true fact from the research that makes it surprising. For example: "Ask an agent to change a service, and it reads one repository. Even the experts it never reads disagreed with each other: the same person gave two clients opposite answers three hours apart." A hook about the making of the video ("an agent read 13 meetings") is about the research, not the viewer. A reviewer scored one such hook 3 of 5. The hook carries a claim mark like any fact.
2. **A "how" question gets a mechanism.** When a question of the brief starts with "how", its chapter walks through cause and effect, step by step, and says what each step produces. A list of parts or products does not answer it. The researcher prompt in `prompts.md` collects the mechanism at stage 2 for this reason.
3. **Every mechanism ends in its outcome.** Say what the mechanism produces, and what happens when it fails.
4. **A worked example with real numbers.** At least one chapter computes something the viewer can check: a count, a cost, a before and after. Its values come from `claims.md`.
5. **A problem without an answer is said aloud.** A row of the problem-answer table that is `partly` or `not built` is said in the chapter that presents the fix.
6. **At most 3 named people.** A fourth person, or a second person with the first name of one already named, gets a role instead: "the platform lead". Each name is one more thing the viewer has to keep.
7. **Example before rule.** Give the concrete case with its real values first, then the general rule. "Order 4417 waited 9 seconds in the queue" before "the queue absorbs a spike".
8. **One running example.** Pick one concrete case in the first chapters, such as one order, one document or one request, and follow it through every chapter it fits. A new chapter then shows what happens to a case the viewer already knows.
9. **At most 6 paragraphs a chapter,** about 90 seconds. A longer chapter holds two ideas: split it, and give each half its own question.
10. **A term before its use.** Order the chapters so that no chapter leans on a term a later chapter explains. If two chapters need each other, the mechanism goes first.
11. **One number per sentence,** with what it compares to: "three of the twelve services still read the old schema" teaches; "three services" alone does not.
12. **Names and dates earn their place.** Describe or cut a client, a tool, a date or an identifier the viewer does not need for the mechanism. Each one counts against the term budget.

## The reviews

Two reviews check the explanation from the viewer's side. The explain-back reader reads `script.md` at stage 4, and the mute viewer reads the slides at stage 6. Their prompts and pass rules are in `prompts.md`, with the other reviews of the run.
