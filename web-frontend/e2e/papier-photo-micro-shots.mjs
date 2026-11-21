#!/usr/bin/env node
// «La photo» and «Le micro» (2026-11-21), looked at in a browser: the walk's throwaway stack
// (fake providers, no model call, no network to Commons) for a signed-in learner, then the
// dev mock's sessions (`/revue?mock=1&photo=1` / `&micro=1`) played as a German A1, a German
// A2 and an English B1 learner at 375 × 812. Every screen is saved as `p-…` / `m-…` into the
// evidence folder (or --out), with a line per screen: buttons under 44 px, a horizontal
// scroll, the newest part hidden under the foot.
//
//   node e2e/papier-photo-micro-shots.mjs [--out DIR] [--only photo|micro]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { registerLearner } from './lib/session.mjs';
import { startStack } from './lib/stack.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const out = path.resolve(opt('out', path.join(here, '..', '..', 'docs/implementation/atelier-v2/evidence/papier-nouvelle-formule-2026-11-20')));
const only = opt('only', '');
const SECRET = 'e3-walk-secret-not-for-production';
mkdirSync(out, { recursive: true });
const logDir = path.join(here, 'out', `photo-micro-${Date.now()}`);

const report = [];

async function check(page, name) {
  const found = await page.evaluate(() => {
    const vis = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const small = Array.from(document.querySelectorAll('button, a, [role=radio]'))
      .filter((el) => vis(el) && !el.closest('.rv-picture__cap'))
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.height < 43.5 || r.width < 43.5)
      .map(({ el, r }) => `${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 24)} ${Math.round(r.width)}×${Math.round(r.height)}`);
    const foot = document.querySelector('.rv-foot');
    const footTop = foot ? foot.getBoundingClientRect().top : window.innerHeight;
    const anchors = Array.from(document.querySelectorAll('[data-ct-anchor]')).filter(vis);
    const newest = anchors[anchors.length - 1];
    const r = newest ? newest.getBoundingClientRect() : null;
    return {
      small,
      overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
      newestHidden: r ? r.top > footTop - 8 || r.bottom < 0 : false,
    };
  });
  report.push({ name, ...found });
  console.log(`${name}: small=${found.small.length ? found.small.join(' | ') : '-'} overflowX=${found.overflowX} newestHidden=${found.newestHidden}`);
}

async function shot(page, name, { full = false } = {}) {
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: full, animations: 'disabled' });
  await check(page, name);
}

const click = async (page, text, { exact = false } = {}) => {
  const pattern = text.startsWith('(?:') ? text : text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const target = page.locator('button:not([disabled])', { hasText: exact ? new RegExp(`^\\s*${pattern}\\s*$`) : text }).first();
  await target.scrollIntoViewIfNeeded();
  await target.click();
  await page.waitForTimeout(900);
};
const pick = async (page, n) => {
  await page.locator('.rb-planche__pick').nth(n).click();
  await page.waitForTimeout(500);
};
/** An option or a word button (never a tappable word of a line: those open the word help). */
const option = async (page, text) => {
  const esc = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const target = page.locator('.ct-opt:not([disabled]), .rb-seen__w:not([disabled])', { hasText: new RegExp(`^\\s*${esc}\\s*$`) }).first();
  await target.scrollIntoViewIfNeeded();
  await target.click();
  await page.waitForTimeout(900);
};
const verify = async (page) => click(page, '(?:Check|Vérifier|Prüfen)', { exact: true });
const foot = async (page) => {
  const target = page.locator('.rv-foot button:not([disabled])').last();
  await target.click();
  await page.waitForTimeout(1100);
};
const type = async (page, text) => {
  const field = page.locator('textarea:not([disabled]), input[type=text]:not([disabled])').last();
  await field.scrollIntoViewIfNeeded();
  await field.fill(text);
  await page.waitForTimeout(300);
};
const open = async (page, web, query, prefix) => {
  await page.goto(`${web}/revue?mock=1&reset=1&${query}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await shot(page, `${prefix}-00-chooser`);
  await page.locator('.rv-une button').first().click();
  await page.waitForTimeout(1500);
  await shot(page, `${prefix}-1-lire`);
  await foot(page);
};

async function photoA1(page, web) {
  const p = 'p-a1de';
  await open(page, web, 'photo=1&band=A1&lang=de', p);
  await shot(page, `${p}-2-planche`);
  await pick(page, 0);
  await foot(page);
  await shot(page, `${p}-2-planche-miss`);
  await pick(page, 1);
  await foot(page);
  await shot(page, `${p}-2-seen`);
  await option(page, 'Paris');
  await option(page, 'une guitare');
  await foot(page);
  await shot(page, `${p}-2-seen-miss`);
  await option(page, 'une guitare');
  await option(page, 'une guitare acoustique');
  await foot(page);
  await shot(page, `${p}-2-seen-right`);
  await foot(page);
  await shot(page, `${p}-3-legende`);
  await page.locator('[role=radio][aria-label*="Paris"]').first().click();
  await foot(page);
  await shot(page, `${p}-3-legende-miss`);
  await page.locator('[role=radio][aria-label*="14 juillet"]').first().click();
  await foot(page);
  await shot(page, `${p}-3-fix`);
  await option(page, 'en 1982');
  await shot(page, `${p}-3-fix-miss`);
  await option(page, 'le 21 juin');
  await shot(page, `${p}-3-fix-done`);
  await foot(page);
  await shot(page, `${p}-4-build`);
  await pick(page, 1);
  await click(page, 'une guitare');
  await click(page, 'La fête est gratuite.');
  await shot(page, `${p}-4-built`);
  await foot(page);
  await shot(page, `${p}-4-printed`);
  await foot(page);
  await shot(page, `${p}-5-page`);
  await shot(page, `${p}-5-page-full`, { full: true });
}

async function photoA2(page, web) {
  const p = 'p-a2de';
  await open(page, web, 'photo=1&band=A2&lang=de&pourquoi=1', p);
  await pick(page, 1);
  await foot(page);
  await option(page, 'une guitare');
  await option(page, 'une guitare acoustique');
  await foot(page);
  await foot(page);
  await page.locator('[role=radio][aria-label*="14 juillet"]').first().click();
  await foot(page);
  await option(page, 'le 21 juin');
  await foot(page);
  await pick(page, 1);
  await shot(page, `${p}-4-build`);
  await type(page, 'Au premier plan, on voit une guitare tres belle. La fête est gratuite.');
  await foot(page);
  await shot(page, `${p}-4-build-marked`);
  const mark = page.locator('.ct-paper [aria-expanded], .ct-paper button').first();
  if (await mark.count()) {
    await mark.click();
    await page.waitForTimeout(600);
    await shot(page, `${p}-4-build-why`);
  }
  await type(page, 'Au premier plan, on voit une guitare très belle. La fête est gratuite.');
  await page.locator('.rv-foot button:not([disabled])').first().click();
  await page.waitForTimeout(1200);
  await shot(page, `${p}-4-build-fixed`);
  await foot(page);
  await shot(page, `${p}-5-page`, { full: true });
}

async function photoB1(page, web) {
  const p = 'p-b1en';
  await open(page, web, 'photo=1&band=B1&lang=en', p);
  await pick(page, 1);
  await foot(page);
  await option(page, 'une guitare');
  await option(page, 'une guitare acoustique');
  await foot(page);
  await foot(page);
  await page.locator('[role=radio][aria-label*="14 juillet"]').first().click();
  await foot(page);
  await shot(page, `${p}-3-fix`);
  await type(page, 'La fête a lieu le 14 juillet.');
  await verify(page);
  await shot(page, `${p}-3-fix-miss`);
  await type(page, 'La première fête a eu lieu le 21 juin 1982.');
  await verify(page);
  await shot(page, `${p}-3-fix-done`);
  await foot(page);
  await pick(page, 1);
  await type(page, 'On voit une guitare.');
  await foot(page);
  await shot(page, `${p}-4-build-refused`);
  await type(page, 'On voit une guitare acoustique, tres belle. La fête est gratuite.');
  await foot(page);
  await shot(page, `${p}-4-build-marked`);
  await type(page, 'On voit une guitare acoustique, très belle. La fête est gratuite.');
  await page.locator('.rv-foot button:not([disabled])').first().click();
  await page.waitForTimeout(1200);
  await shot(page, `${p}-4-build-fixed`);
  await foot(page);
  await shot(page, `${p}-5-page`, { full: true });
}

async function microA1(page, web) {
  const p = 'm-a1de';
  await open(page, web, 'micro=1&band=A1&lang=de', p);
  await shot(page, `${p}-2-prepare`);
  await click(page, 'Combien ça coûte ?');
  await click(page, 'Quand, la première fête ?');
  await click(page, 'Quelles musiques ?');
  await shot(page, `${p}-2-prepare-chosen`);
  await foot(page);
  await foot(page);
  await shot(page, `${p}-3-interview`);
  await click(page, 'Combien coûte la fête ?');
  await foot(page);
  await shot(page, `${p}-3-interview-answer`);
  await click(page, 'Quand est-ce que');
  await foot(page);
  await click(page, 'Quelles musiques est-ce');
  await foot(page);
  await shot(page, `${p}-3-interview-done`);
  await foot(page);
  await shot(page, `${p}-4-notes`);
  await option(page, 'du bruit').catch(() => {});
  await shot(page, `${p}-4-notes-miss`);
  for (const value of ['gratuite', 'le 21 juin 1982', 'toutes les musiques']) await option(page, value).catch(() => {});
  await shot(page, `${p}-4-notes-done`);
  await foot(page);
  await shot(page, `${p}-5-review`);
  await foot(page);
  await shot(page, `${p}-5-review-clean`);
  await foot(page);
  await shot(page, `${p}-6-page`, { full: true });
}

async function microA2(page, web) {
  const p = 'm-a2de';
  await open(page, web, 'micro=1&band=A2&lang=de&pourquoi=1', p);
  await click(page, 'Combien ça coûte ?');
  await click(page, 'Quand, la première fête ?');
  await click(page, 'Quelles musiques ?');
  await foot(page);
  await foot(page);
  await shot(page, `${p}-3-interview`);
  await type(page, 'Qui organise la fête ?');
  await foot(page);
  await shot(page, `${p}-3-interview-shrug`);
  await click(page, 'Combien coûte…');
  await type(page, 'Pourquoi elle est gratuite ?');
  await foot(page);
  await shot(page, `${p}-3-interview-slip`);
  await type(page, 'Quand est-ce que la première fête a eu lieu ?');
  await foot(page);
  await type(page, "Quelles musiques est-ce qu'on peut écouter ?");
  await foot(page);
  await shot(page, `${p}-3-interview-done`);
  await foot(page);
  await shot(page, `${p}-4-notes`);
  for (const value of ['gratuite', 'le 21 juin 1982', 'toutes les musiques']) await option(page, value).catch(() => {});
  await shot(page, `${p}-4-notes-done`);
  await foot(page);
  await shot(page, `${p}-5-review`);
  await foot(page);
  await shot(page, `${p}-5-review-sent`);
  await foot(page);
  await shot(page, `${p}-6-page`, { full: true });
}

async function microB1(page, web) {
  const p = 'm-b1en';
  await open(page, web, 'micro=1&band=B1&lang=en', p);
  await click(page, 'Combien ça coûte ?');
  await click(page, 'Quand, la première fête ?');
  await click(page, 'Quelles musiques ?');
  await foot(page);
  await foot(page);
  await type(page, 'Quand est-ce que la première fête, tres attendue, a eu lieu ?');
  await foot(page);
  await shot(page, `${p}-3-interview`);
  await type(page, 'Ça coûte combien ?');
  await foot(page);
  await type(page, "Quelles musiques est-ce qu'on peut écouter ?");
  await foot(page);
  await foot(page);
  await type(page, 'le 21 juin 1983');
  await verify(page);
  await shot(page, `${p}-4-notes-miss`);
  const fields = page.locator('textarea:not([disabled]), input[type=text]:not([disabled])');
  const values = ['le 21 juin 1982', 'gratuite', 'toutes les musiques'];
  for (let i = 0; i < 3; i += 1) {
    const field = fields.first();
    if (!(await field.count())) break;
    await field.fill(values[i]);
    await verify(page);
  }
  await shot(page, `${p}-4-notes-done`);
  await foot(page);
  await foot(page);
  await shot(page, `${p}-5-review-marked`);
  const draft = await page.locator('textarea').last().inputValue().catch(() => '');
  if (draft) {
    await page.locator('textarea').last().fill(draft.replace('tres', 'très'));
    await page.locator('.rv-foot button:not([disabled])').first().click();
    await page.waitForTimeout(1200);
  }
  await shot(page, `${p}-5-review-fixed`);
  await foot(page);
  await shot(page, `${p}-6-page`, { full: true });
}

const stack = await startStack({ logDir, secret: SECRET, revue: true });
const browser = await chromium.launch();
try {
  const flows = [
    ['photo', 'de', 'A1.1', photoA1],
    ['photo', 'de', 'A2.1', photoA2],
    ['photo', 'en', 'B1.1', photoB1],
    ['micro', 'de', 'A1.1', microA1],
    ['micro', 'de', 'A2.1', microA2],
    ['micro', 'en', 'B1.1', microB1],
  ].filter(([kind]) => !only || kind === only);
  for (const [kind, native, level, flow] of flows) {
    const learner = await registerLearner({ api: stack.api, secret: SECRET, native, level, tag: `pm-${kind}` });
    const context = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, colorScheme: 'light' });
    await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
    const page = await context.newPage();
    page.on('pageerror', (e) => console.log(`PAGEERROR ${kind} ${level}: ${e.message}`));
    try {
      await flow(page, stack.web);
    } catch (e) {
      console.log(`FLOW FAILED ${kind} ${level}: ${e.message}`);
      await page.screenshot({ path: path.join(logDir, `failed-${kind}-${level}.png`) }).catch(() => {});
    }
    await context.close();
  }
} finally {
  await browser.close();
  await stack.stop();
}
console.log(JSON.stringify(report.filter((r) => r.small.length || r.overflowX || r.newestHidden), null, 1));
