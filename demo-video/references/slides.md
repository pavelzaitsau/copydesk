# Narrated slides

`scripts/slides.mjs` records a slide video the way `demo-kit.mjs` records a web demo: a browser shows each slide state while its paragraph speaks. `assets/slides-schema.json` is the input format; this page explains it. `evals/fixtures/sample-slides/` is a small deck that uses every part of it.

## The input

A deck is `slides.json` and one HTML page of slide states.

- **The page.** Every state is an element of 1920x1080 whose `id` is the state's id. Content that overflows its box or the state is refused, since the recording would crop it. The runner shows one state and hides the others. Set a minimum font size in the page's theme: the recording is a video, and small text blurs.
- **Paragraphs.** One voice line each, with an `id`, a `chapter`, a `speaker` and `text`, what the subtitles show. `say` is what the voice reads, with the pronunciation dictionary already applied; without it the voice reads `text`.
- **States.** A state names its `slide` and its `para`. It shows at the start of its paragraph, or at its `anchor`: a phrase of the paragraph's `say`. List the states of a paragraph in the order the voice reaches them; each anchor is found after the one before, and `phrase#2` takes the second occurrence. The first paragraph needs a state without an anchor. An anchor with a number, in digits or in words, ordinals such as "second" or "второй" included, is refused, and so is a Latin one in Russian, because Whisper writes both its own way.
- **Speakers.** Each speaker maps to a voice name from `assets/voices.json`, or to `{ engine, voice }`. Two speakers must be two people; `references/engines.md`, "Voices", says which voices are one speaker. `node scripts/voices.mjs --lang en --purpose client` lists the voices with their licence and whether they fit in memory now.
- **Speed and tempo.** `speed` is the engine's own setting at synthesis, `tempo` a speed-up after it, 0.8 to 1.3. Each is one number, or one per speaker, because two speakers may run on two engines.
- **Inserts.** A browser recording, a chapter of its own after the paragraph that ends a chapter. Its `app` must be in `apps`, the applications the brief named, with an `owner` and `demoData: true`: an insert clicks in the application, which is the one exception to reading only. Its `scenario` is a module that exports `async (kit) => {}`, speaks its `lines` with `kit.narrate` and resets its data in `finally`. Captions are off in an insert: the subtitles are the video's own track.

## The steps

| Command | Does |
| --- | --- |
| `--render` | A PNG of every state and `slides.pdf`, one page per slide in its last state |
| `--audition v1,v2` | The first two paragraphs per voice, at tempo 1.0 and 1.15, with each voice's engine, licence class and licence name; each voice is checked against the purpose and the free memory first |
| `--voice-only` | Voices and checks every paragraph; a paragraph Whisper heard too far from its text stops with exit code 2 |
| `--record [--chapter N]` | Records every chapter that is missing or changed, or chapter N only, counted from 0; joins once every chapter is in place |
| no flag | Render, voice, record and join |

Voicing is cached per paragraph by its text, voice and settings, and written after each paragraph, so an interrupted run resumes where it stopped. A change to `tempo` needs `--voice-only` again, which only re-applies the tempo. `--record` refuses a line whose text, voice or tempo changed since voicing: it would play the old audio under the new subtitles. A state's time comes from Whisper's word timings of the chosen take, aligned word by word with the `say`, so one misheard word still lands in its place. When Whisper heard nothing there, the time comes from the share of characters before the anchor. A state timed any way but by its own word is printed and written to `voice/takes.json` under `anchors`: check it in `sheet.jpg`.

Each chapter records on its own, so a failure or an edit costs one chapter. The join refuses a chapter older than the deck. `mix.py join` glues them: chapters inside the MP4, the VTT as a subtitle track a player can switch off, an MP3, and the loudness checked after the join.

## The output

`<name>.mp4`, `<name>.vtt`, `<name>.mp3`, `chapters.txt`, `timing.json` with each chapter's and paragraph's start, `sheet.jpg` with one frame per paragraph, `slides.pdf` from `--render`, and `credits.txt` when a voice asks for one. `voice/takes.json` holds every paragraph's takes and what Whisper heard.

Check `sheet.jpg`: each frame shows the state its paragraph talks about.
