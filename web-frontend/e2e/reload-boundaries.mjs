#!/usr/bin/env node
// Progress never depends on what one tab remembers (2026-10-09).
//
// A learner answered a word card, reloaded (or closed the app, or answered on a
// second device) before «Continue», and the day was stuck: the verdict and its
// «Continue» lived only in the tab. This walk plays day 1 on its own throwaway
// stack (fake provider, nothing paid) and, at every boundary it meets — a verdict
// on screen, the middle of the scene, a conversation after its first reply, the
// screen after the last step — reloads the tab, comes back in from Home and
// asserts the day still goes forward to the recap. A second pass answers steps
// in a second browser context signed in as the same learner while the first one
// still shows the question, then carries on in the first.
//
//   PATH=<repo>/venv/bin:$PATH node e2e/reload-boundaries.mjs [--keep] [--mode reload|second-device|both]
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Findings } from './lib/assertions.mjs';
import { snapshot } from './lib/driver.mjs';
import { LearnerWalk } from './lib/learner-walk.mjs';
import { registerLearner } from './lib/session.mjs';
import { sleep, startStack } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const mode = opt('mode', 'both');
const SECRET = 'e3-walk-secret-not-for-production';
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outDir = path.join(here, 'out', `reload-${stamp}`);
mkdirSync(outDir, { recursive: true });
const findings = new Findings();
const shots = { root: outDir, list: [] };
const log = (...a) => console.log('[reload]', ...a);

/** «Step 3 of 8» / «Panel 2 of 6» — where in the day a boundary is. */
function position(s) {
  const step = s.text.match(/Step (\d+) of (\d+)/);
  const panel = s.text.match(/Panel (\d+) of (\d+)/);
  const exchange = s.text.match(/Exchange (\d+) of (\d+)/);
  return [step && `step${step[1]}`, panel && `panel${panel[1]}`, exchange && `ex${exchange[1]}`].filter(Boolean).join('-') || 'screen';
}

/** The boundary this screen is, or null: where a tab's memory could matter. */
function boundaryOf(s, kind) {
  const verdict = s.graded[0]?.state || s.epFeedback[0]?.verdict;
  if (verdict) return `verdict:${position(s)}`;
  if (kind === 'reader') {
    const m = s.text.match(/Panel (\d+) of (\d+)/);
    if (m && m[1] !== '1' && m[1] !== m[2]) return `mid-scene:${position(s)}`;
  }
  if (kind === 'thread' && /Exchange 2 of/.test(s.text)) return `mid-conversation:${position(s)}`;
  return null;
}

async function makeWalk(browser, stack, learner, label) {
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, locale: 'en-GB' });
  await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  const walk = new LearnerWalk({ page: null, findings, outDir: path.join(outDir, label), lang: 'en', level: 'A1.1', stack, shots, scale: 1 });
  await walk.newSession(context);
  walk.day = 1;
  return { context, walk };
}

/** Home → the day's primary action, as a learner coming back would. */
async function enterFromHome(walk, stack) {
  const page = walk.page;
  await page.goto(`${stack.web}/atelier`, { waitUntil: 'domcontentloaded' });
  const ready = await page.locator('.av2-btn--primary').first().waitFor({ timeout: 45000 }).then(() => true, () => false);
  if (!ready) return false;
  const s = await snapshot(page);
  if (walk.classify(s) === 'home-done') return true;
  await page.locator('.av2-btn--primary').first().click({ timeout: 5000 }).catch(() => {});
  await sleep(2500);
  return true;
}

/**
 * Play the day to its recap. `onBoundary(s, kind, key)` runs once per boundary key
 * and may reload or act elsewhere; afterwards the day must still move: 15 s with
 * no change and nothing pending is a finding.
 */
async function playWith(walk, stack, onBoundary, label) {
  const page = walk.page;
  const state = { itemIndex: 0, typing: false, readerBox: null };
  const seen = new Set();
  let lastSig = '';
  let sameFor = 0;
  let afterBoundary = null;
  const t0 = Date.now();
  if (!(await enterFromHome(walk, stack))) {
    findings.check('home-loads', false, 'Home never showed its primary action', { label });
    return false;
  }
  while (Date.now() - t0 < 300000) {
    await sleep(250);
    const s = await snapshot(page);
    const kind = walk.classify(s);
    const sig = `${kind}|${s.text.slice(0, 200)}|${s.graded.map((g) => g.state).join()}`;
    if (sig !== lastSig) {
      lastSig = sig;
      sameFor = 0;
      if (afterBoundary) {
        log(label, 'moved on after', afterBoundary, '→', kind, position(s));
        afterBoundary = null;
      }
    } else sameFor += 1;
    if (kind === 'recap' || kind === 'home-done') {
      log(label, 'reached', kind, `in ${((Date.now() - t0) / 1000).toFixed(0)}s; boundaries:`, [...seen].join(', '));
      await walk.shoot(`${label}-end-${kind}`);
      findings.check('day-reaches-the-recap', true, '', { label });
      return true;
    }
    const key = boundaryOf(s, kind);
    if (key && !seen.has(key)) {
      seen.add(key);
      log(label, 'boundary', key);
      await walk.shoot(`${label}-before-${key.replace(/[^\w-]/g, '_')}`);
      await onBoundary(s, kind, key);
      afterBoundary = key;
      lastSig = '';
      continue;
    }
    let acted = await walk.act(s, kind, state);
    if (!acted) {
      // The «This scene moved on» notice offers a quiet «Continue», not a primary one.
      const quiet = page.locator('main button', { hasText: /^(Continue|Weiter|Continuer)$/ }).first();
      if (await quiet.count()) acted = await quiet.click({ timeout: 3000 }).then(() => true, () => false);
    }
    if (!acted && sameFor > (s.pending ? 180 : 60)) {
      findings.check('a-way-forward-after-a-boundary', false, `stuck ${(sameFor / 4).toFixed(0)}s after «${afterBoundary || 'start'}» on «${s.text.slice(0, 160)}»`, { label, kind });
      await walk.shoot(`${label}-stuck`);
      return false;
    }
    if (acted && sameFor > 120) {
      // Acting without the screen changing: the «This scene moved on» loop.
      findings.check('a-way-forward-after-a-boundary', false, `acting changes nothing for ${(sameFor / 4).toFixed(0)}s after «${afterBoundary || 'start'}» on «${s.text.slice(0, 160)}»`, { label, kind });
      await walk.shoot(`${label}-loop`);
      return false;
    }
  }
  findings.check('day-reaches-the-recap', false, 'five minutes without a recap', { label });
  return false;
}

async function main() {
  const stack = await startStack({ logDir: outDir, secret: SECRET });
  const browser = await chromium.launch();
  let ok = true;
  try {
    if (mode === 'reload' || mode === 'both') {
      const learner = await registerLearner({ api: stack.api, secret: SECRET, native: 'en', level: 'A1.1', tag: 'reload' });
      const { walk } = await makeWalk(browser, stack, learner, 'reload');
      ok = (await playWith(walk, stack, async () => {
        // The learner closes the app here and comes back from Home.
        await enterFromHome(walk, stack);
      }, 'reload')) && ok;
    }
    if (mode === 'second-device' || mode === 'both') {
      const learner = await registerLearner({ api: stack.api, secret: SECRET, native: 'en', level: 'A1.1', tag: 'twodev' });
      const a = await makeWalk(browser, stack, learner, 'device-a');
      const b = await makeWalk(browser, stack, learner, 'device-b');
      ok = (await playWith(a.walk, stack, async (s, kind) => {
        // The phone shows this screen; the learner carries on on the laptop until
        // the screen there changes once, then picks the phone up again.
        await enterFromHome(b.walk, stack);
        const stateB = { itemIndex: 0, typing: false, readerBox: null };
        const before = (await snapshot(b.walk.page)).text.slice(0, 200);
        for (let i = 0; i < 40; i += 1) {
          const sb = await snapshot(b.walk.page);
          if (sb.text.slice(0, 200) !== before && i > 0) break;
          await b.walk.act(sb, b.walk.classify(sb), stateB);
          await sleep(500);
        }
        await sleep(1000);
      }, 'second-device')) && ok;
    }
  } finally {
    writeFileSync(path.join(outDir, 'findings.json'), JSON.stringify(findings.results, null, 2));
    await browser.close().catch(() => {});
    if (!argv.includes("--keep")) await stack.stop().catch(() => {});
  }
  const failed = findings.failures || [];
  log('findings:', JSON.stringify(failed).slice(0, 2000));
  log('out:', outDir);
  process.exit(ok && !(failed && failed.length) ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
