---
name: demo-video
description: "Records a scripted browser demo of a running web application as an MP4. Playwright drives the UI at 1920x1080 with captions, title cards, a log panel, row highlights and a visible cursor. An optional offline voice-over in English (default) or Russian paces the run: Kokoro or one of seven MLX engines on Apple Silicon. ffmpeg mixes it in. Use when someone asks for a demo video, walkthrough video, narrated demo or scripted screen recording of a web app. Also use it to re-record an existing demo in another language, voice or engine. Do NOT use it to research a topic or write a script from scratch, to record the user's own screen or a desktop app, to make static screenshots, or to edit an existing video file."
license: MIT-0
allowed-tools: Read, Write, Edit, Bash
---

# demo-video: record a narrated browser demo

A demo video here is a script, not a screen capture. A Node script drives the application through Playwright, writes a WebM, and logs when each voice line starts. `mix.py` trims the WebM, places the voice lines and encodes the MP4. Re-recording after a UI or wording change is two commands: the scenario, then `mix.py`.

| File | Role |
| --- | --- |
| `scripts/demo-kit.mjs` | `startDemo()`: browser at 1920x1080 with video, overlays, narration timing, `run.json` |
| `scripts/kokoro_lines.py` | Synthesises all voice lines in one Kokoro process, prints each line's length |
| `scripts/tts_lines.py` | The same for the MLX engines; owns the model behind each engine name |
| `scripts/mix.py` | WebM plus voice lines to MP4; prints duration and loudness, writes a frame per line |
| `scripts/fit_votes.py` | Fits the voice vote and writes `assets/voices.json`, the list a demo picks from |
| `scripts/slides.mjs`, `scripts/voices.mjs` | A narrated slide video from `slides.json`, and the voices a purpose allows |

For slides with a finished script rather than a running application, read `references/slides.md` and skip the scenario below. A dialogue needs two voices of two different people; the English list may hold no such pair of men, so offer a woman and a man.

`<skill-dir>` below is the directory that holds this file. The scenario template in step 2 is the structure every demo copies.

## Prerequisites

- The application runs and its demo data is in place. A demo run changes data: it creates what it shows.
- Playwright and its Chromium in one `node_modules` folder (`npm ci`, then `npx playwright install chromium`). The scenario loads it with `createRequire('<dir>/package.json')('playwright')` and passes `chromium` and `selectors` to `startDemo`.
- Node 20.11 or later, `ffmpeg` and `ffprobe` on the path.
- An Apple Silicon Mac for a voice; a silent demo records anywhere Playwright runs.
- For a voice, the MLX environment: every voice except the Kokoro ones runs there, and so does the Whisper check. Once: `uv venv --python 3.12 ~/.local/share/demo-tts/mlx`, then install `mlx-audio==0.6.4 soundfile torch mlx-whisper` into it. `MLX_TTS_PY` overrides the interpreter. The first run of an engine downloads its model into `~/.cache/huggingface`.
- For a Kokoro voice such as `nicole`, the Kokoro environment as well: `brew install espeak-ng`, then a Python 3.11 virtual environment at `~/.local/share/kokoro-tts/.venv` with `kokoro`, `soundfile` and the spaCy model `en_core_web_sm` installed up front (spaCy's own download fails inside uv environments). `kokoro_lines.py` points `espeakng_loader` at Homebrew's espeak-ng, because the wheel's built-in path belongs to its build machine. `KOKORO_PY` overrides the interpreter.

Cloud voices (OpenAI and others) send the script to an external service; use them only with the user's approval.

### Voices

Pick a voice by name with `voice`; the name brings its engine. The list is the 3 strongest voices per language and sex in a blind pairwise vote, written by `scripts/fit_votes.py` to `assets/voices.json`:

<!-- fit_votes:voices -->
| Language | Male | Female |
| --- | --- | --- |
| `en` | `voxcpm` (default), `higgs3` | `ono_anna`, `sohee`, `nicole` |
| `ru` | `higgs3` | `serena` (default) |
<!-- /fit_votes -->

Licences differ by engine. Ask what the video is for and pass it as `purpose`: `references/purpose.md` says which voices each purpose allows. `references/engines.md` holds the engines, their licences, the setup and the memory each needs; `references/voice-vote.md` holds the vote behind this list. Every voice needs the MLX setup, Kokoro included, because the Whisper check runs there. Warn the user before a `team` video uses `higgs3`: Fish S2, Drama 3, Higgs and OmniVoice limit or forbid commercial use, and work for an own team usually counts as one. `voice: 'default'` takes the language's default, `'off'` records without audio. An engine's own voice value (any Kokoro voice, a WAV to clone) still works with `engine`, for experiments.

## Workflow

### 1. Write the storyboard

Agree the scenes before writing code. Per step: what the viewer sees, what the caption says, what the voice says. A demo of three to five steps runs two to three minutes. Each step proves one claim, and the last card states the result with numbers from the run.

Write voice lines for the ear. Keep the sentences short, and write numbers as words: "one hundred and eight euros ten", "сто восемь евро". Spell a product name the way a speaker says it: "engine-x" for `nginx`. In Russian, write `ё` where it belongs, because the engines read `е` as `е`. Keep captions for the eye: exact values, menu paths, ids.

A demo in two languages keeps one scenario and one table of text per language, as in the template below. Captions, cards and voice lines all come from that table, so a switch of `DEMO_LANG` switches all three.

### 2. Write the scenario

One `.mjs` file next to the application's other demo tooling:

```js
import { createRequire } from 'node:module';
const { startDemo, sleep } = await import('<skill-dir>/scripts/demo-kit.mjs');
const { chromium, selectors } = createRequire('<dir-with-playwright>/package.json')('playwright');

const out = process.argv[2];                                      // the output folder
const BASE = process.env.BASE_URL;                                // where the application runs
const LANG = process.env.DEMO_LANG || 'en';                       // 'en' or 'ru'
const T = {                                                       // all text, per language
  en: { title: 'Title', step1: 'Menu → Page: what happens', lines: { intro: 'This is ...', step1: '...' } },
  ru: { title: 'Заголовок', step1: 'Меню → Страница: что происходит', lines: { intro: 'Это ...', step1: '...' } },
}[LANG];
const demo = await startDemo({ chromium, selectors, out, lines: T.lines, lang: LANG,
  voice: process.env.VOICE || 'default' });                      // a name from Voices
const { page, caption, card, uncard, click, narrate, voiceDone } = demo;
try {
  await page.goto(BASE + '/start', { waitUntil: 'networkidle' });
  await card(`<div class="k">Product · topic</div><h1>${T.title}</h1>`);
  demo.mark();                                                    // the video starts here
  await sleep(800);                                               // a moment of silence first
  await narrate('intro', { wait: true, pad: 900 });
  await uncard();
  await caption('1', T.step1);
  await narrate('step1');                                         // speaks while the UI works
  await click(page.getByRole('button', { name: 'Save' }));
  await voiceDone();
  console.log(JSON.stringify(await demo.finish({ facts: 'shown in the video' })));
} catch (e) {
  await demo.abort();
  throw e;
} finally {
  resetApplication();                                             // yours: back to the starting state
}
```

`startDemo` options:

| Option | Default | Meaning |
| --- | --- | --- |
| `chromium`, `out` | required | Playwright's `chromium` export and the output folder |
| `selectors` | none | Playwright's `selectors` export; required with `testIdAttribute` |
| `lines` | `{}` | Voice lines by key: a string, or `{ say, text }` when the voice reads a respelling. A key is letters, digits, `_` or `-`, because it names the line's `.wav` and frame files |
| `purpose`, `allowRestrictedLicence` | `'client'`, `false` | `'personal'`, `'team'` or `'client'`; see `references/purpose.md`. The allowance comes only from the user |
| `lang` | `'en'` | Language of the voice: `'en'` or `'ru'`. An engine that does not speak it fails before the browser opens |
| `voice`, `speed` | `'off'`, `1.0` | A name from Voices, `'default'`, or `'off'`, which paces each line by reading time (15 characters per second, at least 2 s) |
| `engine` | `'kokoro'` | Only for an engine's own voice value; a name from Voices sets it, see `references/engines.md` |
| `takes`, `allowFailedTakes` | `1`, `false` | Takes per line for an MLX engine. Whisper checks every line; a line it heard too far from its text stops the run unless allowed, see `references/engines.md` |
| `width`, `height` | `1920`, `1080` | Viewport and video size |
| `locale` | `'en-GB'` or `'ru-RU'`, from `lang` | Browser locale |
| `testIdAttribute` | Playwright's `data-testid` | Attribute behind `getByTestId` |

The kit's calls:

| Call | Effect |
| --- | --- |
| `card(html, ms)` / `uncard()` | Full-screen dark title card; `.k` is the kicker line, `code` is highlighted |
| `caption(step, text)` | Caption box at the bottom left |
| `logPanel(title, lines, 'ok'\|'no')` / `hideLog()` | Terminal panel at the bottom right for evidence from logs or the database |
| `highlight(texts, selector = 'tr')` / `unhighlight()` | Outlines matching rows and returns the count, which belongs in `run.json`; `unhighlight` clears every outline |
| `moveTo(locator)` / `click(locator)` | Moves the drawn cursor before acting, so the viewer sees where |
| `mark()` | Sets the first frame of the video; call it once the first card is on screen, before the first `narrate` |
| `narrate(key, { wait, pad })` | Starts a line after the previous one ends; `wait` blocks until it ends, `pad` is the pause after it |
| `voiceDone()` | Waits until the current line ends, so the picture still matches the line |
| `finish(extra)` | Waits for the current line, closes the browser and writes `run.json`: `video`, `startOffset`, `endAt`, `lang`, `engine`, `voice`, `voiceName`, `purpose`, `allowRestrictedLicence`, `failedLines`, `clips`, plus the fields of `extra` |
| `abort()` | Closes the browser without writing `run.json`, for error paths |

Overlays live in the page. A navigation removes the caption, the card, the log panel and the outlines, and hides the drawn cursor until the next `moveTo`. Set them again after every `page.goto` or link that loads a new page.

Rules that came from failed takes:

- **Narration drives the pacing.** Every line is synthesised before the browser opens, so its length is known. `narrate` waits for the previous line, never cuts it. Put a `voiceDone()` before every navigation or card that the next line describes.
- **Wait on the application, not on time.** After an action, wait for the state the next scene shows: a status label, a row in the database, a log line. A fixed sleep shows an empty page on a slow run.
- **Prepare before recording.** Restarts, seeds and logins go before `startDemo` or behind a card. `mix.py` drops everything before `mark()`. Run long commands during the recording asynchronously; a synchronous one freezes the picture.
- **Show evidence, then claim.** Read the proof (log lines, row counts) during the run and put it on screen. Throw when the proof is missing, so no video claims what the run did not show.
- **Reset in `finally`.** Leave the application in its starting state even when a take fails. Otherwise the next take starts from the data the failed take left behind, and records it. `finally` does not run on Ctrl-C; reset on `SIGINT` too.

### 3. Record

```bash
DEMO_LANG=ru VOICE=serena node <scenario>.mjs <out-dir>   # writes <out-dir>/*.webm, voice/, run.json
python3 <skill-dir>/scripts/mix.py <out-dir> <name>.mp4 [--frames 5,30,60]
```

Keep the default 1920x1080 unless the user asks otherwise: many business UIs collapse below desktop width. A run with `voice: 'off'` gives an MP4 without audio.

### 4. Check before handing over

`mix.py` prints duration, size, mean and peak volume. It writes `frames/<key>.jpg` one second into each line, or into the middle of a line shorter than two seconds. Each `--frames` time adds `frames/t=<seconds>.jpg`. Open the frames and confirm that each one shows what its line says. Check these too:

- The loudness `mix.py` prints is close to the target of its `loudnorm` filter.
- The values in `run.json` (ids, counts, timings) match the captions and the final card.
- The first frame is the title card, not a blank page; the last frame is the result card.

An agent cannot listen to the audio. Whisper's check skips numbers, and Latin words in Russian, so tell the user which words to check by ear: names, abbreviations, numbers and Russian stress that the engine might misread. A run with `higgs3` writes `credits.txt`: put that line in the video's description. Fix a misreading with a respelling in the line's `say`, keeping the written form in `text`: Whisper writes the word its usual way, so a respelling in a plain line fails the check. Then re-record. The engines other than Kokoro sample at random, so a second take sounds different; re-record a take whose pace or tone is off.

### 5. Deliver

Give the MP4 path, its length and what was verified.
