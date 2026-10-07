#!/usr/bin/env node
// WP-143 · before/after captures of the stage: a day-1 scene panel with speakers and the
// Papier's stage on its first beat, at 375×812, light and dark. Uses an already running
// stack (FRONTEND_URL, API_URL with /api/v1, NEXTAUTH_SECRET of that Next server).
//
//   FRONTEND_URL=http://localhost:3143 API_URL=http://127.0.0.1:8143/api/v1 \
//   NEXTAUTH_SECRET=... node e2e/wp143-capture.mjs <out-dir> <label>
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { Findings } from './lib/assertions.mjs';
import { snapshot } from './lib/driver.mjs';
import { LearnerWalk } from './lib/learner-walk.mjs';
import { registerLearner } from './lib/session.mjs';

const web = process.env.FRONTEND_URL || 'http://localhost:3143';
const api = process.env.API_URL || 'http://127.0.0.1:8143/api/v1';
const secret = process.env.NEXTAUTH_SECRET;
const outDir = path.resolve(process.argv[2] || 'e2e/out/wp143');
const label = process.argv[3] || 'after';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
mkdirSync(outDir, { recursive: true });

async function shoot(page, name) {
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme });
    await sleep(400);
    await page.screenshot({ path: path.join(outDir, `${name}-${label}-${scheme}.png`), animations: 'disabled' });
  }
  await page.emulateMedia({ colorScheme: 'light' });
}

async function main() {
  const browser = await chromium.launch();
  const learner = await registerLearner({ api, secret, native: 'en', level: 'A1.1', tag: 'wp143' });
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: 'en-GB' });
  await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: web }]);
  await context.addInitScript(() => {
    try { window.localStorage.setItem('atelier.artSet', 'drawn'); } catch { /* refused */ }
  });
  const page = await context.newPage();
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));

  // 1. Day 1: play the day as the walk does until the reader shows a panel with two
  //    or more figures on the plate.
  const walk = new LearnerWalk({ page, findings: new Findings(), outDir, lang: 'en', level: 'A1.1', stack: { web }, shots: { root: outDir, list: [] }, scale: 2 });
  await page.goto(`${web}/atelier`, { waitUntil: 'domcontentloaded' });
  await page.locator('.av2-btn--primary').first().waitFor({ timeout: 60000 });
  await page.locator('.av2-btn--primary').first().click();
  const state = { itemIndex: 0, typing: false, readerBox: null };
  let shot = false;
  const t0 = Date.now();
  while (!shot && Date.now() - t0 < 240000) {
    await sleep(400);
    const figures = await page.locator('.cast-stage .cast-stage__figure:not(.cast-stage__figure--you)').count();
    if (figures >= 2) {
      await sleep(1500); // the plate and the grade settle
      await page.locator('.cast-stage').first().scrollIntoViewIfNeeded().catch(() => {});
      await shoot(page, 'day1-panel');
      shot = true;
      break;
    }
    const s = await snapshot(page);
    await walk.act(s, walk.classify(s), state);
  }
  // 2. Le Papier, the mock, first beat.
  await page.goto(`${web}/revue?mock=1&lang=de&band=A2&reset=1`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  for (let i = 0; i < 12; i += 1) {
    if (await page.locator('.rv-encounter .rv-stage .cast-stage').count()) break;
    const go = page.locator('.rv-page .av2-btn--primary:not([disabled])').first();
    if (await go.count()) await go.click({ timeout: 3000 }).catch(() => {});
    await sleep(1200);
  }
  await sleep(1500);
  await shoot(page, 'revue-arrive');
  const boxes = await page.evaluate(() => {
    const stage = document.querySelector('.rv-encounter .rv-stage');
    if (!stage) return null;
    const s = stage.getBoundingClientRect();
    // Each figure's head box, `data-head="x y w h"` in % of the cast stage, as viewport pixels.
    const cast = stage.querySelector('.cast-stage');
    const c = (cast || stage).getBoundingClientRect();
    const heads = [...stage.querySelectorAll('[data-head]')].map((el) => {
      const [x, y, w, h] = el.getAttribute('data-head').split(' ').map(Number);
      const left = c.left + (x / 100) * c.width;
      const top = c.top + (y / 100) * c.height;
      return [left, top, left + (w / 100) * c.width, top + (h / 100) * c.height].map(Math.round);
    });
    const inside = heads.every(([l, t, r, b]) => l >= s.left && t >= s.top && r <= s.right && b <= s.bottom);
    return { stage: [s.left, s.top, s.right, s.bottom].map(Math.round), heads, inside };
  });
  console.log(JSON.stringify({ label, boxes }));
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
