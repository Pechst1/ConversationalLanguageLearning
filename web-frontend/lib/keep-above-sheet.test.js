// node --test lib/keep-above-sheet.test.js
//
// #239: after a La Forge miss the correction card (the right sentence and the
// reason) is scrolled into the space between the sticky header and the sticky
// «Noch nicht» sheet. The walk measures the real page; this pins the geometry.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.join(__dirname, '..', 'node_modules/sucrase/register/ts'));
const { scrollToKeepAbove } = require('./keep-above-sheet.ts');

// The 20 Oct build miss at 375×812: card 375→610, sheet from 550, header to 70.
test('a card running under the sheet is scrolled up above it', () => {
  const delta = scrollToKeepAbove({ cardTop: 375, cardBottom: 610, sheetTop: 550, headerBottom: 70 });
  assert.equal(delta, 610 - (550 - 12));
  // After the scroll the card is between the header and the sheet.
  assert.ok(375 - delta >= 70 + 12 && 610 - delta <= 550 - 12);
});

test('a card that already fits is left where it is', () => {
  assert.equal(scrollToKeepAbove({ cardTop: 200, cardBottom: 420, sheetTop: 550, headerBottom: 70 }), 0);
});

test('a card taller than the space shows its first lines, under the header', () => {
  const delta = scrollToKeepAbove({ cardTop: 400, cardBottom: 1000, sheetTop: 550, headerBottom: 70 });
  assert.equal(delta, 400 - 82);
});

test('a card scrolled up under the header comes back down', () => {
  assert.equal(scrollToKeepAbove({ cardTop: 20, cardBottom: 200, sheetTop: 550, headerBottom: 70 }), 20 - 82);
});
