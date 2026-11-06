// Lists the voices a video may use: name, engine, licence class and name, whether the purpose allows it
// without the user's say-so, and whether its engine fits in free memory now.
//   node voices.mjs --lang en --purpose client [--json]
//   node voices.mjs --lang en --prefetch voxcpm,sohee     voice one short line per voice, which downloads
//                                                          each engine's model and Whisper while online
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { checkMemory, ENGINES, freeMemoryGb, resolveVoice, synthesise, VOICES } from './demo-kit.mjs';

const args = process.argv.slice(2);
const value = (f, d) => (args.includes(f) ? args[args.indexOf(f) + 1] : d);
const lang = value('--lang', 'en');
const purpose = value('--purpose', 'client');
if (!(lang in VOICES)) { console.error(`--lang ${lang}: use ${Object.keys(VOICES).join(' or ')}`); process.exit(2); }
if (args.includes('--prefetch')) {
  const dir = mkdtempSync(`${tmpdir()}/demo-video-prefetch-`);
  try {
    for (const name of value('--prefetch', '').split(',').filter(Boolean)) {
      const v = resolveVoice({ lang, voice: name });
      checkMemory(v.engine, lang);
      synthesise({ prefetch: lang === 'ru' ? 'Проверка голоса.' : 'A voice check.' }, { engine: v.engine, lang, voice: v.voice }, `${dir}/${name}`);
      console.log(`${name}\t${v.engine}\tready`);
    }
  } finally { rmSync(dir, { recursive: true, force: true }); }
  process.exit(0);
}
const free = freeMemoryGb();
const rows = Object.entries(VOICES[lang]).map(([name, v]) => {
  const e = ENGINES[v.engine];
  return { name, engine: v.engine, sex: v.sex, strength: v.strength, licence: e.licence, terms: e.terms,
    allowed: purpose !== 'client' || e.licence === 'clean', fits: e.peakGb + 2 <= free };
});
if (args.includes('--json')) console.log(JSON.stringify(rows, null, 1));
else for (const r of rows) console.log(`${r.name}\t${r.engine}\t${r.sex}\t${r.licence}\t${r.terms}\t${r.allowed ? 'allowed' : 'needs the user\'s yes'}\t${r.fits ? 'fits' : 'too big now'}`);
