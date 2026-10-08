#!/usr/bin/env node
// E-3 · the browser walk.  One command:   npm run walk        (from web-frontend/)
//
// Starts its own throwaway database, fake-provider API (with the test-only clock) and
// Next dev server on free ports, registers a learner per language by API, mints the
// NextAuth cookie (no password is ever typed), and plays day 1 (authored) .. day 7:
// the reader, the conversation, the drills, the recap, Home, Courrier and Feuilleton,
// at 375x812 in light and dark. Screenshots and a contact sheet go to e2e/out/<stamp>/.
// The assertions ask, for every screen: does the learner know what to do, whether they
// were right, and how to go on?  Any failed assertion makes the exit code 1.
//
//   --langs en,de,fr   chrome languages of the A1 learners   (default en,de,fr)
//   --days 7           days per learner                      (default 7)
//   --b1-days 3        days for the B1 learner (French chrome; default 3, 0 = skip)
//   --season-days 10   days for the season learner (English, A2; default 10, 0 = skip):
//                      T1 A/B, gap 1, T2 A/B and the first day of gap 2 of season 1
//                      «La clé d'Odile» (WP-111). The server starts every new learner on
//                      the season unless WALK_SEASON= (empty) is set.
//   --out DIR          output folder                         (default e2e/out/<stamp>)
//   --keep             leave the servers and database up (for debugging)
//   --token-minutes 1  expire access tokens during the walk (WP-107)
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
if (argv.includes('--live')) {
  console.error('--live would make paid model calls; this harness only runs the fake provider. Not supported here.');
  process.exit(2);
}
const langs = opt('langs', 'en,de,fr').split(',').filter(Boolean);
const days = Number(opt('days', 7));
const b1Days = Number(opt('b1-days', 3));
const seasonDays = process.env.WALK_SEASON === '' ? 0 : Number(opt('season-days', 10));
const tokenMinutes = Number(opt('token-minutes', 1));
if (!Number.isInteger(tokenMinutes) || tokenMinutes < 1) throw new Error('--token-minutes must be a positive integer');
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outDir = path.resolve(opt('out', path.join(here, 'out', stamp)));
const SECRET = 'e3-walk-secret-not-for-production';
const scale = Number(process.env.WALK_SCALE || 1);

mkdirSync(outDir, { recursive: true });
const findings = new Findings();
const shots = { root: outDir, list: [] };
const timings = [];
const coverage = {};
const t00 = Date.now();
let stack;
let browser;

async function makeLearner({ native, level, dayCount, tag }) {
  const learner = await registerLearner({ api: stack.api, secret: SECRET, native, level, tag });
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    deviceScaleFactor: scale,
    isMobile: true,
    hasTouch: true,
    locale: native === 'fr' ? 'fr-FR' : native === 'de' ? 'de-DE' : 'en-GB',
  });
  await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  // WP-116: WALK_ART_SET=drawn walks the drawn cast (the device switch, as Settings sets it).
  if (process.env.WALK_ART_SET) {
    await context.addInitScript((value) => {
      try { window.localStorage.setItem('atelier.artSet', value); } catch { /* storage refused */ }
    }, process.env.WALK_ART_SET);
  }
  const label = tag === 'b1' ? `${native}-${level}` : tag === 'season' ? `season-${native}` : native;
  const walk = new LearnerWalk({ page: null, findings, outDir: path.join(outDir, label), lang: native, level, stack, shots, scale });
  await walk.newSession(context);
  return { label, walk, context, dayCount, covered: new Set(), userId: learner.id };
}

async function playDay(l, day) {
  try {
    await playDayInner(l, day);
  } catch (e) {
    // One learner's failure is a finding with a screenshot, not the end of the walk.
    findings.check('day-completes', false, String(e.message).split('\n')[0].slice(0, 200), l.walk.where());
    await l.walk.shoot('error').catch(() => {});
    console.log(`[walk] ${l.label} day ${day} failed: ${String(e.message).split('\n')[0]}`);
  }
}

async function playDayInner(l, day) {
  const { walk, label } = l;
  const d0 = Date.now();
  walk.day = day;
  walk.seq = 0;
  console.log(`[walk] ${label} day ${day}`);
  // WP-109: on day 2 the day is entered from the Feuilleton's «today» card.
  if (day === 2) await walk.enterFromFeuilleton();
  const kinds = await walk.playJourney();
  kinds.forEach((k) => l.covered.add(k));
  findings.check('day-reaches-the-recap', kinds.includes('recap') || kinds.includes('home-done'), `day ${day} never reached the recap; kinds: ${kinds.join(' > ')}`, walk.where());
  await walk.visit('/atelier', 'home-after');
  if (day >= 2 && day % 2 === 0) await walk.playJourney({ entry: '/atelier?mode=forge', maxSeconds: 60, label: 'forge-' });
  l.pages = l.pages || [];
  l.pages.push({ day, text: walk.dayText || '' });
  if (label.startsWith('season-') || day === 1 || day === l.dayCount) await readPage(l, day);
  if (day === l.dayCount && !label.startsWith('season-')) {
    // WP-115a: the learner's caps, and the word drill (graded answers).
    // WP-115b: the word kept from the story comes back on its own line. The walk's
    // clock does not move the vocabulary scheduler, and the day's practice has already
    // reviewed the word, so the kept card is staged here as due and seen once — test
    // data on the walk's own database, for the screenshot of the «scene» rung.
    if (l.userId && /^[0-9a-f-]{36}$/.test(l.userId)) {
      stack.sql(
        `UPDATE user_vocabulary_progress SET due_at = now() - interval '30 days', `
        + `next_review_date = now() - interval '30 days', due_date = (now() - interval '30 days')::date, `
        + `reps = 1, lapses = 0, stability = 2 `
        + `WHERE user_id = '${l.userId}' AND context IS NOT NULL`,
      );
    }
    await walk.visit('/vocabulary/review', 'drill');
    const rung = await walk.page.locator('.lx-card').first().getAttribute('data-mode').catch(() => null);
    const kept = walk.keptWords || [];
    const first = await walk.page.locator('.lx-card .lx-card__word').first().innerText().catch(() => '');
    // A word is kept only with a meaning in the learner's own language, and the core
    // lexicon glosses in English and German: a French-native walker has nothing to
    // keep, and «Garder» is not offered to them.
    if (walk.lang !== 'fr') {
      findings.check('walk-keeps-a-word', kept.length > 0, `no word kept from the story in ${day} days`, walk.where({ kind: 'drill' }));
    }
    if (kept.length) {
      findings.check(
        'drill-brings-a-kept-word-back-on-its-line',
        rung === 'scene',
        `the drill's first card («${first.replace(/\s+/g, ' ').trim().slice(0, 60)}») is on the «${rung}» rung; kept on the walk: ${kept.map((w) => `«${w}»`).join(', ')}`,
        walk.where({ kind: 'drill' }),
      );
    }
    await drillReloadKeepsTheBatch(l);
    await walk.visit('/settings?section=practice', 'settings');
    const caps = walk.page.locator('#st-reviews-label');
    const shown = await caps.count().then((n) => n > 0, () => false);
    findings.check('settings-has-anki-like-caps', shown, 'no «maximum reviews per day» row in Réglages', walk.where({ kind: 'settings' }));
    if (shown) {
      await caps.evaluate((node) => node.scrollIntoView({ block: 'center' }));
      await walk.shoot('settings-caps');
    }
  }
  if (day === 1 || day === l.dayCount) {
    await walk.visit('/missions', 'courrier');
    await walk.visit('/graphic-novel', 'feuilleton');
  }
  timings.push({ label, day, seconds: +((Date.now() - d0) / 1000).toFixed(1) });
}

// WP-154: a reload mid-drill shows the rest of the batch the drill dealt, in the same
// order — never new words in the slots of the cards already answered. The deck is read
// off the page's own due-context responses (the page renders one card at a time); three
// cards are answered through the page's own buttons.
const DECK_LISTS = ['due_words', 'fragile_words', 'linked_words', 'topic_compatible_words', 'new_words'];

async function drillReloadKeepsTheBatch(l) {
  const { walk } = l;
  const page = walk.page;
  const where = walk.where({ kind: 'drill' });
  const deckResponse = () => page.waitForResponse(
    (r) => r.url().includes('/vocabulary/due-context') && r.request().method() === 'GET',
    { timeout: 30000 },
  );
  const reload = async () => {
    const waiting = deckResponse();
    await page.reload({ waitUntil: 'domcontentloaded' });
    const response = await waiting;
    await page.locator('.lx-card').first().waitFor({ timeout: 20000 }).catch(() => {});
    await sleep(800);
    return { url: response.url(), deck: await response.json() };
  };
  const ids = (deck) => Object.fromEntries(DECK_LISTS.map((name) => [name, (deck[name] || []).map((w) => w.word_id)]));
  const word = () => page.locator('.lx-card .lx-card__word').first().innerText().then((t) => t.replace(/\s+/g, ' ').trim(), () => '');

  const before = await reload();
  findings.check('drill-asks-for-its-batch', /[?&]drill=session\b/.test(before.url), `the drill's deck request carries no drill=session: ${before.url.slice(0, 160)}`, where);
  const dealt = ids(before.deck);
  const size = DECK_LISTS.reduce((n, name) => n + dealt[name].length, 0);
  if (size < 4) {
    console.log(`[walk] ${l.label}: drill-reload check skipped, the deck holds ${size} cards`);
    return;
  }
  const answered = [];
  for (let i = 0; i < 3; i += 1) {
    const filed = page.waitForRequest(
      (r) => r.url().includes('/anki/review') && r.method() === 'POST',
      { timeout: 20000 },
    );
    // A grade on an unturned card turns it; the second press files it (on a graded
    // card the second press is its one «next» button).
    await page.locator('.lx-review__foot .lx-rate').last().click();
    await sleep(300);
    await page.locator('.lx-review__foot .lx-rate').last().click();
    const request = await filed;
    answered.push(Number(JSON.parse(request.postData() || '{}').word_id));
    await page.waitForResponse((r) => r.url().includes('/anki/review'), { timeout: 20000 }).catch(() => {});
    await sleep(600);
  }
  const shownBefore = await word();
  const after = await reload();
  const kept = ids(after.deck);
  const expected = Object.fromEntries(DECK_LISTS.map((name) => [name, dealt[name].filter((id) => !answered.includes(id))]));
  const same = DECK_LISTS.every((name) => JSON.stringify(kept[name]) === JSON.stringify(expected[name]));
  findings.check(
    'drill-reload-keeps-the-batch',
    same,
    `answered ${answered.join(', ')}; expected ${JSON.stringify(expected)}, the reload served ${JSON.stringify(kept)}`,
    where,
  );
  const shownAfter = await word();
  findings.check('drill-reload-resumes-on-the-same-card', shownAfter === shownBefore, `before the reload «${shownBefore}», after «${shownAfter}»`, where);
  await walk.shoot('drill-after-reload');
}

// WP-110: a whole episode reads as one page on a phone, with the learner's lines in it.
async function readPage(l, day) {
  let seen;
  try {
    seen = await l.walk.readThePage();
  } catch (e) {
    findings.check('page-reads-through', false, `day ${day}: ${String(e.message).split('\n')[0].slice(0, 160)}`, l.walk.where({ kind: 'page' }));
    await l.walk.shoot('page-error').catch(() => {});
    return;
  }
  const where = l.walk.where({ kind: 'page' });
  if (seen.authored) {
    findings.check('authored-day-keeps-its-replies', seen.replyBox, `day ${day}: an authored day without its reply box`, where);
    return;
  }
  findings.check('page-draws-your-line', seen.you.length >= 1, `day ${day}: no balloon of yours in ${seen.panels} panels (${seen.movements.join(' > ')})`, where);
  findings.check('page-has-the-six-movements', seen.movements.includes('turn') && seen.movements.includes('reaction'), `day ${day}: ${seen.movements.join(' > ')}`, where);
  findings.check('page-ends-a-suivre', seen.aSuivre || seen.movements[seen.movements.length - 1] === 'resolution', `day ${day}: the page never reached its ending (${seen.movements.join(' > ')})`, where);
  if (process.env.WALK_ART_SET === 'drawn') {
    findings.check('page-draws-the-cast', seen.castPanels >= Math.min(3, seen.panels), `day ${day}: people on ${seen.castPanels} of ${seen.panels} panels`, where);
    if (l.walk.mouthShapes != null) findings.check('face-mouth-follows-the-voice', l.walk.mouthShapes >= 3, `day ${day}: ${l.walk.mouthShapes} mouth shapes while a line played`, where);
  }
  if (seen.you.length) l.covered.add('page');
  if (l.label.startsWith('season') && day >= 2) {
    findings.check('season-choice-asked-as-cards', (l.walk.cardsTapped || 0) >= 1, `day ${day}: no «Le choix» card tapped yet`, where);
  }
}

// WP-111: the tentpoles of season 1 the season learner must meet, each once, as the
// bible wrote them (A2 lines). The weekend flex may move T2 by a day, never more.
const SEASON_PAGES = [
  { key: 't1.a', line: 'Tu as une valise, une lettre et une clé.', days: [1] },
  { key: 't1.b', line: 'Mon grand-père a tout l\'immeuble', days: [2] },
  { key: 't2.a', line: 'Tu devais partir aujourd\'hui. Tu es encore là.', days: [7, 8, 9] },
  { key: 't2.b', line: 'Architecte d\'intérieur.', days: [8, 9, 10] },
];

function seasonChecks(l) {
  for (const page of SEASON_PAGES) {
    // French print sets the apostrophe as ’ (lib/french-typography); the bible writes '.
    const fold = (text) => text.replace(/[’ʼ]/g, "'");
    const where = (l.pages || []).filter((row) => fold(row.text).includes(fold(page.line))).map((row) => row.day);
    findings.check(
      'season-tentpole-on-its-day',
      where.length >= 1 && where.every((day) => page.days.includes(day)) && new Set(where).size === 1,
      `${page.key}: «${page.line}» seen on day(s) ${where.join(', ') || 'none'} (expected one of ${page.days.join(', ')})`,
      l.walk.where({ kind: 'reader' }),
    );
  }
}

let exitCode = 0;
try {
  console.log(`[walk] output: ${outDir}`);
  stack = await startStack({ logDir: path.join(outDir, 'logs'), secret: SECRET, tokenMinutes });
  console.log(`[walk] stack up: api :${stack.apiPort}, web :${stack.webPort}, db ${stack.dbName} (migrate ${stack.migrateSeconds}s)`);
  // Warm the dev server's on-demand compiles so the first screenshots are not spinners.
  browser = await chromium.launch();
  {
    const warm = await registerLearner({ api: stack.api, secret: SECRET, native: 'en', level: 'A1.1', tag: 'warm' });
    for (const route of ['/atelier', '/missions', '/graphic-novel', '/atelier?mode=forge']) {
      await fetch(`${stack.web}${route}`, { headers: { cookie: `next-auth.session-token=${warm.cookie}` } }).catch(() => {});
    }
  }
  // Learners walk side by side: the test clock is global, so every day is played by all of
  // them before the clock moves on. It also exercises the engine's writer under concurrency.
  const learners = [];
  for (const native of langs) learners.push(await makeLearner({ native, level: 'A1.1', dayCount: days, tag: 'walk' }));
  if (b1Days > 0) learners.push(await makeLearner({ native: 'en', level: 'B1.1', dayCount: b1Days, tag: 'b1' }));
  if (seasonDays > 0) learners.push(await makeLearner({ native: 'en', level: 'A2.1', dayCount: seasonDays, tag: 'season' }));
  const lastDay = Math.max(days, b1Days, seasonDays);
  for (let day = 1; day <= lastDay; day += 1) {
    await stack.setClock(day - 1);
    await Promise.all(learners.filter((l) => day <= l.dayCount).map((l) => playDay(l, day)));
  }
  for (const l of learners.filter((row) => row.label.startsWith('season-'))) seasonChecks(l);
  for (const l of learners) {
    for (const need of ['reader', 'thread', 'recap']) {
      findings.check('walk-covers-' + need, l.covered.has(need), `${l.label}: no ${need} screen in ${l.dayCount} days (saw ${[...l.covered].join(', ')})`, l.walk.where());
    }
    coverage[l.label] = [...l.covered];
    console.log(`[walk] ${l.label}: screens seen: ${[...l.covered].join(', ')}`);
    // WP-107: a refused replay has a clear reconnect action, in every chrome
    // language. This fault is local to this browser; it changes no user row.
    await l.walk.page.route(`${stack.api}/**`, (route) => {
      const preflight = route.request().method() === 'OPTIONS';
      return route.fulfill({
        status: preflight ? 204 : 401,
        headers: {
          'access-control-allow-origin': stack.web,
          'access-control-allow-methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
          'access-control-allow-headers': route.request().headers()['access-control-request-headers'] || 'authorization, content-type, x-request-id',
        },
        contentType: 'application/json', body: preflight ? '' : '{"detail":"Expired test session"}',
      });
    });
    await l.walk.page.goto(`${stack.web}/atelier`);
    const expired = l.walk.page.getByText(/Your session has expired|Deine Sitzung ist abgelaufen|Votre session a expiré/);
    await expired.waitFor({ timeout: 15000 });
    findings.check('expired-session-has-reconnect-action',
      await l.walk.page.getByRole('button', { name: /Sign in again|Erneut anmelden|Se reconnecter/ }).count() === 1,
      'The expired session needs one sign-in action', l.walk.where());
    await l.walk.shoot('session-expired');
    await l.walk.page.getByRole('button', { name: /Sign in again|Erneut anmelden|Se reconnecter/ }).click();
    await l.walk.page.waitForURL('**/auth/signin?callbackUrl=*', { timeout: 15000 });
    await l.walk.page.locator('#signin-email').waitFor({ timeout: 15000 });
    findings.check('expired-session-can-sign-in', true, 'The reconnect action opens the sign-in form', l.walk.where());
    await l.context.close();
  }
} catch (e) {
  console.error('[walk] harness error:', e);
  findings.check('harness-ran', false, String(e.stack || e).slice(0, 400), {});
  exitCode = 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  const seconds = Math.round((Date.now() - t00) / 1000);
  const meta = `${new Date().toISOString()} · ${langs.join('/')} × ${days} days + B1 × ${b1Days} + season × ${seasonDays} · fake provider · ${seconds}s`;
  writeContactSheet({ outDir, shots: shots.list, findings, meta });
  writeFileSync(
    path.join(outDir, 'report.json'),
    JSON.stringify({ meta, seconds, timings, coverage, summary: findings.summary(), failures: findings.failures, shots: shots.list.length }, null, 2),
  );
  if (stack && !argv.includes('--keep')) await stack.stop();
  await sleep(200);
  console.log(`\n[walk] ${shots.list.length} screens, ${findings.results.length} checks, ${findings.failures.length} failed, ${seconds}s`);
  for (const r of findings.summary()) console.log(`  ${r.fail ? 'FAIL' : ' ok '} ${r.id}: ${r.pass} pass, ${r.fail} fail`);
  console.log(`[walk] contact sheet: ${path.join(outDir, 'index.html')}`);
  if (findings.failures.length) exitCode = 1;
  process.exit(exitCode);
}
