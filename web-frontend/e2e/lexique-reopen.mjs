#!/usr/bin/env node
// Le Lexique: a card filed with «je sais» stays filed (owner, 2026-10-18).
//
// The deck opens on the copy cached on the device and asks the server for the
// fresh one at the same time. The owner tapped «je sais» on his phone and the
// card did not go: the reopened deck showed words already filed, and when the
// slower fresh deck landed it reset the sitting, so cards just answered came
// back and the count fell from 3/8 to 0/6. This walk files two cards, leaves,
// reopens with the fresh deck held back, files cards meanwhile and asserts no
// word is asked twice and the count never goes back.
//
//   SECRET_KEY=... node e2e/lexique-reopen.mjs [--delay 5000]
import { chromium, devices } from '@playwright/test';
import { registerLearner } from './lib/session.mjs';
import { sleep, startStack } from './lib/stack.mjs';

const argv = process.argv.slice(2);
const i = argv.indexOf('--delay');
const DELAY = i >= 0 ? Number(argv[i + 1]) : 5000;
const SECRET = 'lexique-reopen-secret-not-for-production';

const stack = await startStack({ logDir: 'e2e/out/lexique-reopen', secret: SECRET });
let browser;
const failures = [];
try {
  browser = await chromium.launch(process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {});
  const learner = await registerLearner({ api: stack.api, secret: SECRET, native: 'de', tag: 'lexique' });
  const ctx = await browser.newContext({ ...devices['iPhone 15 Pro'] });
  await ctx.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  const page = await ctx.newPage();
  const card = () => page.evaluate(() => ({
    word: document.querySelector('.lx-card[data-face="front"] .lx-card__word')?.textContent || null,
    count: document.querySelector('.av2-progress__count')?.textContent || '',
  }));
  // «je sais» twice: the first tap turns the card, the second files it.
  const know = async () => {
    for (let tap = 0; tap < 2; tap++) {
      await page.locator('button.av2-btn--done.lx-rate').tap();
      await sleep(tap ? 700 : 250);
    }
  };
  const filed = [];
  let lastDone = 0;
  const fileOne = async (label) => {
    const { word, count } = await card();
    if (!word) return false;
    const done = Number(count.split('/')[0] || 0);
    if (filed.includes(word)) failures.push(`${label}: «${word}» was asked again after «je sais»`);
    if (done < lastDone) failures.push(`${label}: the count went back to ${count}`);
    lastDone = done;
    filed.push(word);
    await know();
    return true;
  };

  await page.goto(`${stack.web}/vocabulary/review`, { waitUntil: 'networkidle' });
  const sticker = page.getByRole('button', { name: /Verstanden/ });
  if (await sticker.count()) await sticker.first().click();
  for (let n = 0; n < 2; n++) await fileOne('first visit');

  await page.route('**/vocabulary/due-context**', async (route) => {
    const response = await route.fetch();
    await sleep(DELAY);
    await route.fulfill({ response });
  });
  await page.goto(`${stack.web}/vocabulary/review`, { waitUntil: 'domcontentloaded' });
  await page.locator('.lx-card').waitFor();
  lastDone = 0;
  for (let n = 0; n < 12; n++) if (!(await fileOne('reopened'))) break;
  console.log(`filed: ${filed.join(', ')}`);
} finally {
  await browser?.close();
  await stack.stop();
}
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log('ok: every filed card stayed filed');
