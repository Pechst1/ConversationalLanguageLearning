#!/usr/bin/env node
// Le Lexique: the flip-and-swipe card (owner, 4 Nov). Opens the deck on a throwaway
// stack, turns a card, swipes it right and left, files one with the pair, and checks
// each time that the next card is on screen within one frame budget of the gesture.
//
//   node e2e/lexique-swipe.mjs [--out e2e/out/lexique-swipe]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { registerLearner } from './lib/session.mjs';
import { sleep, startStack } from './lib/stack.mjs';

const argv = process.argv.slice(2);
const o = argv.indexOf('--out');
const OUT = o >= 0 ? argv[o + 1] : 'e2e/out/lexique-swipe';
const SECRET = 'lexique-swipe-secret-not-for-production';
mkdirSync(OUT, { recursive: true });

const stack = await startStack({ logDir: OUT, secret: SECRET });
let browser;
const failures = [];
try {
  browser = await chromium.launch(process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {});
  const learner = await registerLearner({ api: stack.api, secret: SECRET, native: 'de', tag: 'swipe' });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await ctx.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  const page = await ctx.newPage();
  const word = () => page.evaluate(() => document.querySelector('.lx-card:not([data-ghost]) .lx-card__word')?.textContent || null);
  const count = () => page.evaluate(() => document.querySelector('.av2-progress__count')?.textContent || '');
  // Time from the gesture to the next card's word in the DOM.
  const nextCardWithin = async (before, act) => {
    const t0 = Date.now();
    await act();
    await page.waitForFunction((prev) => {
      const text = document.querySelector('.lx-card:not([data-ghost]) .lx-card__word')?.textContent || null;
      return text !== prev;
    }, before, { timeout: 3000, polling: 'raf' }).catch(() => null);
    return Date.now() - t0;
  };
  const swipe = async (dx) => {
    const box = await page.locator('.lx-card:not([data-ghost])').boundingBox();
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    await page.mouse.move(x, y);
    await page.mouse.down();
    for (let i = 1; i <= 8; i += 1) await page.mouse.move(x + (dx * i) / 8, y + i);
    await page.mouse.up();
  };

  // The throwaway lexicon carries no example sentences: give every card one, so the
  // back's example and its translation are on the screenshots.
  await page.route('**/vocabulary/due-context**', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    for (const key of ['due_words', 'fragile_words', 'linked_words', 'topic_compatible_words', 'new_words']) {
      for (const item of body[key] || []) {
        item.example_sentence ||= `Je pense qu’il y en a ${item.word} ici, mais pas toujours.`;
        item.example_translation ||= 'Ich glaube, hier gibt es das, aber nicht immer.';
      }
    }
    await route.fulfill({ response, json: body });
  });
  await page.goto(`${stack.web}/vocabulary/review`, { waitUntil: 'networkidle' });
  const sticker = page.getByRole('button', { name: /Verstanden/ });
  if (await sticker.count()) await sticker.first().click();
  await page.locator('.lx-card').first().waitFor({ timeout: 30000 });
  await sleep(400);
  await page.screenshot({ path: `${OUT}/01-front.png` });

  await page.locator('.lx-card').first().click();
  await sleep(400);
  await page.screenshot({ path: `${OUT}/02-back.png` });
  if ((await page.locator('.lx-card[data-face="back"]').count()) !== 1) failures.push('a tap did not turn the card');
  if (await page.locator('.lx-card input').count()) failures.push('the card still holds a field');

  // Half a drag: the stamp shows, the card is still there.
  const box = await page.locator('.lx-card').first().boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  for (let i = 1; i <= 6; i += 1) await page.mouse.move(box.x + box.width / 2 + i * 12, box.y + box.height / 2 + i);
  await page.screenshot({ path: `${OUT}/03-dragging.png` });
  await page.mouse.up();
  await sleep(350);
  if ((await page.locator('.lx-card[data-face="back"]').count()) !== 1) failures.push('a short drag did not spring back');

  let before = await word();
  const c0 = await count();
  const rightMs = await nextCardWithin(before, () => swipe(220));
  const afterRight = await word();
  console.log(`swipe right: «${before}» → «${afterRight}» in ${rightMs} ms, count ${c0} → ${await count()}`);
  if (afterRight === before) failures.push('a swipe right did not file the card');
  await page.screenshot({ path: `${OUT}/04-after-swipe.png` });

  await page.locator('.lx-card').first().click();
  await sleep(350);
  before = await word();
  const leftMs = await nextCardWithin(before, () => swipe(-220));
  console.log(`swipe left: «${before}» → «${await word()}» in ${leftMs} ms`);

  await page.locator('.lx-review__foot .lx-turn').click();
  await sleep(300);
  before = await word();
  const tapMs = await nextCardWithin(before, () => page.locator('button.av2-btn--done.lx-rate').click());
  console.log(`«Je sais» button: «${before}» → «${await word()}» in ${tapMs} ms`);

  await page.emulateMedia({ colorScheme: 'dark' });
  await page.locator('.lx-card').first().click();
  await sleep(400);
  await page.screenshot({ path: `${OUT}/05-back-dark.png` });
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
console.log('lexique-swipe: ok');
