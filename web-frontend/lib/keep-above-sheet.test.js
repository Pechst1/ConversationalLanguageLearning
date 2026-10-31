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

// Codex on #260: a right classification with its repair open shows no sheet; the
// sheet mounts when the repair is done or shown, and nothing else changes then.
test('the scroll runs again when the repair under a verdict settles', () => {
  const fs = require('node:fs');
  const page = fs.readFileSync(path.join(__dirname, '..', 'pages/atelier.tsx'), 'utf8');
  const effect = page.match(/keepCardAboveSheet\(feedbackRef\.current\)[\s\S]*?\}, \[([^\]]*)\]\);/);
  assert.ok(effect, 'the effect that keeps the card above the sheet');
  assert.match(effect[1], /repairOutcome/);
  assert.match(page, /const repairOutcome = followUps\[feedbackKey\]\?\.outcome \?\? null;/);
});

// #319: the walk of 23 Oct found a French correction card partly under the sheet.
// The scroll was worked out once, from the card's size at that moment; a card that
// grows afterwards (a late font, the notes under the right sentence) stayed where it
// was, under the sticky sheet. The card is kept above the sheet while it settles.
function fakePage({ cardTop = 375, cardHeight = 235, sheetTop = 550, headerBottom = 70 } = {}) {
  const page = { scrollY: 0, cardHeight, observers: [], sheetTop, headerBottom };
  const rect = (top, height) => ({ top, bottom: top + height, height });
  const sheet = { classList: { contains: (name) => name === 'ep-foot' }, getBoundingClientRect: () => rect(sheetTop, 140) };
  const card = { classList: { contains: () => false }, getBoundingClientRect: () => rect(cardTop - page.scrollY, page.cardHeight) };
  const header = { getBoundingClientRect: () => rect(0, headerBottom) };
  page.feedback = {
    parentElement: null,
    children: [card, sheet],
    querySelector: (selector) => (selector === '.ep-foot' ? sheet : null),
  };
  global.window = { innerHeight: 812, scrollBy: ({ top }) => { page.scrollY += top; } };
  global.document = {
    body: {},
    documentElement: {},
    querySelector: (selector) => (selector === '.ep-top' ? header : selector === '.ep-foot' ? sheet : null),
  };
  global.ResizeObserver = class {
    constructor(callback) { this.callback = callback; page.observers.push(this); }
    observe() {}
    disconnect() { this.callback = null; }
  };
  page.cardBox = () => card.getBoundingClientRect();
  page.resize = () => page.observers.forEach((o) => o.callback && o.callback([]));
  return page;
}

function withFakePage(options, run) {
  const page = fakePage(options);
  try {
    run(page);
  } finally {
    delete global.window;
    delete global.document;
    delete global.ResizeObserver;
  }
}

test('a card that grows after the scroll is brought back above the sheet', () => {
  const { keepCardAboveSheet } = require('./keep-above-sheet.ts');
  withFakePage({}, (page) => {
    keepCardAboveSheet(page.feedback, { smooth: false });
    assert.ok(page.cardBox().bottom <= page.sheetTop, 'the first scroll puts the card above the sheet');
    page.cardHeight = 335; // the notes arrive and the card runs under the sheet again
    page.resize();
    const box = page.cardBox();
    assert.ok(box.bottom <= page.sheetTop, `the card still runs under the sheet: ${box.top}-${box.bottom}, sheet from ${page.sheetTop}`);
    assert.ok(box.top >= page.headerBottom, 'and it is not scrolled up under the header');
  });
});

test('a card that is let go is not scrolled again', () => {
  const { keepCardAboveSheet } = require('./keep-above-sheet.ts');
  withFakePage({}, (page) => {
    const stop = keepCardAboveSheet(page.feedback, { smooth: false });
    assert.equal(typeof stop, 'function', 'the caller can let the card go when the verdict goes away');
    stop();
    const before = page.scrollY;
    page.cardHeight = 335;
    page.resize();
    assert.equal(page.scrollY, before);
  });
});
