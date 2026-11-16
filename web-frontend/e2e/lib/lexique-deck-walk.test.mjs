// node --test e2e/lib/lexique-deck-walk.test.mjs
//
// The day's words step lands on Le Lexique's review deck. Main's season walk stood 10 s
// on «Lexique — review 0/27 · Again · I know it» (run 43000929857, day 8) and never
// reached the recap: the walk had no hand for the deck's grades. Its selectors are
// checked here against the buttons the page renders.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { LEXIQUE_DECK } from './driver.mjs';

const PAGE = readFileSync(new URL('../../pages/vocabulary/review.tsx', import.meta.url), 'utf8');

/** The `button.class` a selector names. */
function buttonClass(selector) {
  const m = /^button\.([\w-]+):not\(\[disabled\]\)$/.exec(selector);
  assert.ok(m, `the walk's deck selector changed shape («${selector}»): update this guard with it`);
  return m[1];
}

test('the walk files a Lexique card by the buttons the deck renders', () => {
  assert.ok(LEXIQUE_DECK, 'the walk defines how it plays the Lexique deck (e2e/lib/driver.mjs LEXIQUE_DECK)');
  for (const key of ['turn', 'again', 'know']) {
    const cls = buttonClass(LEXIQUE_DECK[key]);
    const button = new RegExp(`<button\\b[^>]*className="[^"]*\\b${cls}\\b[^"]*"`);
    assert.match(PAGE, button, `the deck renders no <button> with «${cls}» (the walk's «${key}»)`);
  }
});
