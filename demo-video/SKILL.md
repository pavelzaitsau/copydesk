---
name: demo-video
description: "Records a scripted browser demo of a running web application as an MP4. Playwright drives the UI at 1920x1080 with captions, title cards, a log panel, row highlights and a visible cursor. An optional offline English voice-over (Kokoro) paces the run; ffmpeg mixes it in. Use when someone asks for a demo video, walkthrough video, narrated demo or scripted screen recording of a web app. Also use it to re-record an existing demo in another language or voice. Do NOT use it to record the user's own screen or a desktop app, to make slides or static screenshots, or to edit an existing video file."
license: MIT-0
allowed-tools: Read, Write, Edit, Bash
---

# demo-video: record a narrated browser demo

A demo video here is a script, not a screen capture. A Node script drives the application through Playwright, writes a WebM, and logs when each voice line starts. `mix.py` trims the WebM, places the voice lines and encodes the MP4. Re-recording after a UI or wording change is two commands: the scenario, then `mix.py`.

| File | Role |
| --- | --- |
| `scripts/demo-kit.mjs` | `startDemo()`: browser at 1920x1080 with video, overlays, narration timing, `run.json` |
| `scripts/kokoro_lines.py` | Synthesises all voice lines in one Kokoro process, prints each line's length |
| `scripts/mix.py` | WebM plus voice lines to MP4; prints duration and loudness, writes a frame per line |

`<skill-dir>` below is the directory that holds this file. The scenario template in step 2 is the structure every demo copies.

## Prerequisites

- The application runs and its demo data is in place. A demo run changes data: it creates what it shows.
- Playwright and its Chromium in one `node_modules` folder (`npm ci`, then `npx playwright install chromium`). The scenario loads it with `createRequire('<dir>/package.json')('playwright')` and passes `chromium` and `selectors` to `startDemo`.
- Node 20.11 or later, `ffmpeg` and `ffprobe` on the path.
- For a voice, the Kokoro environment. Check it with `~/.local/share/kokoro-tts/.venv/bin/python -c 'import kokoro, soundfile, espeakng_loader'`. Setup on macOS:
  1. `brew install espeak-ng`
  2. A Python 3.11 virtual environment at `~/.local/share/kokoro-tts/.venv` with `kokoro`, `soundfile` and the spaCy model `en_core_web_sm` installed up front (spaCy's own download fails inside uv environments).
  3. `kokoro_lines.py` points `espeakng_loader` at Homebrew's espeak-ng; the wheel's built-in path belongs to its build machine. On an Intel Mac, set `ESPEAK_PREFIX=/usr/local/opt/espeak-ng`. The script loads a macOS `.dylib`, so it does not run on Linux as shipped.
  4. `demo-kit.mjs` runs that environment's Python; set `KOKORO_PY` to use another interpreter.
  5. The first run downloads the model (`hexgrad/Kokoro-82M`, about 330 MB) into `~/.cache/huggingface`.

Kokoro speaks English only in this setup: voices starting with `a` are American, `b` British. The examples here use `bm_george` (British male). For another language, record with on-screen captions in that language and `voice: 'off'`. Cloud voices (OpenAI and others) send the script to an external service; use them only with the user's approval.

## Workflow

### 1. Write the storyboard

Agree the scenes before writing code. Per step: what the viewer sees, what the caption says, what the voice says. A demo of three to five steps runs two to three minutes. Each step proves one claim, and the last card states the result with numbers from the run.

Write voice lines for the ear. Keep the sentences short, and write numbers as words: "one hundred and eight euros ten". Spell a product name the way a speaker says it: "engine-x" for `nginx`. Keep captions for the eye: exact values, menu paths, ids.

### 2. Write the scenario

One `.mjs` file next to the application's other demo tooling:

```js
import { createRequire } from 'node:module';
const { startDemo, sleep } = await import('<skill-dir>/scripts/demo-kit.mjs');
const { chromium, selectors } = createRequire('<dir-with-playwright>/package.json')('playwright');

const out = process.argv[2];                                      // the output folder
const BASE = process.env.BASE_URL;                                // where the application runs
const LINES = { intro: 'This is ...', step1: '...' };             // key -> voice line
const demo = await startDemo({ chromium, selectors, out, lines: LINES, voice: process.env.VOICE || 'bm_george' });
const { page, caption, card, uncard, click, narrate, voiceDone } = demo;
try {
  await page.goto(BASE + '/start', { waitUntil: 'networkidle' });
  await card('<div class="k">Product · topic</div><h1>Title</h1>');
  demo.mark();                                                    // the video starts here
  await sleep(800);                                               // a moment of silence first
  await narrate('intro', { wait: true, pad: 900 });
  await uncard();
  await caption('Step 1', 'Menu → Page: what happens');
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
| `lines` | `{}` | Voice lines by key. A key is letters, digits, `_` or `-`, because it names the line's `.wav` and frame files |
| `voice`, `speed` | `'off'`, `1.0` | Kokoro voice and speed; `'off'` paces each line by reading time (15 characters per second, at least 2 s) |
| `width`, `height` | `1920`, `1080` | Viewport and video size |
| `locale` | `'en-GB'` | Browser locale |
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
| `finish(extra)` | Waits for the current line, closes the browser and writes `run.json`: `video`, `startOffset`, `endAt`, `voice`, `clips`, plus the fields of `extra` |
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
node <scenario>.mjs <out-dir>                     # writes <out-dir>/*.webm, voice/, run.json
python3 <skill-dir>/scripts/mix.py <out-dir> <name>.mp4 [--frames 5,30,60]
```

Keep the default 1920x1080 unless the user asks otherwise: many business UIs collapse below desktop width. A run with `voice: 'off'` gives an MP4 without audio.

### 4. Check before handing over

`mix.py` prints duration, size, mean and peak volume. It writes `frames/<key>.jpg` one second into each line, or into the middle of a line shorter than two seconds. Each `--frames` time adds `frames/t=<seconds>.jpg`. Open the frames and confirm that each one shows what its line says. Check these too:

- The mean volume is near -17 dB and the peak at or below -1.5 dB.
- The values in `run.json` (ids, counts, timings) match the captions and the final card.
- The first frame is the title card, not a blank page; the last frame is the result card.

An agent cannot listen to the audio. Tell the user which words to check by ear: names, abbreviations and numbers Kokoro might misread. Fix a misreading by respelling the word in `LINES`, then re-record.

### 5. Deliver

Give the MP4 path, its length and what was verified.
