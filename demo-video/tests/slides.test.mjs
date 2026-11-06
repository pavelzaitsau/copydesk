// Tests for the checks and timing in scripts/slides.mjs: node --test demo-video/tests
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { align, anchorIndices, anchorTime, chapters, checkDeck, identity, loadDeck, startState } from '../scripts/slides.mjs';

const DECK = new URL('../evals/fixtures/sample-slides/slides.json', import.meta.url).pathname;
const deck = (change = (d) => d) => change(loadDeck(DECK));

test('the sample deck passes its checks', () => {
  assert.doesNotThrow(() => checkDeck(deck()));
});

test('an insert is a chapter of its own, after the chapter it follows', () => {
  assert.deepEqual(chapters(deck()).map((c) => `${c.kind}:${c.title}`), ['slides:Opening', 'slides:Parts', 'insert:In the app', 'slides:Why']);
});

test('two speakers on one clip are one person', () => {
  assert.equal(identity({ engine: 'voxcpm2', voice: 'default' }), identity({ engine: 'qwen3', voice: 'ryan' }));
  assert.notEqual(identity({ engine: 'qwen3', voice: 'ryan' }), identity({ engine: 'qwen3', voice: 'sohee' }));
  assert.throws(() => checkDeck(deck((d) => ({ ...d, speakers: { host: 'voxcpm', expert: 'higgs3' } }))), /one voice/);
});

test('an anchor must be in the say, without numbers', () => {
  assert.throws(() => checkDeck(deck((d) => { d.states[2].anchor = 'not there'; return d; })), /not in the say/);
  assert.throws(() => checkDeck(deck((d) => { d.paragraphs[1].text += ' It took 3 tries.'; d.states[2].anchor = 'took 3'; return d; })), /number/);
  // A number in words too: Whisper writes it in digits.
  assert.throws(() => checkDeck(deck((d) => { d.paragraphs[1].text += ' It took three tries.'; d.states[2].anchor = 'took three'; return d; })), /number/);
});

test('an ordinal is a number in an anchor, in English and in Russian', () => {
  // Whisper writes "second" as "2nd" and "второй" as "2-й", so an anchor on the word never matches.
  for (const word of ['second', 'twentieth', 'hundredth']) {
    assert.throws(() => checkDeck(deck((d) => { d.paragraphs[1].text += ` The ${word} try worked.`; d.states[3].anchor = `${word} try`; return d; })), /number/, word);
  }
  const ru = (d) => {
    d.lang = 'ru';
    d.paragraphs = d.paragraphs.map((p, i) => ({ ...p, text: ['Очередь за две минуты.', 'Вторая попытка прошла.', 'Зачем?', 'Чтобы ждать.'][i] }));
    d.states = d.states.map(({ anchor, ...s }) => s);
    return d;
  };
  assert.doesNotThrow(() => checkDeck(deck((d) => { ru(d); d.states[3].anchor = 'попытка прошла'; return d; })));
  assert.throws(() => checkDeck(deck((d) => { ru(d); d.states[3].anchor = 'Вторая попытка'; return d; })), /number/);
});

test('the anchors of a paragraph follow the voice, each found after the one before', () => {
  const para = { id: 'p', text: 'The queue holds work. A worker takes it from the queue.' };
  const at = anchorIndices(para, [{ id: 'a', anchor: 'A worker' }, { id: 'b', anchor: 'the queue' }]);
  assert.deepEqual(at, { a: 4, b: 9 });
  assert.throws(() => checkDeck(deck((d) => { [d.states[2], d.states[3]] = [d.states[3], d.states[2]]; return d; })), /comes before the previous/);
});

test('the deck is checked against its schema before anything runs', () => {
  assert.throws(() => checkDeck(deck((d) => { delete d.paragraphs[0].chapter; return d; })), /'chapter' is required/);
  assert.throws(() => checkDeck(deck((d) => ({ ...d, tempo: 1.6 }))), /none of the allowed forms/);
  assert.throws(() => checkDeck(deck((d) => ({ ...d, takes: 0 }))), /below 1/);
  assert.doesNotThrow(() => checkDeck(deck((d) => ({ ...d, speed: { host: 1.1, expert: 0.9 }, tempo: { host: 1.2 } }))));
  assert.throws(() => checkDeck(deck((d) => { d.states[0].anchor = 'Today'; return d; })), /needs a state without an anchor/);
});

test('an insert needs an app from the brief and must follow a chapter end', () => {
  assert.throws(() => checkDeck(deck((d) => { d.apps = []; return d; })), /not in apps/);
  assert.throws(() => checkDeck(deck((d) => { d.inserts[0].after = 'p3'; return d; })), /does not end a chapter/);
  assert.throws(() => checkDeck(deck((d) => { d.apps[0].demoData = false; return d; })), /demo data/);
  assert.throws(() => checkDeck(deck((d) => { delete d.apps[0].owner; return d; })), /'owner' is required/);
});

test('an anchor is timed by Whisper\'s words, else by its share of the text', () => {
  const d = deck();
  const para = d.paragraphs[1];
  const state = d.states[2];  // anchor 'The queue holds'
  const words = 'A producer adds work. The queue holds it. A worker takes it out.'.split(' ').map((w, i) => ({ w, t: i, e: i + 1 }));
  assert.equal(anchorTime(d, para, state, { best: 0, takes: [{ sec: 13, words }] }).t, 4);
  const share = anchorTime(d, para, state, { best: 0, takes: [{ sec: 13, words: [] }] });
  assert.equal(share.how, 'share');
  assert.ok(share.t > 2 && share.t < 5);
  assert.equal(anchorTime({ ...d, tempo: 1.25 }, para, state, { best: 0, takes: [{ sec: 13, words }] }).t, 3.2);
});

test('a misheard anchor word still times the anchor, through the alignment', () => {
  assert.deepEqual(align(['the', 'queue', 'holds'], ['the', 'cue', 'holds']), [0, 1, 2]);
  const d = deck();
  const words = 'A producer adds work. The cue holds it. A worker takes it out.'.split(' ').map((w, i) => ({ w, t: i, e: i + 1 }));
  const r = anchorTime(d, d.paragraphs[1], d.states[2], { best: 0, takes: [{ sec: 13, words }] });
  assert.deepEqual(r, { t: 4, how: 'words' });
  const first = 'A producer adds work. Cue holds it.'.split(' ').map((w, i) => ({ w, t: i, e: i + 1 }));
  assert.equal(anchorTime(d, d.paragraphs[1], d.states[2], { best: 0, takes: [{ sec: 7, words: first }] }).how, 'aligned');
});

test('a chapter opens on its own first state, or keeps the slide before it', () => {
  const d = deck();
  const why = chapters(d).find((c) => c.title === 'Why');
  assert.equal(startState(d, why).id, 's3a');
  d.states[4].para = 'p4';  // p3 loses its state: the slide of the chapter before stays
  assert.equal(startState(d, why).id, 's2c');
});
