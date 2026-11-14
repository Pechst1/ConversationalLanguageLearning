#!/usr/bin/env node
// Owner 2026-11-13 · La Forge's free-sentence item and its miss, photographed at phone size
// in de, en and fr (from web-frontend/):
//
//   node e2e/forge-reading-shots.mjs --out DIR [--root WEB_ROOT] [--cases item,withheld,shown]
//
// Starts only the Next dev server (no database, no API: pages/dev/forge-reading.tsx holds
// the screens) and writes `<case>-<lang>.png` at 375x812 for each case, plus the miss in the
// dark theme and at 125 % text. `--root` points it at another checkout of web-frontend (an
// extract of origin/main with the same fixture page) for the «before» images.
import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import path from 'node:path';
import { freePort, sleep, WEB_ROOT } from './lib/stack.mjs';

const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const index = argv.indexOf(name);
  return index >= 0 ? argv[index + 1] : fallback;
};
const outDir = path.resolve(arg('--out', path.join(WEB_ROOT, 'e2e', 'out', 'forge-reading')));
const root = path.resolve(arg('--root', WEB_ROOT));
const cases = arg('--cases', 'item,withheld,shown').split(',');
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
const distDir = `.next-forge-reading-${port}`;
const next = spawn('npx', ['next', 'dev', '-p', String(port)], {
  cwd: root,
  env: { ...process.env, NEXT_DIST_DIR: distDir, NEXT_TELEMETRY_DISABLED: '1', NEXTAUTH_URL: `http://localhost:${port}`, NEXTAUTH_SECRET: 'forge-reading-not-for-production' },
  detached: true,
  stdio: 'ignore',
});
const stop = () => {
  try { process.kill(-next.pid, 'SIGKILL'); } catch { /* already gone */ }
  rmSync(path.join(root, distDir), { recursive: true, force: true });
};
process.on('exit', stop);

let browser;
let failed = 0;
try {
  await waitFor(`http://localhost:${port}/api/auth/csrf`, 180000);
  browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const shoot = async ({ lang, shot, scheme = 'light', textScale = 1, name }) => {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: scheme });
    const page = await context.newPage();
    page.on('pageerror', (error) => console.log(`[page error] ${error.message}`));
    await page.goto(`http://localhost:${port}/dev/forge-reading?case=${shot}&lang=${lang}`, { waitUntil: 'domcontentloaded', timeout: 180000 });
    await page.waitForSelector('.ep-exercise', { timeout: 180000 });
    if (scheme === 'dark') await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
    if (textScale !== 1) await page.addStyleTag({ content: `html { font-size: ${textScale * 100}% !important; }` });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await sleep(1800); // the miss scroll settles (lib/keep-above-sheet.ts)
    await page.screenshot({ path: path.join(outDir, `${name}.png`) });
    // The page never scrolls sideways at phone width.
    const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    if (wide) { console.log(`FAIL ${name}: the page scrolls sideways`); failed += 1; }
    console.log(`ok   ${name}`);
    await context.close();
  };
  for (const shot of cases) {
    for (const lang of ['de', 'en', 'fr']) await shoot({ lang, shot, name: `${shot}-${lang}` });
  }
  const miss = cases.includes('withheld') ? 'withheld' : cases[cases.length - 1];
  await shoot({ lang: 'de', shot: miss, scheme: 'dark', name: `${miss}-de-dark` });
  await shoot({ lang: 'de', shot: miss, textScale: 1.25, name: `${miss}-de-text125` });
  if (cases.includes('item')) await shoot({ lang: 'de', shot: 'item', scheme: 'dark', name: 'item-de-dark' });
} catch (error) {
  console.log(`FAIL the page did not come up: ${error.message}`);
  failed += 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  stop();
}
process.exit(failed ? 1 : 0);
