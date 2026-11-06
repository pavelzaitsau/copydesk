// Records a scripted browser demo as video, using Playwright's recordVideo. It adds the overlays
// a headless recording lacks: captions, title cards, a log panel, row highlights, a visible
// cursor. An optional voice-over paces the run by the length of each line: Kokoro by default, or
// one of the MLX engines in tts_lines.py, in English or Russian.
//
//   const demo = await startDemo({ chromium, selectors, out, lines, lang: 'en', voice: 'voxcpm' });  // a name from VOICES
//   await demo.page.goto(...); await demo.card('<h1>Title</h1>');
//   demo.mark();                                      // the video starts here (mix.py trims before it)
//   await demo.narrate('intro', { wait: true });
//   ...
//   await demo.finish({ any: 'extra fields for run.json' });
//
// The caller passes Playwright in, so this file needs no node_modules of its own.
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';

const OVERLAY_CSS = `
#demo-cap{position:fixed;left:24px;bottom:24px;z-index:2147483646;max-width:1100px;background:rgba(17,28,40,.93);color:#fff;
  font:500 22px/1.35 -apple-system,Helvetica,Arial,sans-serif;padding:16px 22px;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.3)}
#demo-cap b{color:#6fd3ef;font-weight:700;margin-right:8px}
#demo-card{position:fixed;inset:0;z-index:2147483647;background:#111c28;color:#fff;display:flex;flex-direction:column;justify-content:center;
  padding:0 160px;font:400 26px/1.5 -apple-system,Helvetica,Arial,sans-serif}
#demo-card h1{font-size:52px;line-height:1.15;margin:0 0 22px;font-weight:700}
#demo-card .k{color:#6fd3ef;font-size:22px;letter-spacing:.06em;text-transform:uppercase;margin-bottom:14px}
#demo-card li{margin:6px 0}
#demo-card code{font:24px Menlo,monospace;color:#ffd479;background:transparent!important;border:0!important;padding:0!important}
#demo-log{position:fixed;right:24px;bottom:24px;z-index:2147483646;width:640px;background:#0d1117;color:#c9d1d9;border-radius:10px;
  font:16px/1.5 Menlo,monospace;padding:14px 18px;box-shadow:0 6px 24px rgba(0,0,0,.35)}
#demo-log .t{color:#8b949e;font:600 15px -apple-system,Helvetica,sans-serif;margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em}
#demo-log .ok{color:#7ee787}#demo-log .no{color:#ffa657}
.demo-hl{outline:4px solid #f5a623!important;outline-offset:-2px;background:rgba(245,166,35,.16)!important}
#demo-cursor{position:fixed;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(245,166,35,.55);
  border:2px solid #f5a623;z-index:2147483647;pointer-events:none;transition:transform .12s}
#demo-cursor.down{transform:scale(1.7)}`;

// Runs in every document: a headless video shows no pointer, so draw one and pulse it on clicks.
const INIT = `(() => { const add = () => { if (document.getElementById('demo-cursor') || !document.body) return;
  const c = document.createElement('div'); c.id = 'demo-cursor'; c.style.left = '-50px'; c.style.top = '-50px'; document.body.appendChild(c);
  const s = document.createElement('style'); s.id = 'demo-style'; s.textContent = ${JSON.stringify(OVERLAY_CSS)}; document.head.appendChild(s); };
  document.addEventListener('DOMContentLoaded', add); window.addEventListener('load', add);
  document.addEventListener('mousemove', e => { const c = document.getElementById('demo-cursor'); if (c) { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; } }, true);
  document.addEventListener('mousedown', () => document.getElementById('demo-cursor')?.classList.add('down'), true);
  document.addEventListener('mouseup', () => document.getElementById('demo-cursor')?.classList.remove('down'), true); })()`;

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

// Engine name -> the languages it speaks, the class of its weights' licence, the licence's name, and its peak memory in GB
// together with Whisper, measured on an M5 Pro with 48 GB with tts_lines.py --takes 2 --report-peak.
// Kokoro runs in its own process: its figure is the larger of that process (1.7 GB) and Whisper alone. This table owns the licence and memory facts;
// references/engines.md repeats them. kokoro runs kokoro_lines.py in the Kokoro environment, the rest
// run tts_lines.py in the mlx-audio environment, which owns the model behind each name.
// Licence classes: 'clean' allows any use; 'conditional' allows commercial use under conditions
// (Drama 3: the licensee's revenue under USD 500k a year); 'noncommercial' forbids it.
export const ENGINES = {
  kokoro: { langs: ['en'], licence: 'clean', terms: 'Apache-2.0', peakGb: 2.6 },
  qwen3: { langs: ['en', 'ru'], licence: 'clean', terms: 'Apache-2.0', peakGb: 9.7 },
  voxcpm2: { langs: ['en', 'ru'], licence: 'clean', terms: 'Apache-2.0', peakGb: 9.8 },
  chatterbox: { langs: ['en', 'ru'], licence: 'clean', terms: 'MIT', peakGb: 6.2 },
  omnivoice: { langs: ['en', 'ru'], licence: 'noncommercial', terms: 'CC-BY-NC-4.0', peakGb: 5.2 },
  'fish-s2': { langs: ['en', 'ru'], licence: 'noncommercial', terms: 'Fish Audio Research License', peakGb: 18.1 },
  drama3: { langs: ['en', 'ru'], licence: 'conditional', terms: 'Fish Audio Community License', peakGb: 30.2 },
  higgs3: { langs: ['en', 'ru'], licence: 'noncommercial', terms: 'Higgs TTS 3 licence', peakGb: 12.2 },
  // Silence of a length set by the text, and a Whisper check that hears the line exactly: for tests
  // and evals on a machine without the models.
  fake: { langs: ['en', 'ru'], licence: 'clean', terms: 'none', peakGb: 0 },
};
const LOCALES = { en: 'en-GB', ru: 'ru-RU' };

// The voices to pick from, by language: name -> engine, the engine's own voice value, sex and the
// strength from the November 2026 blind pairwise vote. scripts/fit_votes.py writes the file from
// assets/voice-vote.json; edit the votes, never the list.
export const VOICES = JSON.parse(readFileSync(`${import.meta.dirname}/../assets/voices.json`, 'utf8'));
// The default voice per language; fit_votes.py --check fails unless each is in VOICES and runs on a 'clean' engine.
const DEFAULT_VOICE = JSON.parse(readFileSync(`${import.meta.dirname}/../assets/defaults.json`, 'utf8'));

// Synthesises every line before the recording starts, so each line's length is known.
// Returns { key: seconds }. Without a voice, estimates the time a viewer needs to read the line.
// The MLX environment's interpreter; every voice except Kokoro runs there, and so does Whisper.
export const MLX_PY = () => process.env.MLX_TTS_PY || `${homedir()}/.local/share/demo-tts/mlx/bin/python`;

export function synthesise(lines, { engine, lang, voice, speed = 1.0, takes = 1 }, dir) {
  // A key names <key>.wav and frames/<key>.jpg, and kokoro_lines.py prints "<key> <seconds>":
  // a space or a slash in a key breaks one of the three.
  // A line is a string, or { say, text }: the voice reads say, the Whisper check may match either.
  const say = (t) => (typeof t === 'string' ? t : t?.say);
  for (const [k, t] of Object.entries(lines)) {
    if (!/^[\w-]+$/.test(k)) throw new Error(`line key '${k}': use letters, digits, '_' or '-' only`);
    if (typeof say(t) !== 'string' || !say(t).trim()) throw new Error(`line ${k} has no text`);
  }
  if (!voice || voice === 'off') {
    return { len: Object.fromEntries(Object.entries(lines).map(([k, t]) => [k, Math.max(2, say(t).length / 15)])), failed: [] };
  }
  mkdirSync(dir, { recursive: true });
  writeFileSync(`${dir}/lines.json`, JSON.stringify(lines));
  if (engine === 'fake') return fakeLines(lines, dir, say);
  const mlx = MLX_PY();
  const tts = `${import.meta.dirname}/tts_lines.py`;
  let out;
  if (engine === 'kokoro') {
    const kokoro = process.env.KOKORO_PY || `${homedir()}/.local/share/kokoro-tts/.venv/bin/python`;
    writeFileSync(`${dir}/kokoro.json`, JSON.stringify(Object.fromEntries(Object.entries(lines).map(([k, t]) => [k, say(t)]))));
    execFileSync(kokoro, [`${import.meta.dirname}/kokoro_lines.py`, `${dir}/kokoro.json`, dir, voice, String(speed)],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] });
    // Kokoro has no Whisper of its own: the MLX environment checks its lines as it checks its own.
    out = execFileSync(mlx, [tts, `${dir}/lines.json`, dir, '--check-existing', '--lang', lang],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] });
  } else {
    out = execFileSync(mlx, [tts, `${dir}/lines.json`, dir, '--engine', engine, '--lang', lang,
      '--speed', String(speed), '--takes', String(takes), ...(voice === 'default' ? [] : ['--voice', voice])],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] });
  }
  const len = {};
  for (const row of out.trim().split('\n')) { const [k, s] = row.split(' '); len[k] = Number(s); }
  for (const k of Object.keys(lines)) if (!(len[k] > 0)) throw new Error(`no audio for line ${k}`);
  const report = existsSync(`${dir}/takes.json`) ? JSON.parse(readFileSync(`${dir}/takes.json`, 'utf8')) : {};
  return { len, failed: Object.keys(report).filter((k) => report[k].failed) };
}

// The fake engine: a silent 16 kHz WAV per line, 15 characters a second and at least 1 s, and a
// takes.json in which Whisper heard every line exactly.
function fakeLines(lines, dir, say) {
  const len = {};
  const report = {};
  for (const [k, t] of Object.entries(lines)) {
    const sec = Math.max(1, Math.round(say(t).length / 15 * 100) / 100);
    const n = Math.round(sec * 16000);
    const wav = Buffer.alloc(44 + n * 2);
    wav.write('RIFF', 0); wav.writeUInt32LE(36 + n * 2, 4); wav.write('WAVEfmt ', 8); wav.writeUInt32LE(16, 16);
    wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22); wav.writeUInt32LE(16000, 24); wav.writeUInt32LE(32000, 28);
    wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(n * 2, 40);
    writeFileSync(`${dir}/${k}.wav`, wav);
    len[k] = sec;
    // Word timings spread evenly over the line, as Whisper would report them.
    const ws = say(t).split(/\s+/).filter(Boolean);
    const words = ws.map((w, i) => ({ w, t: Math.round((sec * i / ws.length) * 100) / 100, e: Math.round((sec * (i + 1) / ws.length) * 100) / 100 }));
    report[k] = { best: 0, failed: false, takes: [{ sec, miss: 0, slow: false, heard: say(t), words }] };
  }
  writeFileSync(`${dir}/takes.json`, JSON.stringify(report, null, 1));
  return { len, failed: [] };
}

// The skill runs on an Apple Silicon Mac only. DEMO_VIDEO_PLATFORM=other pretends otherwise, for tests.
export function checkPlatform() {
  let arm = process.env.DEMO_VIDEO_PLATFORM ? process.env.DEMO_VIDEO_PLATFORM === 'arm64' : false;
  if (!process.env.DEMO_VIDEO_PLATFORM) {
    // sysctl tells the truth under Rosetta, where process.arch and uname -m report x86_64.
    try { arm = execFileSync('sysctl', ['-n', 'hw.optional.arm64'], { encoding: 'utf8' }).trim() === '1'; } catch { arm = false; }
  }
  if (!arm) throw new Error('demo-video runs on an Apple Silicon Mac only');
}

// Free memory in GB: the free, inactive, speculative and purgeable pages vm_stat reports.
// DEMO_VIDEO_FREE_MEM sets the figure, for tests.
export function freeMemoryGb() {
  if (process.env.DEMO_VIDEO_FREE_MEM) return Number(process.env.DEMO_VIDEO_FREE_MEM);
  const vm = execFileSync('vm_stat', { encoding: 'utf8' });
  const page = Number(/page size of (\d+) bytes/.exec(vm)[1]);
  const pages = (name) => Number((new RegExp(`Pages ${name}:\\s+(\\d+)`).exec(vm) || [0, 0])[1]);
  return ((pages('free') + pages('inactive') + pages('speculative') + pages('purgeable')) * page) / 1e9;
}

// Refuses an engine whose peak memory with Whisper, plus 2 GB, does not fit in free memory.
export function checkMemory(engine, lang) {
  const free = freeMemoryGb();
  const need = (e) => ENGINES[e].peakGb + 2;
  if (need(engine) <= free) return;
  // fake records silence: a test engine, never a suggestion.
  const fit = Object.keys(ENGINES).filter((e) => e !== 'fake' && ENGINES[e].langs.includes(lang) && need(e) <= free);
  throw new Error(`${engine} needs about ${need(engine).toFixed(1)} GB, ${free.toFixed(1)} GB are free; engines that fit: ${fit.join(', ') || 'none'}`);
}

// The purpose of the video decides which licences are allowed. 'client' is the default, the strictest.
export const PURPOSES = ['personal', 'team', 'client'];
export function checkLicence(engine, purpose = 'client', allowRestrictedLicence = false) {
  if (!PURPOSES.includes(purpose)) throw new Error(`purpose '${purpose}': use ${PURPOSES.join(', ')}`);
  const licence = ENGINES[engine].licence;
  if (licence === 'clean') return;
  if (purpose === 'client' && !allowRestrictedLicence) {
    throw new Error(`${engine} has a ${licence} licence and the video is for a client; pick a clean voice, or pass allowRestrictedLicence after the user agrees`);
  }
  if (purpose === 'team') {
    console.error(`demo-video: ${engine} has a ${licence} licence; work for an own team usually counts as commercial use`);
  }
}

// Turns startDemo's lang, engine and voice into the engine and the engine's own voice value.
// A voice from VOICES brings its own engine. 'default' with the default engine picks the
// language's default voice; 'default' with another engine keeps that engine's own default.
export function resolveVoice({ lang = 'en', engine = 'kokoro', voice = 'off' } = {}) {
  if (!(lang in LOCALES)) throw new Error(`resolveVoice: lang '${lang}': use ${Object.keys(LOCALES).join(' or ')}`);
  let voiceName = null;
  if (voice === 'default' && engine === 'kokoro') voice = DEFAULT_VOICE[lang];
  // Only without an explicit engine: with one, voice is that engine's own value, such as any Qwen3 speaker.
  if (engine === 'kokoro' && voice && voice !== 'off' && voice !== 'default' && !(voice in VOICES[lang]) && Object.values(VOICES).some((v) => voice in v)) {
    throw new Error(`resolveVoice: voice '${voice}' is not in the ${lang} list; use one of ${Object.keys(VOICES[lang]).join(', ')}`);
  }
  if (engine === 'kokoro' && voice && !['off', 'default'].includes(voice) && !(voice in VOICES[lang]) && !/^[ab][fm]_/.test(voice)) {
    throw new Error(`resolveVoice: no ${lang} voice '${voice}'; use one of ${Object.keys(VOICES[lang]).join(', ')}, or pass engine with its own voice value`);
  }
  if (voice in VOICES[lang]) {
    voiceName = voice;
    ({ engine, voice } = VOICES[lang][voiceName]);
  }
  if (!(engine in ENGINES)) throw new Error(`resolveVoice: engine '${engine}': use one of ${Object.keys(ENGINES).filter((e) => e !== 'fake').join(', ')}`);
  if (voice && voice !== 'off' && !ENGINES[engine].langs.includes(lang)) {
    throw new Error(`resolveVoice: ${engine} does not speak '${lang}'; pick an engine from ${
      Object.keys(ENGINES).filter((e) => e !== 'fake' && ENGINES[e].langs.includes(lang)).join(', ')}`);
  }
  if (engine === 'kokoro' && voice === 'default') voice = 'bm_fable';
  return { engine, voice, voiceName };
}

export async function startDemo({ chromium, selectors, out, lines = {}, lang = 'en', engine = 'kokoro', voice = 'off',
  speed = 1.0, takes = 1, width = 1920, height = 1080, locale, testIdAttribute,
  purpose = 'client', allowRestrictedLicence = false, allowFailedTakes = false, prepared } = {}) {
  if (!out) throw new Error('startDemo: out is required');
  if (!(lang in LOCALES)) throw new Error(`startDemo: lang '${lang}': use ${Object.keys(LOCALES).join(' or ')}`);
  let voiceName = null;
  // prepared: { len, engine, voice, failed } for lines already voiced into <out>/voice by the caller,
  // such as slides.mjs, which voices and checks them itself.
  if (prepared) ({ engine, voice } = prepared);
  else ({ engine, voice, voiceName } = resolveVoice({ lang, engine, voice }));
  const speaking = Boolean(prepared) || (voice && voice !== 'off');
  // The voice needs Apple Silicon; a silent demo records anywhere Playwright runs.
  if (speaking) checkPlatform();
  if (speaking && !prepared) {
    checkLicence(engine, purpose, allowRestrictedLicence);
    checkMemory(engine, lang);
  }
  locale ??= LOCALES[lang];
  mkdirSync(out, { recursive: true });
  const { len: clipLen, failed } = prepared ? { len: prepared.len, failed: prepared.failed || [] }
    : synthesise(lines, { engine, lang, voice, speed, takes }, `${out}/voice`);
  if (failed.length && !allowFailedTakes) {
    throw new Error(`Whisper heard these lines too far from their text: ${failed.join(', ')}; see ${out}/voice/takes.json`);
  }
  // Higgs TTS 3's Creator Use Grant asks a video on the creator's own channels to credit the model.
  if (speaking && !prepared && engine === 'higgs3') writeFileSync(`${out}/credits.txt`, "Voice: Boson AI's Higgs Audio (Higgs TTS 3).\n");
  if (testIdAttribute) selectors.setTestIdAttribute(testIdAttribute);

  const browser = await chromium.launch();
  // Many business UIs collapse below desktop width; record at full HD, one device pixel per pixel.
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1,
    recordVideo: { dir: out, size: { width, height } }, locale });
  await context.addInitScript(INIT);
  // The video starts when the page is created. Measured against the MP4, a line still lands about
  // 0.1 s after the picture it belongs to; a UI demo tolerates that.
  const t0 = Date.now();
  const page = await context.newPage();
  const since = () => (Date.now() - t0) / 1000;
  let startOffset = null;
  const clips = [];
  let busyUntil = 0;

  const ensureStyle = () => page.evaluate((css) => {
    if (!document.getElementById('demo-style')) {
      const s = document.createElement('style'); s.id = 'demo-style'; s.textContent = css; document.head.appendChild(s);
    }
  }, OVERLAY_CSS);
  const upsert = async (id, html) => {
    await ensureStyle();
    await page.evaluate(([id, html]) => {
      let el = document.getElementById(id);
      if (!el) { el = document.createElement('div'); el.id = id; document.body.appendChild(el); }
      el.innerHTML = html;
    }, [id, html]);
  };

  const demo = {
    page, context, browser, sleep,
    // The video's first useful frame. Call it once the page shows the first card or screen.
    mark() { startOffset = since(); },
    // Caption at the bottom left. `step` and `text` are HTML.
    caption: (step, text) => upsert('demo-cap', (step ? `<b>${step}</b>` : '') + text),
    // Full-screen title card over the page; `html` is trusted markup.
    async card(html, ms = 0) { await upsert('demo-card', html); if (ms) await sleep(ms); },
    uncard: () => page.evaluate(() => document.getElementById('demo-card')?.remove()),
    // Terminal-style panel at the bottom right; `lines` are plain text, `cls` is 'ok' or 'no'.
    logPanel: (title, lines, cls = '') => upsert('demo-log',
      `<div class="t">${escapeHtml(title)}</div>` + lines.map((l) => `<div class="${cls}">${escapeHtml(l)}</div>`).join('')),
    hideLog: () => page.evaluate(() => document.getElementById('demo-log')?.remove()),
    // Outlines every element matching `selector` whose text contains one of `texts`; returns the count.
    highlight: (texts, selector = 'tr') => page.evaluate(([texts, selector]) => {
      let n = 0;
      document.querySelectorAll(selector).forEach((el) => {
        if (texts.some((t) => el.innerText.includes(t))) { el.classList.add('demo-hl'); n++; }
      });
      return n;
    }, [texts, selector]),
    unhighlight: () => page.evaluate(() => document.querySelectorAll('.demo-hl').forEach((el) => el.classList.remove('demo-hl'))),
    async moveTo(locator) {
      const b = await locator.boundingBox();
      if (b) await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 18 });
    },
    async click(locator) { await demo.moveTo(locator); await sleep(250); await locator.click(); },
    // Starts line `key` once the previous line has finished, and logs its start for mix.py.
    // `wait` blocks until this line ends; `pad` is the pause after it.
    async narrate(key, { wait = false, pad = 600 } = {}) {
      if (!(key in clipLen)) throw new Error(`no line ${key}`);
      if (startOffset === null) throw new Error(`narrate('${key}') before mark(): mix.py would cut the line's start`);
      await demo.voiceDone();
      clips.push({ key, t: since(), len: clipLen[key] });
      busyUntil = Date.now() + clipLen[key] * 1000 + pad;
      if (wait) await demo.voiceDone();
    },
    async voiceDone() { const ms = busyUntil - Date.now(); if (ms > 0) await sleep(ms); },
    // Closes the browser (which writes the video) and writes run.json next to it. Waits for the
    // current line first: mix.py cuts the audio at endAt, so a line still playing would be lost.
    async finish(extra = {}) {
      await demo.voiceDone();
      const endAt = since();
      const video = page.video();
      await context.close();
      await browser.close();
      const run = { ...extra, video: video ? await video.path() : null, startOffset: startOffset ?? 0, endAt,
        lang, engine: speaking ? engine : null, voice: speaking ? voice : null, voiceName, purpose, allowRestrictedLicence,
        failedLines: failed, clips };
      writeFileSync(`${out}/run.json`, JSON.stringify(run, null, 2));
      return run;
    },
    // Closes without writing run.json, for error paths.
    async abort() { await context.close().catch(() => {}); await browser.close().catch(() => {}); },
  };
  return demo;
}
