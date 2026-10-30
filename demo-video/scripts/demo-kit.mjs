// Records a scripted browser demo as video, using Playwright's recordVideo. It adds the overlays
// a headless recording lacks: captions, title cards, a log panel, row highlights, a visible
// cursor. An optional Kokoro voice-over paces the run by the length of each line.
//
//   const demo = await startDemo({ chromium, selectors, out, lines, voice: 'bm_george' });
//   await demo.page.goto(...); await demo.card('<h1>Title</h1>');
//   demo.mark();                                      // the video starts here (mix.py trims before it)
//   await demo.narrate('intro', { wait: true });
//   ...
//   await demo.finish({ any: 'extra fields for run.json' });
//
// The caller passes Playwright in, so this file needs no node_modules of its own.
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
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

// Synthesises every line before the recording starts, so each line's length is known.
// Returns { key: seconds }. Without a voice, estimates the time a viewer needs to read the line.
function synthesise(lines, voice, speed, dir) {
  // A key names <key>.wav and frames/<key>.jpg, and kokoro_lines.py prints "<key> <seconds>":
  // a space or a slash in a key breaks one of the three.
  for (const [k, t] of Object.entries(lines)) {
    if (!/^[\w-]+$/.test(k)) throw new Error(`line key '${k}': use letters, digits, '_' or '-' only`);
    if (typeof t !== 'string' || !t.trim()) throw new Error(`line ${k} has no text`);
  }
  if (!voice || voice === 'off') {
    return Object.fromEntries(Object.entries(lines).map(([k, t]) => [k, Math.max(2, t.length / 15)]));
  }
  mkdirSync(dir, { recursive: true });
  writeFileSync(`${dir}/lines.json`, JSON.stringify(lines));
  const python = process.env.KOKORO_PY || `${homedir()}/.local/share/kokoro-tts/.venv/bin/python`;
  const script = `${import.meta.dirname}/kokoro_lines.py`;
  const out = execFileSync(python, [script, `${dir}/lines.json`, dir, voice, String(speed)],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] });
  const len = {};
  for (const row of out.trim().split('\n')) { const [k, s] = row.split(' '); len[k] = Number(s); }
  for (const k of Object.keys(lines)) if (!(len[k] > 0)) throw new Error(`no audio for line ${k}`);
  return len;
}

export async function startDemo({ chromium, selectors, out, lines = {}, voice = 'off', speed = 1.0,
  width = 1920, height = 1080, locale = 'en-GB', testIdAttribute } = {}) {
  if (!out) throw new Error('startDemo: out is required');
  mkdirSync(out, { recursive: true });
  const clipLen = synthesise(lines, voice, speed, `${out}/voice`);
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
        voice: voice && voice !== 'off' ? voice : null, clips };
      writeFileSync(`${out}/run.json`, JSON.stringify(run, null, 2));
      return run;
    },
    // Closes without writing run.json, for error paths.
    async abort() { await context.close().catch(() => {}); await browser.close().catch(() => {}); },
  };
  return demo;
}
