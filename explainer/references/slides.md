# Slides: what they are for and which type to use

The voice explains, and the slide shows what the voice cannot say. That is structure, containment, order in time, who talks to whom, a real file and a set of values. A slide that prints the sentences the voice says gives the viewer nothing new, and the viewer reads it instead of listening. `demo-video/references/slides.md` owns the format of `slides.json` and the page; this file owns what goes on a slide.

## Rules

- **Every chapter has at least one diagram:** the picture its line in `outline.md` names (`explaining.md`).
- **`list` and `thesis` states make at most 30% of the deck.** `check_slides.py` refuses a deck above it. A list is the last resort, for parallel items with no structure between them.
- **Dim what the voice is not naming.** In every state, the part the voice names carries `.on` and the parts it has not reached or has left carry `.dim`. A deck where every box stays at full strength has no focus, and the eye goes to whatever is brightest. The first deck the user preferred dimmed every part but one.
- **States follow the voice.** A part lights on the word that names it, with the state's anchor on that word. Items appear in the order the voice says them. Every part the voice names lights at some point; a part that never lights is a part the viewer never ties to the words.
- **The last state shows the result.** A diagram of a mechanism ends on what the mechanism produced, or says "no result yet". A diagram that stops at the last step leaves the viewer to guess the outcome.
- **An arrow reads as a sentence.** Read the source, the label and the target aloud: "the shop writes an order to the queue". If that sentence is false, the arrow is wrong. Two things that both follow from one source get two arrows from it, never a chain through one of them.
- **One diagram, one idea, except the map.** A later chapter that returns to an idea shows what changed, not the same boxes with new labels. The viewer reads a repeated picture as a repeated point. The `map` is the exception: one overview of the parts of the whole, which returns at the start of each chapter about one part, with that part lit and the rest dimmed. It tells the viewer where they are.
- **The kicker frames, and admits.** The line above a heading says what kind of claim the slide makes: "Rejected", "The new version · on a branch". When a slide simplifies or invents for illustration, the kicker or a note says so: "Simplified: 12 of 17 entities", "Illustration of the form, with invented paths".
- **Values on slides come from claims.** Every number, date and identifier on a slide is in `claims.md`, in the claim or in its values, the date on the title slide included. A date on a slide in another form than in the claim, such as "5 November" for 2026-11-05, goes into the values. A `code` or `artefact` state is exempt, since it quotes a real file, and so is an element with class `tick`, an axis scale rather than a fact.

`check_slides.py` checks the share of `list` and `thesis` states and the values, before the render:

```bash
python3 <skill-dir>/scripts/check_slides.py slides.html claims.md   # exit 1 on any problem
```

The mute viewer and the sync reviewer in `prompts.md` check the rest at stage 6.

## The types

Pick the type by the shape of the content, then copy it from `assets/slides-template.html`. `assets/theme.css` styles each one, and the comment above a type in either file says how to extend it.

| The content is | Type |
| --- | --- |
| A centre that 2 to 6 parts rely on | `hub`: a centre, up to 3 satellites above and 3 below, each link labelled with what the satellite takes |
| Parts inside a whole: a server, a folder, a team | `nest`: a box inside a box is a part of it, never a step after it |
| A stack where each level uses the one below | `layers` |
| The stages of a mechanism, 3 to 5, each with what it produces | `steps`, with the result in the last state |
| Steps in order, up to 5 in a row | `diagram`, with a label on each arrow; a longer chain goes in `.col` |
| Steps that repeat until a condition holds | `diagram` with a `loopback` bar back to an earlier box |
| Messages between people or systems | `sequence` |
| Events over time, 3 to 6 points | `timeline` |
| The parts of the whole the video returns to | `map`: a grid of 2 to 6 parts, one lit per chapter |
| Up to 8 real lines: a file tree, a configuration excerpt, a check's output, the files a change touched in `M`, `R`, `A` form | `artefact`, straight on the background, never retyped from memory |
| A longer file, a configuration, a command and its output | `code`: its real lines from the research, at most 12, never retyped from memory |
| Before and after, or two options | `compare`, with the same rows on both sides |
| Values to compare across items, or two measures of the same items | `chart`: a bar chart or a scatter in inline SVG, axes labelled in words |
| One sentence that carries a chapter | `thesis`, at most one per chapter, its key phrase in `.hl`; with its evidence under it, a `statement` |
| Who does what, in order: people, agents, tools | `diagram` of roles, each box a role and what it hands on |
| Parallel items with no structure | `list` |
| The topic and the date of the research; the takeaways | `title`; `summary` |

When no type fits, draw an inline SVG inside the state, as `chart` does. Set `width` and `height` equal to the `viewBox`: one unit is then one pixel, and the text sizes stay true. Take colours from classes in `theme.css`, since an SVG attribute does not read a CSS variable. Keep text at 32px or more.
