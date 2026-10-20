#!/usr/bin/env node
// Les appels · the browser walk of a call. One command (from web-frontend/):
//
//   node e2e/appels-walk.mjs [--out DIR] [--lang en] [--keep]
//
// The walk's own stack (throwaway database, fake-provider API, Next dev server) with
// ATELIER_CALLS_ENABLED on. A season learner plays day 1 to the recap; then the home
// should ring, the call is answered, one line is spoken (Chromium's fake microphone,
// the API's fake transcriber), one is typed, and the learner hangs up. Last, the
// learner's story memory is read from the database: the call's lines must be there,
// heard by the caller only. Screenshots at 375x812 go to the output folder.
import { chromium } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Findings } from './lib/assertions.mjs';
import { LearnerWalk } from './lib/learner-walk.mjs';
import { registerLearner } from './lib/session.mjs';
import { REPO_ROOT, sleep, startStack } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.lastIndexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const lang = opt('lang', 'en');
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outDir = path.resolve(opt('out', path.join(here, 'out', `appels-${stamp}`)));
const SECRET = 'appels-walk-secret-not-for-production';

process.env.ATELIER_CALLS_ENABLED = 'true';
mkdirSync(outDir, { recursive: true });
const findings = new Findings();
let stack;
let browser;
let n = 0;

async function shoot(page, name) {
  n += 1;
  const file = path.join(outDir, `${String(n).padStart(2, '0')}-${name}.png`);
  await page.screenshot({ path: file });
  console.log(`[appels] ${path.basename(file)}`);
}

function threadState(dbName, userId) {
  // Read-only, on the walk's own throwaway database.
  const code = [
    'import sys, json, psycopg2',
    'c = psycopg2.connect(sys.argv[1])',
    'cur = c.cursor(); cur.execute("select state from serial_threads where user_id = %s and status = \'active\' order by created_at desc limit 1", (sys.argv[2],))',
    'row = cur.fetchone(); print(json.dumps(row[0] if row else None))',
  ].join('\n');
  const admin = new URL(process.env.WALK_PG_ADMIN_URL || 'postgresql://localhost/postgres');
  admin.pathname = `/${dbName}`;
  const r = spawnSync('python', ['-c', code, admin.toString(), userId], { encoding: 'utf8', cwd: REPO_ROOT });
  if (r.status !== 0) throw new Error(r.stderr.slice(-800));
  return JSON.parse(r.stdout);
}

async function main() {
  stack = await startStack({ logDir: path.join(outDir, 'logs'), secret: SECRET, tokenMinutes: 30 });
  browser = await chromium.launch({
    ...(process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {}),
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
  });
  const learner = await registerLearner({ api: stack.api, secret: SECRET, native: lang, level: 'A2.1', tag: 'appels' });
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: lang === 'de' ? 'de-DE' : lang === 'fr' ? 'fr-FR' : 'en-GB',
  });
  await context.grantPermissions(['microphone'], { origin: stack.web });
  await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  const walk = new LearnerWalk({ page: null, findings, outDir: path.join(outDir, 'day1'), lang, level: 'A2.1', stack, shots: { root: outDir, list: [] }, scale: 2 });
  await walk.newSession(context);
  walk.day = 1;
  const kinds = await walk.playJourney();
  findings.check('day-reaches-the-recap', kinds.includes('recap') || kinds.includes('home-done'), `kinds: ${kinds.join(' > ')}`, walk.where());

  const page = walk.page;
  await page.goto(`${stack.web}/atelier`, { waitUntil: 'domcontentloaded' });
  const card = page.locator('.ap-card');
  const rang = await card.waitFor({ timeout: 30000 }).then(() => true, () => false);
  findings.check('home-rings-after-the-day', rang, 'no ringing card on the home after day 1', walk.where({ kind: 'home' }));
  if (!rang) {
    await shoot(page, 'home-no-call');
    return;
  }
  await card.scrollIntoViewIfNeeded();
  await sleep(600);
  await shoot(page, 'home-ringing');
  await card.locator('.av2-btn--primary').click();
  await page.locator('.ap-ring').waitFor({ timeout: 30000 });
  await sleep(500);
  await shoot(page, 'call-ringing');
  await page.locator('.ap-ring .av2-btn--primary').click();
  await page.locator('.ap-talk').waitFor({ timeout: 30000 });
  await sleep(800);
  await shoot(page, 'call-live');

  // One spoken line: hold, speak (the fake microphone), let go.
  const talk = page.locator('.ap-talk');
  await talk.dispatchEvent('pointerdown');
  await sleep(2500);
  await shoot(page, 'call-holding');
  const before = await page.locator('.ap-meta').innerText();
  await talk.dispatchEvent('pointerup');
  // The line is answered when the count of lines left moves.
  const answered = await page
    .waitForFunction((was) => (document.querySelector('.ap-meta')?.textContent || was) !== was, before, { timeout: 30000 })
    .then(() => true, () => false);
  findings.check('spoken-line-answered', answered, 'the caller did not answer the spoken line', walk.where({ kind: 'call' }));
  await page.locator('.ap-link', { hasText: /text|texte|Text/ }).first().click();
  await sleep(400);
  await shoot(page, 'call-text');

  // One typed line, then hang up.
  await page.locator('.ap-live__foot .ap-link').click();
  await page.locator('.ap-type__field').fill('Je reste encore un peu, je crois.');
  await page.locator('.ap-type .av2-btn--primary').click();
  await sleep(1500);
  await shoot(page, 'call-typed');
  if (await page.locator('.ap-hangup').count()) await page.locator('.ap-hangup').click();
  await page.locator('.ap-end').waitFor({ timeout: 30000 });
  await sleep(500);
  await page.screenshot({ path: path.join(outDir, `${String(++n).padStart(2, '0')}-call-ended.png`), fullPage: true });

  const state = threadState(stack.dbName, learner.id);
  const live = state?.living_story || {};
  const call = (state?.appels?.calls || []).at(-1);
  const said = (live.memory?.said || []).filter((row) => String(row.event_id || '').startsWith('appel:'));
  findings.check('call-lines-in-memory', said.length >= 2, `memory rows from the call: ${said.length}`, walk.where({ kind: 'call' }));
  findings.check(
    'heard-by-the-caller-only',
    said.every((row) => JSON.stringify(row.heard_by) === JSON.stringify([call?.caller])),
    JSON.stringify(said.map((row) => row.heard_by)),
    walk.where({ kind: 'call' }),
  );
  const event = (live.events || []).find((row) => row.source === 'appel');
  findings.check('call-event-in-story', Boolean(event), 'no events[] row from the call', walk.where({ kind: 'call' }));
  writeFileSync(path.join(outDir, 'call.json'), JSON.stringify({ call, said, event }, null, 2));
}

main()
  .catch((e) => {
    findings.check('walk-runs', false, String(e.stack || e).slice(0, 400), {});
  })
  .finally(async () => {
    const report = { summary: findings.summary(), failures: findings.failures };
    writeFileSync(path.join(outDir, 'findings.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2).slice(0, 3000));
    await browser?.close().catch(() => {});
    if (!argv.includes('--keep')) await stack?.stop();
    process.exit(findings.failures.length ? 1 : 0);
  });
