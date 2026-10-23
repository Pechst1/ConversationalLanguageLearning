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
} catch (error) {
  console.log(`FAIL the page did not come up: ${error.message}`);
  failed += 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  stop();
}
process.exit(failed ? 1 : 0);
