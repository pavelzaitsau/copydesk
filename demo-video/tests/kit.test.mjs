// Tests for the checks in scripts/demo-kit.mjs that run before any model: node --test demo-video/tests
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { checkLicence, checkMemory, checkPlatform, ENGINES, resolveVoice, synthesise, VOICES } from '../scripts/demo-kit.mjs';

const withEnv = (vars, fn) => {
  const old = Object.fromEntries(Object.keys(vars).map((k) => [k, process.env[k]]));
  Object.assign(process.env, vars);
  try { return fn(); } finally {
    for (const [k, v] of Object.entries(old)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; }
  }
};

test('the default voices are clean and in the list', () => {
  for (const lang of ['en', 'ru']) {
    const { engine, voiceName } = resolveVoice({ lang, voice: 'default' });
    assert.ok(voiceName in VOICES[lang]);
    assert.equal(ENGINES[engine].licence, 'clean');
  }
});

test('a name from another language is refused, an engine\'s own value is not', () => {
  assert.throws(() => resolveVoice({ lang: 'en', voice: 'serena' }), /not in the en list/);
  assert.deepEqual(resolveVoice({ lang: 'en', engine: 'qwen3', voice: 'serena' }), { engine: 'qwen3', voice: 'serena', voiceName: null });
});

test('an engine that does not speak the language is refused', () => {
  assert.throws(() => resolveVoice({ lang: 'ru', engine: 'kokoro', voice: 'af_nicole' }), /does not speak/);
});

test('a client video refuses a restricted licence unless allowed', () => {
  assert.throws(() => checkLicence('higgs3', 'client'), /client/);
  assert.throws(() => checkLicence('drama3'), /client/);  // client is the default purpose
  assert.doesNotThrow(() => checkLicence('higgs3', 'client', true));
  assert.doesNotThrow(() => checkLicence('higgs3', 'personal'));
  assert.doesNotThrow(() => checkLicence('voxcpm2', 'client'));
  assert.throws(() => checkLicence('qwen3', 'public'), /purpose/);
});

test('an engine that does not fit in free memory is refused, with the ones that fit', () => {
  withEnv({ DEMO_VIDEO_FREE_MEM: '10' }, () => {
    assert.throws(() => checkMemory('drama3', 'en'), /fit: kokoro, chatterbox, omnivoice/);
    assert.doesNotThrow(() => checkMemory('chatterbox', 'en'));
  });
});

test('another platform stops the skill', () => {
  withEnv({ DEMO_VIDEO_PLATFORM: 'other' }, () => assert.throws(() => checkPlatform(), /Apple Silicon/));
  withEnv({ DEMO_VIDEO_PLATFORM: 'arm64' }, () => assert.doesNotThrow(() => checkPlatform()));
});

test('without a voice, a line lasts as long as reading it takes', () => {
  const { len, failed } = synthesise({ a: 'x'.repeat(60), b: { say: 'short', text: 'short' } }, { voice: 'off' }, '/tmp/unused');
  assert.equal(len.a, 4);
  assert.equal(len.b, 2);
  assert.deepEqual(failed, []);
  assert.throws(() => synthesise({ 'bad key': 'x' }, { voice: 'off' }, '/tmp/unused'), /line key/);
});

test('the fake engine writes silent lines and a clean Whisper report', () => {
  const dir = mkdtempSync(`${tmpdir()}/fake-`);
  const { len, failed } = synthesise({ a: 'x'.repeat(30), b: { say: 'short', text: 'short' } }, { engine: 'fake', lang: 'en', voice: 'default' }, dir);
  assert.equal(len.a, 2);
  assert.equal(len.b, 1);
  assert.deepEqual(failed, []);
  assert.equal(statSync(`${dir}/a.wav`).size, 44 + 2 * 16000 * 2);
  const report = JSON.parse(readFileSync(`${dir}/takes.json`, 'utf8'));
  assert.equal(report.b.takes[0].heard, 'short');
});

test('the fake engine is clean and needs no memory', () => {
  assert.equal(ENGINES.fake.licence, 'clean');
  withEnv({ DEMO_VIDEO_FREE_MEM: '2' }, () => assert.doesNotThrow(() => checkMemory('fake', 'ru')));
  assert.deepEqual(resolveVoice({ lang: 'ru', engine: 'fake', voice: 'default' }), { engine: 'fake', voice: 'default', voiceName: null });
});
