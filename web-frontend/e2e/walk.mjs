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
//   --out DIR          output folder                         (default e2e/out/<stamp>)
//   --keep             leave the servers and database up (for debugging)
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
  const label = tag === 'b1' ? `${native}-${level}` : native;
  const walk = new LearnerWalk({ page: null, findings, outDir: path.join(outDir, label), lang: native, level, stack, shots, scale });
  await walk.newSession(context);
  return { label, walk, context, dayCount, covered: new Set() };
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
  const kinds = await walk.playJourney();
  kinds.forEach((k) => l.covered.add(k));
  findings.check('day-reaches-the-recap', kinds.includes('recap'), `day ${day} never reached the recap; kinds: ${kinds.join(' > ')}`, walk.where());
  await walk.visit('/atelier', 'home-after');
  if (day >= 2 && day % 2 === 0) await walk.playJourney({ entry: '/atelier?mode=forge', maxSeconds: 60, label: 'forge-' });
  if (day === 1 || day === l.dayCount) {
    await walk.visit('/missions', 'courrier');
    await walk.visit('/graphic-novel', 'feuilleton');
  }
  timings.push({ label, day, seconds: +((Date.now() - d0) / 1000).toFixed(1) });
}

let exitCode = 0;
try {
  console.log(`[walk] output: ${outDir}`);
  stack = await startStack({ logDir: path.join(outDir, 'logs'), secret: SECRET });
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
  for (let day = 1; day <= days; day += 1) {
    await stack.setClock(day - 1);
    await Promise.all(learners.filter((l) => day <= l.dayCount).map((l) => playDay(l, day)));
  }
  for (const l of learners) {
    for (const need of ['reader', 'thread', 'recap']) {
      findings.check('walk-covers-' + need, l.covered.has(need), `${l.label}: no ${need} screen in ${l.dayCount} days (saw ${[...l.covered].join(', ')})`, l.walk.where());
    }
    coverage[l.label] = [...l.covered];
    console.log(`[walk] ${l.label}: screens seen: ${[...l.covered].join(', ')}`);
    await l.context.close();
  }
} catch (e) {
  console.error('[walk] harness error:', e);
  findings.check('harness-ran', false, String(e.stack || e).slice(0, 400), {});
  exitCode = 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  const seconds = Math.round((Date.now() - t00) / 1000);
  const meta = `${new Date().toISOString()} · ${langs.join('/')} × ${days} days + B1 × ${b1Days} · fake provider · ${seconds}s`;
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
