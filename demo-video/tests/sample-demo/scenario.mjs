// A short demo of a fake release page, the same for every voice and language. It checks the kit
// end to end on one engine; record-all.sh runs it for many.
//   npm install && npx playwright install chromium        once, in demo-video/
//   DEMO_LANG=ru VOICE=serena node scenario.mjs <out-dir>
//   DEMO_LANG=en TTS_ENGINE=voxcpm2 VOICE=default PURPOSE=personal node scenario.mjs <out-dir>
import { createRequire } from 'node:module';
import { startDemo, sleep } from '../../scripts/demo-kit.mjs';
const { chromium } = createRequire(`${import.meta.dirname}/../../package.json`)('playwright');

const out = process.argv[2];
const LANG = process.env.DEMO_LANG || 'en';
const ENGINE = process.env.TTS_ENGINE || 'kokoro';  // with VOICE=default, the language's default voice
// The page is the eval fixture, so the package carries it.
const PAGE = `file://${import.meta.dirname}/../../evals/fixtures/release-page/index.html?lang=${LANG}`;

const T = {
  en: {
    kicker: 'Voice test', title: 'Release desk in one minute', run: 'Run checks', ship: 'Ship release',
    caps: ['Run every check with one click', 'One check failed: the load test', 'Fix it, then ship'],
    lines: {
      intro: 'Hi! This is Release desk. In about a minute, I will show you how a release goes from five open checks to shipped.',
      run: 'First, one click on Run checks. Every check starts at once, and the statuses fill in as they finish.',
      fail: 'Hmm. Four passed, but the load test failed. That is exactly what this screen is for: you see the problem before your users do.',
      fix: 'Oleg fixes the load test, the status turns green, and the Ship button unlocks.',
      ship: 'One more click, and version two point four is out. Five of five checks, zero surprises.',
      outro: 'That is it. Thanks for watching!',
    },
    end: 'Release 2.4.0: 5 of 5 checks passed',
  },
  ru: {
    kicker: 'Тест голоса', title: 'Релизный стол за одну минуту', run: 'Запустить проверки', ship: 'Выпустить релиз',
    caps: ['Все проверки одним нажатием', 'Одна проверка упала: нагрузочный тест', 'Исправляем и выпускаем'],
    lines: {
      intro: 'Привет! Это Релизный стол. Примерно за минуту я покажу, как релиз проходит путь от пяти открытых проверок до выпуска.',
      run: 'Сначала одно нажатие на «Запустить проверки». Все проверки стартуют сразу, а статусы заполняются по мере готовности.',
      fail: 'Хм. Четыре прошли, а нагрузочный тест упал. Именно для этого и нужен этот экран: вы видите проблему раньше, чем ваши пользователи.',
      fix: 'Олег чинит нагрузочный тест, статус становится зелёным, и кнопка выпуска открывается.',
      ship: 'Ещё одно нажатие, и версия два точка четыре вышла. Пять проверок из пяти, никаких сюрпризов.',
      outro: 'Вот и всё. Спасибо за просмотр!',
    },
    end: 'Релиз 2.4.0: пройдено 5 проверок из 5',
  },
}[LANG];

const demo = await startDemo({ chromium, out, lines: T.lines, lang: LANG, engine: ENGINE, voice: process.env.VOICE || 'default',
  purpose: process.env.PURPOSE || 'client', takes: Number(process.env.TAKES || 1) });
const { page, caption, card, uncard, click, narrate, voiceDone, highlight, unhighlight } = demo;
try {
  await page.goto(PAGE, { waitUntil: 'load' });
  await card(`<div class="k">${T.kicker} · ${ENGINE} · ${LANG.toUpperCase()}</div><h1>${T.title}</h1>`);
  demo.mark();
  await sleep(800);
  await narrate('intro', { wait: true, pad: 700 });
  await uncard();

  await caption('1', T.caps[0]);
  await narrate('run');
  await sleep(1500);
  await click(page.getByRole('button', { name: T.run }));
  await page.locator('#sum[data-done="1"]').waitFor();
  await voiceDone();

  await caption('2', T.caps[1]);
  const failed = await highlight(['Load test', 'Нагрузочный тест']);
  await narrate('fail', { wait: true });

  await unhighlight();
  await caption('3', T.caps[2]);
  await narrate('fix');
  await click(page.locator('tr[data-i="3"]'));
  await sleep(1200);
  await voiceDone();
  await narrate('ship');
  await click(page.getByRole('button', { name: T.ship }));
  await page.locator('#sum[data-shipped="1"]').waitFor();
  await voiceDone();

  await card(`<div class="k">${ENGINE} · ${LANG.toUpperCase()}</div><h1>${T.end}</h1>`);
  await narrate('outro', { wait: true, pad: 1200 });
  console.log(JSON.stringify(await demo.finish({ failedRows: failed })));
} catch (e) {
  await demo.abort();
  throw e;
}
