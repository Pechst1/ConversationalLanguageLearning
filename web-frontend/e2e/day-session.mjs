#!/usr/bin/env node
// Round 3 · the day as one sequence, walked in the browser.   npm run walk:day
//
// One new A1 learner per language plays day 1 the way the day is meant to run:
// La Une's programme (Szene · Grammatik · Wörter · Fertig; owner, 1 Nov 2026), the
// scene, the scene's ending handing on to La Forge, La Forge's recap handing on to
// the day's word deck, the deck to its end handing on to «Fertig für heute», and
// La Une after with every step done. Screenshots and a contact sheet go to e2e/out/day-<stamp>/.
//
//   --langs de,fr,en   chrome languages (default de)
//   --out DIR          output folder
//   --keep             leave the servers and database up
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Findings } from './lib/assertions.mjs';
import { writeContactSheet } from './lib/contact-sheet.mjs';
import { LearnerWalk } from './lib/learner-walk.mjs';
import { registerLearner } from './lib/session.mjs';
import { sleep, startStack } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const langs = opt('langs', 'de').split(',').filter(Boolean);
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outDir = path.resolve(opt('out', path.join(here, 'out', `day-${stamp}`)));
const SECRET = 'e3-walk-secret-not-for-production';

mkdirSync(outDir, { recursive: true });
const findings = new Findings();
const shots = { root: outDir, list: [] };
let stack;
let browser;

const WORDS_NEXT = /Weiter: \d+ Wörter|Suite : \d+ mots|Next: \d+ words/;
const GRAMMAR_NEXT = /Weiter: Grammatik|Suite : grammaire|Next: grammar/;
const FINISH = /Fertig für heute|Fini pour aujourd’hui|Done for today/;
// Phase 2 «Folge in Akten»: Fertig's first tile on a day that played more than one act.
const ACTS = /^(Akte|Actes|Acts)$/;

async function programme(page) {
  return page.locator('[data-day-session] [data-part]').evaluateAll((rows) =>
    rows.map((row) => `${row.getAttribute('data-part')}:${row.getAttribute('data-state')}`),
  ).catch(() => []);
}

async function playTheDay(native) {
  const learner = await registerLearner({ api: stack.api, secret: SECRET, native, level: 'A1.1', tag: 'day' });
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    isMobile: true,
    hasTouch: true,
    locale: native === 'fr' ? 'fr-FR' : native === 'de' ? 'de-DE' : 'en-GB',
  });
  await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  const walk = new LearnerWalk({ page: null, findings, outDir: path.join(outDir, native), lang: native, level: 'A1.1', stack, shots, scale: 1 });
  await walk.newSession(context);
  walk.day = 1;
  walk.seq = 0;
  const page = walk.page;
  const where = (kind) => walk.where({ kind });

  // 1 · La Une: the programme, the scene first.
  await page.goto(`${stack.web}/atelier`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-day-session]').waitFor({ timeout: 60000 }).catch(() => {});
  const before = await programme(page);
  findings.check('day-programme-on-la-une', before.join() === 'scene:next,grammar:todo,words:todo,finish:todo', `programme: ${before.join(' ') || 'none'}`, where('home'));
  // #396: Home's word count before the scene is the day's one number.
  const homeWordsText = await page.locator('[data-day-session] [data-part="words"]').first().innerText().catch(() => '');
  const homeWords = Number((homeWordsText.match(/\d+/) || [])[0]);
  await walk.shoot('home-programme');

  // 2 · The scene, to its ending.
  const kinds = await walk.playJourney();
  findings.check('day-scene-reaches-its-ending', kinds.includes('recap'), `kinds: ${kinds.join(' > ')}`, where('recap'));
  // #143: the scene's count never grows (a drill asked again is not a step) and never goes back.
  const counts = walk.stepCaptions.map((caption) => (caption.match(/\d+/g) || []).map(Number));
  const steady = counts.every(([n, m], i) => m === counts[0][1] && (i === 0 || n >= counts[i - 1][0]));
  findings.check('scene-step-count-holds', counts.length > 0 && steady, `captions: ${walk.stepCaptions.join(' > ') || 'none'}`, where('recap'));
  await sleep(1500);
  await walk.shoot('scene-ending');
  const handOn = page.locator('.journey-recap .av2-btn--primary, .av2-reward .av2-btn--primary').first();
  const handOnText = await handOn.innerText().catch(() => '');
  // Owner, 1 Nov 2026: La Forge comes before the words.
  findings.check('scene-hands-on-to-the-grammar', GRAMMAR_NEXT.test(handOnText), `the ending's button reads «${handOnText.trim()}»`, where('recap'));
  await handOn.click();

  // 3 · La Forge, to its recap.
  await page.waitForURL(/mode=forge.*from=day|from=day.*mode=forge/, { timeout: 30000 }).catch(() => {});
  const forgeUrl = new URL(page.url());
  findings.check('grammar-opens-la-forge-for-the-day', forgeUrl.searchParams.get('from') === 'day', page.url(), where('forge'));
  await walk.playJourney({ entry: `${forgeUrl.pathname}${forgeUrl.search}`, maxSeconds: 240, label: 'forge-' });
  // The walk's driver cannot assemble every word-bank correction; a séance it
  // leaves unfinished is filed with «Beenden» (twice: the button asks first).
  if (!(await page.locator('.ep-recap').count())) {
    for (let i = 0; i < 2 && !(await page.locator('.ep-recap').count()); i += 1) {
      await page.locator('.ep-finish').first().click().catch(() => {});
      await sleep(800);
    }
  }
  await page.locator('.ep-recap').waitFor({ timeout: 30000 }).catch(() => {});
  await walk.shoot('forge-recap');
  // The walk's driver presses a recap's primary button itself, so the hand-on
  // is either still on screen or already taken.
  const toWords = page.locator('.ep-recap .ep-handoff .av2-btn--primary').first();
  const toWordsText = await toWords.innerText().catch(() => '');
  const handedOn = page.url().includes('/vocabulary/review');
  findings.check('grammar-hands-on-to-the-words', handedOn || WORDS_NEXT.test(toWordsText), `the recap's button reads «${toWordsText.trim()}» on ${page.url()}`, where('forge'));
  if (!handedOn) await toWords.click().catch(() => {});

  // 4 · The day's word deck, to its end.
  await page.waitForURL(/\/vocabulary\/review\?day=1/, { timeout: 30000 }).catch(() => {});
  findings.check('words-open-the-day-deck', page.url().includes('/vocabulary/review?day=1'), page.url(), where('drill'));
  await page.locator('.lx-card, [data-day-next]').first().waitFor({ timeout: 45000 }).catch(() => {});
  await walk.shoot('words-first-card');
  // #143: «Weiter: 20 Wörter» opened «0/19». The deck is the count the button promised
  // (the recap's, when the walk saw it; Home's number otherwise, which #396 makes the same).
  const promised = Number((toWordsText.match(/\d+/) || [])[0]) || homeWords;
  const deckCount = (await page.locator('.av2-progress__count').first().innerText().catch(() => '')).trim();
  findings.check('words-deck-is-the-count-promised', deckCount === `0/${promised}`, `«${toWordsText.trim() || homeWordsText.trim()}» opened a deck of «${deckCount}»`, where('drill'));
  findings.check('home-words-is-the-hand-on', homeWords === promised, `Home said «${homeWordsText.trim()}», La Forge's recap «${toWordsText.trim()}»`, where('drill'));
  let presses = 0;
  while (presses < 260 && (await page.locator('[data-day-next]').count()) === 0) {
    // An unturned card offers only its turn button; a turned one its grades.
    const rate = page.locator('.lx-review__foot .lx-turn, .lx-review__foot .lx-rate').last();
    if (await rate.count()) {
      await rate.click().catch(() => {});
      presses += 1;
    }
    await sleep(250);
  }
  const wordsDone = await page.locator('[data-day-next]').count();
  findings.check('words-deck-ends-with-the-next-step', wordsDone === 1, `${presses} presses, no «words done» screen`, where('drill'));
  // Owner, 2 Nov: the day deck's end offers «Noch 5 neue Wörter», with its line on the goal.
  await page.locator('[data-day-next] [data-extra-words]').waitFor({ timeout: 10000 }).catch(() => {});
  const extraOffer = (await page.locator('[data-day-next] [data-extra-words] [data-goal-line]').first().innerText().catch(() => '')).trim();
  findings.check('words-done-offers-five-more-with-the-goal', extraOffer.length > 0, 'no «Noch 5 neue Wörter» with its goal line', where('drill'));
  await walk.shoot('words-done');
  // Codex review on #490: «Noch 5» taken on the day deck, two answered, the page reloaded:
  // the three still unanswered come back (the server's day deck serves today's extras).
  const extraButton = page.locator('[data-day-next] [data-extra-words] button').first();
  if (await extraButton.count()) {
    await extraButton.click().catch(() => {});
    const count = () => page.locator('.av2-progress__count').first().innerText().catch(() => '');
    await page.locator('.av2-progress__count').first().waitFor({ timeout: 15000 }).catch(() => {});
    let extraPresses = 0;
    while (extraPresses < 20 && !/^2\//.test((await count()).trim())) {
      const rate = page.locator('.lx-review__foot .lx-turn, .lx-review__foot .lx-rate').last();
      if (await rate.count()) {
        await rate.click().catch(() => {});
        extraPresses += 1;
      }
      await sleep(250);
    }
    const answered = (await count()).trim();
    await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.locator('.av2-progress__count').first().waitFor({ timeout: 15000 }).catch(() => {});
    await sleep(1000);
    const afterReload = (await count()).trim();
    const left = Number((answered.match(/^\d+\/(\d+)/) || [])[1] || 0) - 2;
    findings.check('extra-words-survive-a-reload', left > 0 && afterReload === `0/${left}`, `answered «${answered}», after the reload «${afterReload}»`, where('drill'));
    let rest = 0;
    while (rest < 60 && (await page.locator('[data-day-next]').count()) === 0) {
      const rate = page.locator('.lx-review__foot .lx-turn, .lx-review__foot .lx-rate').last();
      if (await rate.count()) {
        await rate.click().catch(() => {});
        rest += 1;
      }
      await sleep(250);
    }
  }
  const toFinish = page.locator('[data-day-next] .av2-btn--primary').first();
  const toFinishText = await toFinish.innerText().catch(() => '');
  findings.check('words-hand-on-to-fertig', FINISH.test(toFinishText), `the button reads «${toFinishText.trim()}»`, where('drill'));
  await toFinish.click().catch(() => {});

  // 5 · Fertig für heute.
  await page.waitForURL(/\/fertig/, { timeout: 30000 }).catch(() => {});
  await page.locator('.av2-fertig__body[data-fertig]').waitFor({ timeout: 30000 }).catch(() => {});
  await sleep(1500);
  const state = await page.locator('.av2-fertig__body').getAttribute('data-fertig').catch(() => null);
  findings.check('fertig-says-the-day-is-done', state === 'done', `data-fertig=${state}`, where('fertig'));
  const tally = await page.locator('.av2-tally__n').allInnerTexts().catch(() => []);
  // The first tile is the day's scene, or on a day of acts its acts («2 Akte»).
  const storyLabel = (await page.locator('.av2-tally__l').first().innerText().catch(() => '')).trim();
  const storyTile = Number(tally[0]) === 1 || (Number(tally[0]) > 1 && ACTS.test(storyLabel));
  findings.check('fertig-tallies-scene-words-exercises', tally.length === 3 && storyTile && Number(tally[1]) > 0 && Number(tally[2]) > 0, `tally: ${tally.join(' · ')} (${storyLabel})`, where('fertig'));
  // Phase 2: under the tally, the story's words the day read (its pages, the characters' lines, the endings).
  const storyRead = (await page.locator('[data-story-words]').first().innerText().catch(() => '')).trim();
  findings.check('fertig-counts-the-story-read', Number(storyRead.replace(/\D/g, '')) > 0, `the story line reads «${storyRead}»`, where('fertig'));
  findings.check('fertig-words-is-the-deck', Number(tally[1]) === promised, `the deck held ${promised}, Done says ${tally[1]} words`, where('fertig'));
  findings.check('fertig-offers-five-more-words', (await page.locator('[data-more-words]').count()) === 1, 'no «Noch 5 neue Wörter»', where('fertig'));
  // #359: the Done screen names tomorrow's open question (the line Home prints, checked below
  // against Home), and the curtain call's «End of the session» tag is centred over the cast and
  // touches no bubble at phone width.
  const tomorrowOnFertig = (await page.locator('[data-tomorrow] .journey-today-card__hint').first().innerText().catch(() => '')).trim();
  const tag = await page.evaluate(() => {
    const box = (el) => { const r = el.getBoundingClientRect(); return { left: r.left, top: r.top, right: r.right, bottom: r.bottom }; };
    const el = document.querySelector('.cameo-troupe > .cameo-reason');
    if (!el) return null;
    return { tag: box(el), bubbles: [...document.querySelectorAll('.cameo-troupe .cameo-bubble')].map(box), width: window.innerWidth };
  }).catch(() => null);
  if (tag) {
    const mid = (tag.tag.left + tag.tag.right) / 2;
    const touches = tag.bubbles.filter((b) => !(b.top >= tag.tag.bottom + 4 || b.left >= tag.tag.right || b.right <= tag.tag.left)).length;
    findings.check('fertig-badge-clear-of-the-cast', Math.abs(mid - tag.width / 2) <= 24 && touches === 0, `tag ${Math.round(tag.tag.left)}–${Math.round(tag.tag.right)} of ${tag.width}px, touching ${touches} bubbles`, where('fertig'));
  }
  await walk.shoot('fertig');

  // 6 · La Une after: every step done.
  await page.locator('.av2-fertig .av2-btn--done').first().click().catch(() => {});
  await page.waitForURL(/\/atelier/, { timeout: 30000 }).catch(() => {});
  await page.locator('[data-day-session]').waitFor({ timeout: 30000 }).catch(() => {});
  await sleep(1500);
  const after = await programme(page);
  findings.check('la-une-after-the-day', after.join() === 'scene:done,grammar:done,words:done,finish:done', `programme: ${after.join(' ') || 'none'}`, where('home'));
  // #143: «20 Wörter — erledigt» on La Une after «Fertig» counted 19.
  const wordsRow = await page.locator('[data-day-session] [data-part="words"]').first().innerText().catch(() => '');
  findings.check('la-une-words-match-fertig', Number((wordsRow.match(/\d+/) || [])[0]) === Number(tally[1]), `La Une «${wordsRow.trim()}», Fertig ${tally[1]}`, where('home'));
  const tomorrowOnHome = (await page.locator('.journey-today-card__teaser .journey-today-card__hint').first().innerText().catch(() => '')).trim();
  findings.check('fertig-names-tomorrows-question', tomorrowOnFertig === tomorrowOnHome, `Done screen «${tomorrowOnFertig}», Home «${tomorrowOnHome}»`, where('fertig'));
  await walk.shoot('home-after');
  await context.close();
}

let exitCode = 0;
try {
  stack = await startStack({ logDir: path.join(outDir, 'logs'), secret: SECRET, tokenMinutes: 60 });
  console.log(`[day] stack up: api :${stack.apiPort}, web :${stack.webPort}`);
  browser = await chromium.launch(process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {});
  const warm = await registerLearner({ api: stack.api, secret: SECRET, native: 'en', level: 'A1.1', tag: 'warm' });
  for (const route of ['/atelier', '/vocabulary/review', '/atelier?mode=forge', '/fertig']) {
    await fetch(`${stack.web}${route}`, { headers: { cookie: `next-auth.session-token=${warm.cookie}` } }).catch(() => {});
  }
  for (const native of langs) {
    try {
      await playTheDay(native);
    } catch (e) {
      findings.check('day-completes', false, String(e.message).split('\n')[0].slice(0, 200), { lang: native });
    }
  }
} catch (e) {
  console.error('[day] harness error:', e);
  findings.check('harness-ran', false, String(e.stack || e).slice(0, 400), {});
  exitCode = 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  writeContactSheet({ outDir, shots: shots.list, findings, meta: `round 3 day · ${langs.join('/')}` });
  writeFileSync(path.join(outDir, 'report.json'), JSON.stringify({ summary: findings.summary(), failures: findings.failures }, null, 2));
  if (stack && !argv.includes('--keep')) await stack.stop();
  await sleep(200);
  console.log(`\n[day] ${shots.list.length} screens, ${findings.results.length} checks, ${findings.failures.length} failed`);
  for (const r of findings.summary()) console.log(`  ${r.fail ? 'FAIL' : ' ok '} ${r.id}: ${r.pass} pass, ${r.fail} fail`);
  for (const f of findings.failures) console.log(`    ${f.id}: ${f.detail || f.message || JSON.stringify(f).slice(0, 200)}`);
  console.log(`[day] contact sheet: ${path.join(outDir, 'index.html')}`);
  if (findings.failures.length) exitCode = 1;
  process.exit(exitCode);
}
