#!/usr/bin/env node
// #851 (live walk 17 Nov): on the first Lexique visit, with the first-time note still
// open, «I know it» did nothing: the card turned back to its front and the count stayed
// 0/15, fifteen taps in a row. A tap aimed at «I know it» by its name reached the turned
// card instead (it carried the drag stamps «Again» / «I know it» as its own text, and a
// tap on the card turns it back). This plays a new account's first deck the way the
// walks tap, by the words on screen, and checks that each grade files its card.
//
//   node e2e/lexique-first-visit.mjs [--out e2e/out/lexique-first-visit]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { registerLearner } from './lib/session.mjs';
import { sleep, startStack } from './lib/stack.mjs';

const argv = process.argv.slice(2);
const o = argv.indexOf('--out');
const OUT = o >= 0 ? argv[o + 1] : 'e2e/out/lexique-first-visit';
const SECRET = 'lexique-first-visit-secret-not-for-production';
mkdirSync(OUT, { recursive: true });

// The walks' own hand (e2e/explore.mjs, e2e/explore-live.mjs): the first visible control
// whose words hold the label.
const CONTROLS = 'button, a[href], [role=button], [role=tab], [role=radio], [role=option], input[type=checkbox], input[type=radio], select';

const stack = await startStack({ logDir: OUT, secret: SECRET });
let browser;
const failures = [];
try {
  browser = await chromium.launch(process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {});
  const learner = await registerLearner({ api: stack.api, secret: SECRET, native: 'en', tag: 'firstlex' });
  const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
  await ctx.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  const page = await ctx.newPage();
  const tapByName = (text) => page.locator(CONTROLS).filter({ visible: true }).filter({ hasText: text }).first().click({ timeout: 8000 });
  const count = () => page.evaluate(() => document.querySelector('.av2-progress__count')?.textContent || '');
  const filed = (label) => Number(String(label).split('/')[0] || 0);
  const word = () => page.evaluate(() => document.querySelector('.lx-card:not([data-ghost]) .lx-card__word')?.textContent || null);

  await page.goto(`${stack.web}/vocabulary/review`, { waitUntil: 'networkidle' });
  await page.locator('.lx-card').first().waitFor({ timeout: 30000 });
  await sleep(400);
  // The first visit: the note is open, and it stays open for the whole check.
  if (!(await page.locator('[data-first-step="words"]').count())) failures.push('the first Lexique visit shows no first-time note');

  // «I know it» counts the card (0/8 → 1/8); «Again» files it to be asked again at the end,
  // so the count holds and the next card comes up.
  for (const [round, grade, counts] of [[1, 'I know it', 1], [2, 'Again', 0], [3, 'I know it', 1]]) {
    const before = await count();
    const wordBefore = await word();
    await tapByName('Show the answer');
    await sleep(300);
    if ((await page.locator('.lx-card[data-face="back"]').count()) !== 1) failures.push(`round ${round}: «Show the answer» did not turn the card`);
    if (round === 1) {
      // The drag stamps still show their word (drawn by CSS, not written in the card).
      const stamp = await page.evaluate(() => getComputedStyle(document.querySelector('.lx-stamp--know'), '::after').content);
      if (!/I know it/.test(stamp)) failures.push(`the «I know it» stamp draws ${stamp}`);
    }
    await tapByName(grade);
    await sleep(500);
    const after = await count();
    const wordAfter = await word();
    console.log(`round ${round}: «${grade}» ${before} → ${after}, «${wordBefore}» → «${wordAfter}»`);
    if (filed(after) !== filed(before) + counts || wordAfter === wordBefore) {
      failures.push(`round ${round}: one tap on «${grade}» with the first-time note open left the count at ${after} (was ${before}) and the card on «${wordAfter}», its ${await page.locator('.lx-card:not([data-ghost])').first().getAttribute('data-face')} up`);
      await page.screenshot({ path: `${OUT}/round-${round}.png` });
      break;
    }
  }
  if (!(await page.locator('[data-first-step="words"]').count())) failures.push('the first-time note closed by itself');
} catch (error) {
  failures.push(String(error?.stack || error));
} finally {
  await browser?.close();
  await stack.stop?.();
}
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log('lexique-first-visit: ok');
