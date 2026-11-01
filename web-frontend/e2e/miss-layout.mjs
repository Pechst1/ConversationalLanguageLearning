#!/usr/bin/env node
// #282 · a La Forge miss at phone size, measured in a real browser.   (from web-frontend/)
//
//   node e2e/miss-layout.mjs [--out DIR]
//   CHROMIUM_PATH=/path/to/chrome node e2e/miss-layout.mjs      (when Playwright's own build is absent)
//
// Starts only the Next dev server (no database, no API: pages/dev/miss-layout.tsx holds the
// miss itself), opens that page at 375x812 and, with «two mistakes in a row» on screen,
// asserts with bounding boxes that
//   * no cameo bubble stands on the prompt, the answer or the correction;
//   * «Compare» is fully above the pink verdict sheet (the page scrolled it clear);
//   * the field holds «à le», the words the instruction names, not «à le marché aux puces»,
//     and typing «au» alone there is what the instruction says.
// Then (#381) the live walk's line «Je voudrais un tomate, sil te plait.»: typed as the walker
// typed it, only the gap still wrong is red; with the right repair typed and accepted, the band
// under «Line fixed» takes the success state and «Not yet» is gone.
// The same predicates run in the 7-day walk (e2e/lib/miss-layout.mjs). Exit 1 on a failure.
import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SNAPSHOT_FN, TYPEABLE_FIELD } from './lib/driver.mjs';
import { missLayoutChecks } from './lib/miss-layout.mjs';
import { freePort, sleep, WEB_ROOT } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const outIndex = argv.indexOf('--out');
const outDir = path.resolve(outIndex >= 0 ? argv[outIndex + 1] : path.join(here, 'out', 'miss-layout'));
mkdirSync(outDir, { recursive: true });

async function waitFor(url, timeoutMs) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch { /* not up yet */ }
    await sleep(1000);
  }
  throw new Error(`${url} did not answer in ${timeoutMs / 1000}s`);
}

const port = await freePort();
const distDir = `.next-walk-miss-${port}`;
const next = spawn('npx', ['next', 'dev', '-p', String(port)], {
  cwd: WEB_ROOT,
  env: { ...process.env, NEXT_DIST_DIR: distDir, NEXT_TELEMETRY_DISABLED: '1', NEXTAUTH_URL: `http://localhost:${port}`, NEXTAUTH_SECRET: 'miss-layout-not-for-production' },
  detached: true,
  stdio: 'ignore',
});
const stop = () => {
  try { process.kill(-next.pid, 'SIGKILL'); } catch { /* already gone */ }
  rmSync(path.join(WEB_ROOT, distDir), { recursive: true, force: true });
};
process.on('exit', stop);


async function measure(page, label, { cameoComes = false } = {}) {
  await page.screenshot({ path: path.join(outDir, `miss-${label}.png`) });
  const snap = await page.evaluate(SNAPSHOT_FN, TYPEABLE_FIELD);
  const layout = snap.layout;
  console.log(`[${label}] layout: ${JSON.stringify(layout)}`);
  check(`${label} the miss is on screen`, layout.sheet.length === 1 && layout.exercise.length >= 1, 'no verdict sheet or prompt');
  if (cameoComes) check(`${label} a cameo stands on the miss`, layout.bubbles.length >= 1, 'no cameo bubble: the placement check would be vacuous');
  check(`${label} «Compare» is on screen`, layout.compare.length === 1, `compare boxes: ${JSON.stringify(layout.compare)}`);
  const checks = missLayoutChecks(layout);
  for (const name of ['miss-action-above-the-sheet', 'repair-field-matches-the-instruction']) {
    const found = checks.find((entry) => entry.name === name);
    check(`${label} ${name}`, Boolean(found) && found.ok, found ? found.detail : 'the screen did not offer the parts to check');
  }
  // With no bubble there is nothing over the prompt; with one, it is measured.
  const covered = checks.find((entry) => entry.name === 'miss-prompt-not-covered');
  check(`${label} miss-prompt-not-covered`, !covered || covered.ok, covered && covered.detail);
  check(`${label} the field holds exactly «à le»`, layout.gaps.length === 1 && layout.gaps[0] === 'à le', JSON.stringify(layout.gaps));
  // The learner does what the instruction says: types «au» alone over «à le».
  const gap = page.locator('.ep-parts__gap').first();
  await gap.fill('au');
  const draft = await page.locator('[data-fixture="draft"]').textContent();
  check(`${label} «au» alone repairs the line`, draft === 'Il est au marché aux puces avec Romy', `the line sent is «${draft}»`);
  // «Compare» then takes a click as it stands, with no scrolling by the test.
  const clicked = await page.locator('.ep-repair__submit').first().click({ timeout: 3000, trial: true }).then(() => null, (error) => error.message.split('\n')[0]);
  check(`${label} «Compare» takes a click (nothing in front of it)`, clicked === null, clicked);
}

/** #381: type the right repair of the walk's line and read the band under «Line fixed». */
async function repairedLine(page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(`http://localhost:${port}/dev/miss-layout?case=381`, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForSelector('.ep-parts__gap', { timeout: 120000 });
  const gaps = page.locator('.ep-parts__gap');
  check('381 the line has a gap for each correction', (await gaps.count()) === 2, `${await gaps.count()} gaps`);
  // The red every gap to fix is drawn in, before anything is typed or compared.
  const toFix = await gaps.nth(0).evaluate((node) => getComputedStyle(node).color);
  // As the walker did: the whole stretch in the gap of «un», and «plait» without its accent.
  await gaps.nth(0).fill('une tomate');
  await gaps.nth(1).fill("s'il te plait");
  const draft = await page.locator('[data-fixture="draft"]').textContent();
  check('381 «une tomate» typed in the gap of «un» is sent once', draft === "Je voudrais une tomate, s'il te plait.", `the line sent is «${draft}»`);
  await page.locator('.ep-repair__submit').first().click();
  await page.waitForSelector('.ep-repair[data-status="no"]', { timeout: 10000 });
  await page.evaluate(() => document.activeElement?.blur()); // no focus colour on a gap
  const drawn = await gaps.evaluateAll((nodes) => nodes.map((node) => ({ state: node.getAttribute('data-state'), color: getComputedStyle(node).color })));
  check('381 only the gap still wrong is red', drawn[0].state === 'fixed' && drawn[1].state === 'wrong', `gaps drawn as ${JSON.stringify(drawn)}`);
  check('381 «une tomate» is not drawn in the red of a gap to fix', drawn[0].color !== toFix, `«une tomate» is ${drawn[0].color}, a gap to fix ${toFix}`);
  check('381 «Not yet» while a word is still wrong', (await page.locator('.ep-feedback .ep-verdict[data-tone="wrong"]').count()) === 1, 'no «Not yet» band before the line is fixed');
  await page.screenshot({ path: path.join(outDir, 'repair-381-one-word-left.png') });
  // The right repair: the accent.
  await gaps.nth(1).fill("s'il te plaît");
  await page.locator('.ep-repair__submit').first().click();
  await page.waitForSelector('.ep-repair[data-status="ok"]', { timeout: 10000 });
  await sleep(500);
  await page.screenshot({ path: path.join(outDir, 'repair-381-fixed.png') });
  const snap = await page.evaluate(SNAPSHOT_FN, TYPEABLE_FIELD);
  const said = snap.epFeedback.map((feedback) => feedback.text).join(' ').replace(/\s+/g, ' ');
  check('381 «Line fixed» is on screen', /Line fixed/.test(said), said.slice(0, 240));
  check('381 «Not yet» is gone once the line is fixed', !/Not yet/i.test(said), said.slice(0, 240));
  check('381 the band shows the success state', (await page.locator('.ep-feedback .ep-foot[data-tone="correct"] .ep-verdict[data-tone="correct"]').count()) === 1, 'no success band under the fixed line');
  check('381 the answer stays a miss', snap.epFeedback.length === 1 && snap.epFeedback[0].verdict === 'wrong', JSON.stringify(snap.epFeedback.map((feedback) => feedback.verdict)));
  const banner = missLayoutChecks(snap.layout).find((entry) => entry.name === 'repaired-line-has-no-failure-banner');
  check('381 repaired-line-has-no-failure-banner', Boolean(banner) && banner.ok, banner ? banner.detail : `the screen did not offer the parts to check: ${JSON.stringify(snap.layout.repairs)}`);
}

let browser;
let failed = 0;
const check = (name, ok, detail) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${ok ? '' : `: ${detail}`}`);
  if (!ok) failed += 1;
};
try {
  await waitFor(`http://localhost:${port}/api/auth/csrf`, 120000);
  const chromePath = process.env.CHROMIUM_PATH || undefined;
  browser = await chromium.launch({ executablePath: chromePath });
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, locale: 'en-GB' });
  const page = await context.newPage();
  page.on('pageerror', (error) => console.log(`[page error] ${error.message}`));
  await page.goto(`http://localhost:${port}/dev/miss-layout`, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForSelector('.ep-feedback[data-verdict="wrong"]', { timeout: 120000 });
  // The cameo comes a moment after the miss, and the page settles (fonts, scroll) after that.
  await page.waitForSelector('.cameo-bubble', { timeout: 8000 }).catch(() => {});
  await sleep(1500);
  await page.screenshot({ path: path.join(outDir, 'miss-375x812.png') });

  await measure(page, '375x812');
  // A taller phone has room for the bubble: it must then stand clear, not merely stay away.
  await page.setViewportSize({ width: 375, height: 1100 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.ep-feedback[data-verdict="wrong"]', { timeout: 120000 });
  await page.waitForSelector('.cameo-bubble', { timeout: 8000 }).catch(() => {});
  await sleep(1500);
  await measure(page, '375x1100', { cameoComes: true });
  await repairedLine(page);
} catch (error) {
  console.log(`FAIL the page did not come up: ${error.message}`);
  failed += 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  stop();
}
process.exit(failed ? 1 : 0);
