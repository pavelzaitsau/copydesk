// Records a narrated slide video from slides.json and an HTML page of slide states, the way
// demo-kit.mjs records a web demo: a browser shows the states while the voice speaks.
// assets/slides-schema.json is the format; references/slides.md explains it.
//
//   node slides.mjs <slides.json> <out-dir>                  render, voice, record and join: the whole video
//   node slides.mjs <slides.json> <out-dir> --render         PNG of every state and slides.pdf
//   node slides.mjs <slides.json> <out-dir> --audition v1,v2 two paragraphs per voice, at two tempos
//   node slides.mjs <slides.json> <out-dir> --voice-only     voice and check every paragraph, no picture
//   node slides.mjs <slides.json> <out-dir> --record [--chapter N]   record from the voiced lines, then join
//
// Voicing is cached per paragraph, so a second run voices only what changed. A paragraph Whisper
// heard too far from its text stops the run with exit code 2 and its id, unless allowFailedTakes.
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { checkLicence, checkMemory, checkPlatform, ENGINES, MLX_PY, resolveVoice, sleep, startDemo, synthesise } from './demo-kit.mjs';

export const GAPS = { lead: 1.0, paragraph: 0.7, chapter: 1.5, tail: 2.0 };
const SCHEMA = JSON.parse(readFileSync(new URL('../assets/slides-schema.json', import.meta.url), 'utf8'));
const sha1 = (x) => createHash('sha1').update(typeof x === 'string' ? x : JSON.stringify(x)).digest('hex');
const readJson = (f, fallback) => (existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : fallback);

// ---- the deck ---------------------------------------------------------------------------------

export function loadDeck(file) {
  const deck = JSON.parse(readFileSync(file, 'utf8'));
  deck.base = dirname(resolve(file));
  deck.gaps = { ...GAPS, ...(deck.gaps || {}) };
  deck.lang ??= 'en';
  deck.purpose ??= 'client';
  deck.name ??= 'slides';
  deck.title ??= deck.name;
  deck.takes ??= 1;
  deck.states ??= [];
  deck.inserts ??= [];
  deck.apps ??= [];
  return deck;
}

// The subset of JSON Schema that slides-schema.json uses. Returns one line per violation.
export function validate(value, schema = SCHEMA, path = 'slides.json') {
  const out = [];
  const type = (v) => (Array.isArray(v) ? 'array' : v === null ? 'null' : Number.isInteger(v) ? 'integer' : typeof v);
  if (schema.oneOf) {
    const fits = schema.oneOf.filter((s) => !validate(value, s, path).length);
    if (fits.length !== 1) out.push(`${path}: ${fits.length ? 'matches more than one form' : 'has none of the allowed forms'}`);
    return out;
  }
  if ('const' in schema && value !== schema.const) out.push(`${path}: must be ${JSON.stringify(schema.const)}`);
  if (schema.enum && !schema.enum.includes(value)) out.push(`${path}: must be one of ${schema.enum.join(', ')}`);
  if (schema.type) {
    const t = type(value);
    const ok = schema.type === t || (schema.type === 'number' && t === 'integer');
    if (!ok) return [...out, `${path}: must be ${schema.type === 'object' ? 'an object' : schema.type === 'array' ? 'a list' : `a ${schema.type}`}`];
  }
  if (typeof value === 'number') {
    if (schema.minimum !== undefined && value < schema.minimum) out.push(`${path}: ${value} is below ${schema.minimum}`);
    if (schema.maximum !== undefined && value > schema.maximum) out.push(`${path}: ${value} is above ${schema.maximum}`);
  }
  if (typeof value === 'string' && schema.pattern && !new RegExp(schema.pattern).test(value)) out.push(`${path}: '${value}' does not match ${schema.pattern}`);
  if (Array.isArray(value)) {
    if (schema.minItems && value.length < schema.minItems) out.push(`${path}: needs at least ${schema.minItems} item`);
    if (schema.items) value.forEach((v, i) => out.push(...validate(v, schema.items, `${path}[${i}]`)));
  }
  if (type(value) === 'object') {
    for (const k of schema.required || []) if (!(k in value)) out.push(`${path}: '${k}' is required`);
    for (const [k, v] of Object.entries(value)) {
      const sub = schema.properties?.[k] ?? (typeof schema.additionalProperties === 'object' ? schema.additionalProperties : null);
      if (sub) out.push(...validate(v, sub, `${path}.${k}`));
    }
  }
  return out;
}

const norm = (s) => s.toLowerCase().replace(/ё/g, 'е').replace(/[‘’ʼ]/g, "'").match(/[\p{L}\p{N}']+/gu) || [];
const sayOf = (p) => p.say || p.text;
const perSpeaker = (x, speaker) => (typeof x === 'number' ? x : x?.[speaker]) ?? 1.0;
const tempoOf = (deck, speaker) => perSpeaker(deck.tempo, speaker);
const speedOf = (deck, speaker) => perSpeaker(deck.speed, speaker);

// The speaker behind a voice: a preset, or the reference clip a cloning engine copies.
export function identity({ engine, voice }) {
  const cloning = !['qwen3', 'kokoro', 'fake'].includes(engine);
  if (cloning && voice === 'default') return 'qwen3:ryan';
  if (cloning) return `clip:${sha1(readFileSync(voice))}`;
  return `${engine}:${voice}`;
}

export function speakerVoices(deck) {
  const out = {};
  for (const [speaker, v] of Object.entries(deck.speakers || {})) {
    out[speaker] = typeof v === 'string' ? resolveVoice({ lang: deck.lang, voice: v })
      : resolveVoice({ lang: deck.lang, engine: v.engine, voice: v.voice });
  }
  return out;
}

// Chapters in order: the paragraphs' chapters, and each insert as a chapter of its own.
export function chapters(deck) {
  const list = [];
  for (const p of deck.paragraphs) {
    if (!list.length || list.at(-1).title !== p.chapter || list.at(-1).kind !== 'slides') list.push({ title: p.chapter, kind: 'slides', paras: [] });
    list.at(-1).paras.push(p);
  }
  for (const ins of deck.inserts) {
    const at = list.findIndex((c) => c.kind === 'slides' && c.paras.at(-1).id === ins.after);
    list.splice(at + 1, 0, { title: ins.chapter, kind: 'insert', insert: ins,
      paras: Object.entries(ins.lines).map(([id, text]) => ({ id, text, say: text, speaker: ins.speaker, chapter: ins.chapter })) });
  }
  return list;
}

// The phrases among `phrases` that hold a number in digits or in words, by wer.py's closed list.
function numberPhrases(phrases, lang) {
  if (!phrases.length) return [];
  const flags = JSON.parse(execFileSync('python3', [`${import.meta.dirname}/wer.py`, '--has-number', lang], { input: JSON.stringify(phrases), encoding: 'utf8' }));
  return phrases.filter((_, i) => flags[i]);
}

// Where each state of a paragraph starts in its say, as a word index: 0 without an anchor; the
// n-th occurrence for 'phrase#n'; else the first occurrence after the previous anchor, or the
// first one before it when there is none after. -1: absent.
export function anchorIndices(para, states) {
  const said = norm(sayOf(para));
  const out = {};
  let from = 0;
  for (const s of states) {
    if (!s.anchor) { out[s.id] = 0; continue; }
    const want = norm(s.anchor.replace(/#\d+$/, ''));
    const n = /#(\d+)$/.exec(s.anchor);
    // Not after the previous anchor, but earlier: report that index, so the order check names it.
    const later = n ? findWords(said, want, Number(n[1])) : findWords(said, want, 1, from);
    const hit = later.found || n ? later : findWords(said, want);
    out[s.id] = hit.found ? hit.index : -1;
    if (hit.found) from = hit.index + 1;
  }
  return out;
}

export function checkDeck(deck) {
  const { base, ...data } = deck;
  const problems = validate(data);
  if (problems.length) throw new Error(`slides.json:\n  ${problems.join('\n  ')}`);
  if (!existsSync(resolve(deck.base, deck.html))) problems.push(`html '${deck.html}' not found`);
  const ids = new Set();
  const voices = (() => { try { return speakerVoices(deck); } catch (e) { problems.push(e.message); return {}; } })();
  const seen = new Map();
  for (const [speaker, v] of Object.entries(voices)) {
    const who = identity(v);
    if (seen.has(who)) problems.push(`speakers ${seen.get(who)} and ${speaker} are one voice (${who}); pick voices of two different people`);
    seen.set(who, speaker);
  }
  const allParas = [...deck.paragraphs, ...deck.inserts.flatMap((i) => Object.keys(i.lines).map((id) => ({ id, speaker: i.speaker, say: i.lines[id] })))];
  for (const p of allParas) {
    if (ids.has(p.id)) problems.push(`paragraph id '${p.id}' is used twice`);
    ids.add(p.id);
    if (!sayOf(p)?.trim()) problems.push(`paragraph ${p.id} has no text`);
    if (!(p.speaker in voices)) problems.push(`paragraph ${p.id}: speaker '${p.speaker}' is not in speakers`);
  }
  const order = Object.fromEntries(deck.paragraphs.map((p, i) => [p.id, i]));
  let last = -1;
  const byPara = {};
  const stateIds = new Set();
  for (const s of deck.states) {
    if (stateIds.has(s.id)) problems.push(`state id '${s.id}' is used twice`);
    stateIds.add(s.id);
    if (!(s.para in order)) { problems.push(`state ${s.id}: no paragraph '${s.para}'`); continue; }
    if (order[s.para] < last) problems.push(`state ${s.id} comes after a later paragraph`);
    last = Math.max(last, order[s.para]);
    if (s.anchor && deck.lang === 'ru' && /[a-z]/i.test(s.anchor)) problems.push(`state ${s.id}: anchor '${s.anchor}' holds Latin, which Whisper writes its own way in Russian`);
    (byPara[s.para] ||= []).push(s);
  }
  const first = deck.paragraphs[0];
  if (!(byPara[first.id] || []).some((s) => !s.anchor)) problems.push(`paragraph ${first.id} opens the video and needs a state without an anchor`);
  for (const [para, states] of Object.entries(byPara)) {
    const at = anchorIndices(deck.paragraphs[order[para]], states);
    let prev = -1;
    for (const s of states) {
      if (at[s.id] < 0) problems.push(`state ${s.id}: anchor '${s.anchor}' is not in the say of ${para}`);
      else if (at[s.id] < prev) problems.push(`state ${s.id}: its anchor comes before the previous state's in ${para}; list the states of a paragraph in the order the voice reaches them`);
      prev = Math.max(prev, at[s.id]);
    }
  }
  const anchors = deck.states.filter((s) => s.anchor);
  for (const a of numberPhrases(anchors.map((s) => s.anchor.replace(/#\d+$/, '')), deck.lang)) {
    problems.push(`anchor '${a}' holds a number, which Whisper writes its own way`);
  }
  for (const ins of deck.inserts) {
    const app = deck.apps.find((a) => a.id === ins.app);
    if (!app) problems.push(`insert ${ins.id}: app '${ins.app}' is not in apps, the apps of the brief`);
    else if (app.demoData !== true) problems.push(`insert ${ins.id}: app '${ins.app}' does not hold demo data only, and an insert clicks in it`);
    if (!existsSync(resolve(deck.base, ins.scenario))) problems.push(`insert ${ins.id}: scenario '${ins.scenario}' not found`);
    const ch = chapters({ ...deck, inserts: [] });
    if (!ch.some((c) => c.paras.at(-1).id === ins.after)) problems.push(`insert ${ins.id}: '${ins.after}' does not end a chapter; an insert is a chapter of its own`);
  }
  if (problems.length) throw new Error(`slides.json:\n  ${problems.join('\n  ')}`);
  return { voices, byPara };
}

// The n-th place in words where the anchor's words start, from index `from`, or found: false.
function findWords(words, anchor, n = 1, from = 0) {
  for (let i = from; i + anchor.length <= words.length; i++) {
    if (anchor.every((w, k) => words[i + k] === w) && --n === 0) return { found: true, index: i };
  }
  return { found: false };
}

// Word-level Levenshtein alignment: for each word of a, the index of the word of b it matched or
// replaced, or -1 where it was dropped. A misheard word ("cue" for "queue") still maps to its place.
export function align(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => Array.from({ length: b.length + 1 }, (_, j) => (i ? (j ? 0 : i) : j)));
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1), d[i - 1][j] + 1, d[i][j - 1] + 1);
  }
  const map = new Array(a.length).fill(-1);
  for (let i = a.length, j = b.length; i > 0 && j > 0;) {
    if (d[i][j] === d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)) map[--i] = --j;
    else if (d[i][j] === d[i - 1][j] + 1) i--;
    else j--;
  }
  return map;
}

// When a state shows, in seconds into its paragraph, divided by the tempo. `how` says where the time
// came from: 'start'; 'words', Whisper heard the anchor's word; 'aligned', Whisper heard another
// word in its place; 'share', the share of characters before the anchor, when Whisper heard nothing there.
export function anchorTime(deck, para, state, report) {
  if (!state.anchor) return { t: 0, how: 'start' };
  const tempo = tempoOf(deck, para.speaker);
  const take = report?.takes?.[report.best];
  const said = norm(sayOf(para));
  const index = anchorIndices(para, deck.states.filter((s) => s.para === para.id))[state.id];
  const span = norm(state.anchor.replace(/#\d+$/, '')).length;
  if (take?.words?.length && index >= 0) {
    const heard = take.words.flatMap((w) => norm(w.w).map((x) => ({ x, t: w.t })));
    const map = align(said, heard.map((h) => h.x));
    for (let k = index; k < index + span; k++) {
      if (map[k] < 0) continue;
      const exact = heard[map[k]].x === said[k];
      return { t: heard[map[k]].t / tempo, how: exact && k === index ? 'words' : 'aligned' };
    }
  }
  const before = index > 0 ? said.slice(0, index).join(' ').length : 0;
  return { t: ((take?.sec ?? 0) * before / Math.max(said.join(' ').length, 1)) / tempo, how: 'share' };
}

// ---- voice ------------------------------------------------------------------------------------

const python = () => MLX_PY();
const seconds = (wav) => Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', wav], { encoding: 'utf8' }).trim());
const mlxVersion = () => { try { return execFileSync(python(), ['-c', 'import importlib.metadata as m; print(m.version("mlx-audio"))'], { encoding: 'utf8' }).trim(); } catch { return '?'; } };

// What a voiced line depends on. A change to any part voices the line again.
function lineKey(deck, voices, p, mlx) {
  const v = voices[p.speaker];
  const clip = !['qwen3', 'kokoro', 'fake'].includes(v.engine) && v.voice !== 'default' ? identity(v) : '';
  return sha1([sayOf(p), p.text, v.engine, v.voice, clip, speedOf(deck, p.speaker), deck.takes, deck.lang, mlx]);
}
// What a finished line depends on: the voiced line and the tempo applied after it.
const finalKey = (deck, voices, p, mlx) => sha1([lineKey(deck, voices, p, mlx), tempoOf(deck, p.speaker)]);

function checkVoices(deck, voices) {
  for (const engine of new Set(Object.values(voices).map((x) => x.engine))) {
    checkLicence(engine, deck.purpose, deck.allowRestrictedLicence);
    checkMemory(engine, deck.lang);
  }
}

export function voice(deck, out, { only } = {}) {
  checkPlatform();
  const { voices } = checkDeck(deck);
  checkVoices(deck, voices);
  const dir = `${out}/voice`;
  mkdirSync(dir, { recursive: true });
  const cacheFile = `${dir}/cache.json`;
  const cache = readJson(cacheFile, {});
  const reportFile = `${dir}/takes.json`;
  const report = readJson(reportFile, {});
  const paras = chapters(deck).flatMap((c) => c.paras).filter((p) => !only || only.has(p.id));
  const mlx = mlxVersion();
  for (const speaker of Object.keys(voices)) {
    const todo = paras.filter((p) => p.speaker === speaker && (cache[p.id] !== lineKey(deck, voices, p, mlx) || !existsSync(`${dir}/raw/${p.id}.wav`)));
    if (!todo.length) continue;
    console.error(`voice: ${todo.length} paragraphs for ${speaker} (${voices[speaker].engine} ${voices[speaker].voice})`);
    // One paragraph at a time, so the cache survives an interruption with everything voiced so far.
    for (const p of todo) {
      const raw = `${dir}/raw-${speaker}`;
      const { failed } = synthesise({ [p.id]: { say: sayOf(p), text: p.text } },
        { engine: voices[speaker].engine, lang: deck.lang, voice: voices[speaker].voice, speed: speedOf(deck, speaker), takes: deck.takes }, raw);
      mkdirSync(`${dir}/raw`, { recursive: true });
      copyFileSync(`${raw}/${p.id}.wav`, `${dir}/raw/${p.id}.wav`);
      const takes = JSON.parse(readFileSync(`${raw}/takes.json`, 'utf8'));
      report[p.id] = { ...takes[p.id], speaker, failed: failed.includes(p.id) };
      cache[p.id] = lineKey(deck, voices, p, mlx);
      writeFileSync(cacheFile, JSON.stringify(cache, null, 1));
      writeFileSync(reportFile, JSON.stringify(report, null, 1));
    }
  }
  // Tempo after synthesis, on the whole line and without a pitch change; cheap, so always redone.
  const len = readJson(`${dir}/lengths.json`, {});
  const keys = readJson(`${dir}/keys.json`, {});
  for (const p of paras) {
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', `${dir}/raw/${p.id}.wav`, '-af', `atempo=${tempoOf(deck, p.speaker)}`, `${dir}/${p.id}.wav`]);
    len[p.id] = seconds(`${dir}/${p.id}.wav`);
    keys[p.id] = finalKey(deck, voices, p, mlx);
  }
  writeFileSync(`${dir}/lengths.json`, JSON.stringify(len, null, 1));
  writeFileSync(`${dir}/keys.json`, JSON.stringify(keys, null, 1));
  const failed = paras.filter((p) => report[p.id]?.failed).map((p) => p.id);
  if (Object.values(voices).some((v) => v.engine === 'higgs3')) writeFileSync(`${out}/credits.txt`, "Voice: Boson AI's Higgs Audio (Higgs TTS 3).\n");
  return { len, failed, report };
}

// ---- picture ----------------------------------------------------------------------------------

function playwright() {
  const dir = process.env.PLAYWRIGHT_DIR || resolve(import.meta.dirname, '..');
  if (!existsSync(`${dir}/node_modules/playwright`)) throw new Error(`no Playwright in ${dir}: run npm install there, or set PLAYWRIGHT_DIR`);
  const require = createRequire(`${dir}/package.json`);
  return { ...require('playwright'), version: require('playwright/package.json').version };
}

async function showState(page, ids, id) {
  await page.evaluate(([ids, id]) => {
    for (const s of ids) { const el = document.getElementById(s); if (el) el.style.display = s === id ? '' : 'none'; }
  }, [ids, id]);
}

// Shows each state in turn and checks it is an element of 1920x1080; calls each(state, element).
async function eachState(page, deck, states, each = async () => {}) {
  const ids = deck.states.map((s) => s.id);
  for (const s of states) {
    await showState(page, ids, s.id);
    const el = page.locator(`[id="${s.id}"]`);
    if (!(await el.count())) throw new Error(`slides html: no element with id ${s.id}`);
    const box = await el.boundingBox();
    if (!box) throw new Error(`slides html: #${s.id} is hidden by the page's own CSS`);
    if (Math.round(box.width) !== 1920 || Math.round(box.height) !== 1080) throw new Error(`slides html: #${s.id} is ${Math.round(box.width)}x${Math.round(box.height)}, not 1920x1080`);
    // Content that leaves its box or the state: overflow: hidden would crop it without a trace in the PNG.
    const over = await el.evaluate((root) => {
      const r = root.getBoundingClientRect();
      for (const e of [root, ...root.querySelectorAll('*')]) {
        const b = e.getBoundingClientRect();
        if (!b.width && !b.height) continue;
        const what = (e.textContent || '').trim().slice(0, 40);
        // Sideways for every box; downwards only for the state, since a tight line height lets glyphs
        // stand a few pixels below a visible box without harm.
        const down = e === root && e.scrollHeight > e.clientHeight + 1;
        if (getComputedStyle(e).display !== 'inline' && (e.scrollWidth > e.clientWidth + 1 || down)) return `text overflows its box: '${what}'`;
        if (b.left < r.left - 1 || b.right > r.right + 1 || b.top < r.top - 1 || b.bottom > r.bottom + 1) return `an element leaves the state: '${what}'`;
      }
      return null;
    });
    if (over) throw new Error(`slides html: #${s.id}: ${over}; shorten the text or split the state`);
    await each(s, el);
  }
}

async function openDeck(page, deck) {
  await page.goto(pathToFileURL(resolve(deck.base, deck.html)).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
}

export async function render(deck, out) {
  checkDeck(deck);
  const { chromium } = playwright();
  mkdirSync(`${out}/png`, { recursive: true });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    await openDeck(page, deck);
    await eachState(page, deck, deck.states, (s, el) => el.screenshot({ path: `${out}/png/${s.id}.png` }));
    // One PDF page per slide, in the slide's last state.
    const last = new Map();
    for (const s of deck.states) last.set(s.slide, s.id);
    // Inline images: a page set from a string sits on about:blank, which may not load file:// URLs.
    const imgs = [...last.values()].map((id) => `<img src="data:image/png;base64,${readFileSync(`${out}/png/${id}.png`).toString('base64')}">`).join('');
    const pdfPage = await browser.newPage();
    await pdfPage.setContent(`<style>@page{size:1920px 1080px;margin:0}body{margin:0}img{display:block;width:1920px;height:1080px;page-break-after:always}</style>${imgs}`, { waitUntil: 'load' });
    const broken = await pdfPage.evaluate(() => [...document.images].filter((i) => i.naturalWidth !== 1920).length);
    if (broken) throw new Error(`slides.pdf: ${broken} pages without their image`);
    await pdfPage.pdf({ path: `${out}/slides.pdf`, width: '1920px', height: '1080px', printBackground: true });
  } finally { await browser.close(); }
  console.error(`render: ${deck.states.length} states in ${out}/png, ${out}/slides.pdf`);
}

const part = (out, k) => `${out}/chapters/${String(k).padStart(2, '0')}`;

// What a recorded chapter depends on: its place, its lines, its states, the page or the scenario.
function chapterKey(deck, list, k, keys) {
  const ch = list[k];
  const source = ch.kind === 'insert' ? resolve(deck.base, ch.insert.scenario) : resolve(deck.base, deck.html);
  return sha1([k, k === list.length - 1, ch.title, ch.kind, ch.paras.map((p) => keys[p.id]), deck.states.filter((s) => ch.paras.some((p) => p.id === s.para)),
    startState(deck, ch)?.id, deck.gaps, sha1(readFileSync(source)), ch.kind === 'insert' ? deck.apps.find((a) => a.id === ch.insert.app) : null]);
}

// The state on screen when a chapter of slides opens: its first paragraph's own state without an
// anchor; when that paragraph has none, the last state of an earlier paragraph, so a slide carried
// over from the previous chapter stays.
export function startState(deck, ch) {
  if (ch.kind !== 'slides') return null;
  const own = deck.states.find((s) => s.para === ch.paras[0].id && !s.anchor);
  if (own) return own;
  const order = Object.fromEntries(deck.paragraphs.map((p, i) => [p.id, i]));
  const at = order[ch.paras[0].id];
  return deck.states.filter((s) => order[s.para] < at).at(-1) ?? deck.states[0];
}

async function recordChapter(deck, out, list, k, voiced) {
  const ch = list[k];
  const { chromium, version } = playwright();
  const dir = part(out, k);
  rmSync(dir, { recursive: true, force: true });
  rmSync(`${dir}.mp4`, { force: true });
  mkdirSync(`${dir}/voice`, { recursive: true });
  for (const p of ch.paras) symlinkSync(resolve(`${out}/voice/${p.id}.wav`), `${dir}/voice/${p.id}.wav`);
  const len = Object.fromEntries(ch.paras.map((p) => [p.id, voiced.len[p.id]]));
  const demo = await startDemo({ chromium, out: dir, lang: deck.lang, purpose: deck.purpose,
    allowRestrictedLicence: deck.allowRestrictedLicence, prepared: { len, engine: 'slides', voice: 'speakers' } });
  const g = deck.gaps;
  const anchors = {};
  try {
    if (ch.kind === 'insert') {
      const app = deck.apps.find((a) => a.id === ch.insert.app);
      if (app.url) await demo.page.goto(app.url, { waitUntil: 'load' });
      demo.mark();
      await sleep(g.chapter * 1000 / 2);
      // An insert speaks through the kit, without captions: the subtitles are the video's own track.
      const mod = await import(pathToFileURL(resolve(deck.base, ch.insert.scenario)).href);
      await mod.default({ ...demo, caption: async () => {}, app });
      await demo.voiceDone();
    } else {
      const ids = deck.states.map((s) => s.id);
      await openDeck(demo.page, deck);
      const mine = deck.states.filter((s) => ch.paras.some((p) => p.id === s.para));
      await eachState(demo.page, deck, mine);
      await showState(demo.page, ids, startState(deck, ch).id);
      demo.mark();
      await sleep((k === 0 ? g.lead : g.chapter / 2) * 1000);
      for (const [i, p] of ch.paras.entries()) {
        const timers = [];
        for (const s of deck.states.filter((x) => x.para === p.id)) {
          const { t, how } = anchorTime(deck, p, s, voiced.report[p.id]);
          if (s.anchor) anchors[s.id] = { para: p.id, t: Math.round(t * 100) / 100, how };
          if (t <= 0) await showState(demo.page, ids, s.id);
          else timers.push(setTimeout(() => showState(demo.page, ids, s.id).catch(() => {}), t * 1000));
        }
        await demo.narrate(p.id, { wait: true, pad: (i + 1 < ch.paras.length ? g.paragraph : 0) * 1000 });
        timers.forEach(clearTimeout);
      }
    }
    await sleep((k === list.length - 1 ? g.tail : g.chapter / 2) * 1000);
    await demo.finish({ chapter: ch.title, playwright: version, anchors });
  } catch (e) { await demo.abort(); throw e; }
  execFileSync('python3', [`${import.meta.dirname}/mix.py`, dir, `${dir}.mp4`], { stdio: ['ignore', 'ignore', 'inherit'] });
  // Anchors timed from anything but the anchor's own word: a warning in the take report.
  const loose = Object.entries(anchors).filter(([, a]) => a.how !== 'words');
  for (const [id, a] of loose) console.error(`record: state ${id} timed by ${a.how}, at ${a.t} s into ${a.para}; check it in sheet.jpg`);
  if (loose.length) {
    const file = `${out}/voice/takes.json`;
    const report = readJson(file, {});
    for (const [id, a] of loose) (report[a.para].anchors ||= {})[id] = { t: a.t, how: a.how };
    writeFileSync(file, JSON.stringify(report, null, 1));
  }
  return `${dir}.mp4`;
}

const stamp = (x) => `${String(Math.floor(x / 3600)).padStart(2, '0')}:${String(Math.floor(x % 3600 / 60)).padStart(2, '0')}:${(x % 60).toFixed(3).padStart(6, '0')}`;

// The voiced lines, checked against the deck: a line whose text, voice or tempo changed after
// voicing would play the old audio under new subtitles.
function voicedLines(deck, out, list) {
  const { voices } = checkDeck(deck);
  const dir = `${out}/voice`;
  if (!existsSync(`${dir}/lengths.json`)) throw new Error('no voiced lines: run --voice-only first');
  const voiced = { len: readJson(`${dir}/lengths.json`), keys: readJson(`${dir}/keys.json`, {}), report: readJson(`${dir}/takes.json`, {}) };
  const mlx = mlxVersion();
  const stale = list.flatMap((c) => c.paras).filter((p) => !(p.id in voiced.len) || voiced.keys[p.id] !== finalKey(deck, voices, p, mlx)).map((p) => p.id);
  if (stale.length) throw new Error(`not voiced, or changed since voicing: ${stale.join(', ')}; run --voice-only, which voices only these`);
  return voiced;
}

// Records every chapter that is missing or changed, or chapter N (counted from 0) only, then joins
// when every chapter is in place.
export async function record(deck, out, { chapter } = {}) {
  checkPlatform();
  const list = chapters(deck);
  if (chapter !== undefined && !(chapter >= 0 && chapter < list.length)) throw new Error(`--chapter ${chapter}: the deck has chapters 0 to ${list.length - 1}`);
  const voiced = voicedLines(deck, out, list);
  for (const [k, ch] of list.entries()) {
    const key = chapterKey(deck, list, k, voiced.keys);
    const fresh = existsSync(`${part(out, k)}.mp4`) && readJson(`${part(out, k)}.key.json`, {}).key === key;
    if (chapter !== undefined ? k !== chapter : fresh) continue;
    console.error(`record: chapter ${k} ${ch.title}`);
    await recordChapter(deck, out, list, k, voiced);
    writeFileSync(`${part(out, k)}.key.json`, JSON.stringify({ key }));
  }
  const missing = staleChapters(deck, out, list, voiced.keys);
  if (chapter !== undefined && missing.length) {
    console.error(`record: chapter ${chapter} done; still to record before the join: ${missing.join(', ')}`);
    return null;
  }
  return join(deck, out, list);
}

function staleChapters(deck, out, list, keys) {
  return list.map((_, k) => k).filter((k) => !existsSync(`${part(out, k)}.mp4`) || readJson(`${part(out, k)}.key.json`, {}).key !== chapterKey(deck, list, k, keys));
}

// Glues the chapter MP4s: chapters and subtitles from each chapter's run.json, loudness checked.
export function join(deck, out, list = chapters(deck)) {
  const stale = staleChapters(deck, out, list, readJson(`${out}/voice/keys.json`, {}));
  if (stale.length) throw new Error(`chapters ${stale.join(', ')} are missing or older than the deck: record them`);
  const parts = list.map((_, k) => `${part(out, k)}.mp4`);
  const vtt = ['WEBVTT', ''];
  const marks = [];
  const timing = { chapters: [], paragraphs: {} };
  let offset = 0;
  for (const [k, ch] of list.entries()) {
    const run = JSON.parse(readFileSync(`${part(out, k)}/run.json`, 'utf8'));
    marks.push({ title: ch.title, start: offset });
    timing.chapters.push({ title: ch.title, start: Math.round(offset * 1000) / 1000 });
    for (const c of run.clips) {
      const p = ch.paras.find((x) => x.id === c.key);
      const start = offset + c.t - run.startOffset;
      timing.paragraphs[c.key] = { start: Math.round(start * 1000) / 1000, length: c.len };
      const sentences = p.text.split(/(?<=[.!?…])\s+/).filter(Boolean);
      const size = sentences.reduce((n, s) => n + s.length, 0);
      let t = start;
      for (const s of sentences) {
        const e = t + c.len * s.length / size;
        vtt.push(`${stamp(t)} --> ${stamp(e)}`, s, '');
        t = e;
      }
    }
    offset += seconds(parts[k]);
  }
  timing.total = Math.round(offset * 1000) / 1000;
  writeFileSync(`${out}/${deck.name}.vtt`, vtt.join('\n'));
  writeFileSync(`${out}/chapters.json`, JSON.stringify(marks, null, 1));
  writeFileSync(`${out}/chapters.txt`, marks.map((m) => `${stamp(m.start).slice(0, 8)} ${m.title}`).join('\n') + '\n');
  writeFileSync(`${out}/timing.json`, JSON.stringify(timing, null, 1));
  execFileSync('python3', [`${import.meta.dirname}/mix.py`, 'join', `${out}/${deck.name}.mp4`, '--parts', ...parts,
    '--chapters', `${out}/chapters.json`, '--vtt', `${out}/${deck.name}.vtt`, '--mp3', `${out}/${deck.name}.mp3`,
    '--title', deck.title, '--lang', deck.lang], { stdio: 'inherit' });
  // A contact sheet: the frame each paragraph shows, one second in.
  const frames = list.flatMap((ch, k) => ch.paras.map((p) => `${part(out, k)}/frames/${p.id}.jpg`).filter(existsSync));
  if (frames.length) {
    const cols = 6;
    const rows = Math.ceil(frames.length / cols);
    const inputs = frames.flatMap((f) => ['-i', f]);
    const pads = Array.from({ length: rows * cols - frames.length }, () => ['-f', 'lavfi', '-i', 'color=c=black:s=640x360:d=1']).flat();
    const n = rows * cols;
    const filter = `${Array.from({ length: n }, (_, i) => `[${i}:v]scale=640:360[f${i}]`).join(';')};${Array.from({ length: n }, (_, i) => `[f${i}]`).join('')}xstack=inputs=${n}:layout=${Array.from({ length: n }, (_, i) => `${(i % cols) * 640}_${Math.floor(i / cols) * 360}`).join('|')}[out]`;
    execFileSync('ffmpeg', ['-v', 'error', '-y', ...inputs, ...pads, '-filter_complex', filter, '-map', '[out]', '-frames:v', '1', `${out}/sheet.jpg`]);
  }
  return `${out}/${deck.name}.mp4`;
}

// Two paragraphs per voice, at two tempos, for the user to pick a voice by ear. Each voice is
// checked against the purpose and the free memory before it speaks.
export function audition(deck, out, names) {
  checkPlatform();
  const paras = deck.paragraphs.slice(0, 2);
  const rows = [];
  for (const name of names) {
    const v = resolveVoice({ lang: deck.lang, voice: name });
    checkVoices(deck, { [name]: v });
    const dir = `${out}/audition/${name}`;
    synthesise(Object.fromEntries(paras.map((p) => [p.id, { say: sayOf(p), text: p.text }])), { engine: v.engine, lang: deck.lang, voice: v.voice }, dir);
    for (const t of [1.0, 1.15]) {
      const files = paras.map((p) => `${dir}/${p.id}.wav`);
      const joined = `${out}/audition/${name}-${t}.wav`;
      execFileSync('ffmpeg', ['-v', 'error', '-y', ...files.flatMap((f) => ['-i', f]), '-filter_complex',
        `${files.map((_, i) => `[${i}:a]`).join('')}concat=n=${files.length}:v=0:a=1,atempo=${t}`, joined]);
      const e = ENGINES[v.engine];
      rows.push({ voice: name, engine: v.engine, licence: e.licence, terms: e.terms, tempo: t, file: joined });
    }
  }
  writeFileSync(`${out}/audition/index.json`, JSON.stringify(rows, null, 1));
  for (const r of rows) console.log(`${r.voice}\t${r.engine}\t${r.licence}\t${r.terms}\ttempo ${r.tempo}\t${r.file}`);
  return rows;
}

// ---- command line -----------------------------------------------------------------------------

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const args = process.argv.slice(2);
  const [file, out] = args.filter((a, i) => !a.startsWith('--') && !(args[i - 1] || '').match(/^--(audition|chapter)$/));
  if (!file || !out) {
    console.error('usage: node slides.mjs <slides.json> <out-dir> [--render | --audition v1,v2 | --voice-only | --record [--chapter N]]');
    process.exit(2);
  }
  const flag = (f) => args.includes(f);
  const value = (f) => args[args.indexOf(f) + 1];
  mkdirSync(out, { recursive: true });
  try {
    const deck = loadDeck(file);
    if (flag('--render')) await render(deck, out);
    else if (flag('--audition')) audition(deck, out, value('--audition').split(','));
    else {
      if (!flag('--record')) {
        if (!flag('--voice-only')) await render(deck, out);
        const { failed } = voice(deck, out);
        if (failed.length && !deck.allowFailedTakes) {
          console.error(`Whisper heard these paragraphs too far from their text: ${failed.join(', ')}; see ${out}/voice/takes.json`);
          process.exit(2);
        }
      }
      if (!flag('--voice-only')) {
        const mp4 = await record(deck, out, { chapter: flag('--chapter') ? Number(value('--chapter')) : undefined });
        if (mp4) console.log(mp4);
      }
    }
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }
}
