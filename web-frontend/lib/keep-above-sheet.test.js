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
  const effect = page.match(/keepCardAboveSheet\(feedbackRef\.current[\s\S]*?\}, \[([^\]]*)\]\);/);
  assert.ok(effect, 'the effect that keeps the card above the sheet');
  assert.match(effect[1], /repairOutcome/);
  assert.match(page, /const repairOutcome = followUps\[feedbackKey\]\?\.outcome \?\? null;/);
});

// #319: the walk of 23 Oct found a French correction card partly under the sheet.
// The scroll was worked out once, from the card's size at that moment; a card that
// grows afterwards (a late font, the notes under the right sentence) stayed where it
// was, under the sticky sheet. The card is kept above the sheet while it settles.
function fakePage({ cardTop = 375, cardHeight = 235, sheetTop = 550, headerBottom = 70, repairTop = null, repairHeight = 120 } = {}) {
  const page = { scrollY: 0, cardHeight, observers: [], sheetTop, headerBottom, repairHeight, attributes: {}, listeners: [], scrolls: [] };
  const rect = (top, height) => ({ top, bottom: top + height, height });
  const sheet = { classList: { contains: (name) => name === 'ep-foot' }, getBoundingClientRect: () => rect(sheetTop, 140) };
  const card = { classList: { contains: () => false }, getBoundingClientRect: () => rect(cardTop - page.scrollY, page.cardHeight) };
  const header = { getBoundingClientRect: () => rect(0, headerBottom) };
  // The last repair sits under the card; it moves with the page, and with the card's growth.
  const repair = { classList: { contains: () => false }, getBoundingClientRect: () => rect(repairTop - page.scrollY + (page.cardHeight - cardHeight), page.repairHeight) };
  page.feedback = {
    parentElement: null,
    children: [card, sheet],
    querySelector: (selector) => (selector === '.ep-foot' ? sheet : null),
    querySelectorAll: () => (repairTop == null ? [] : [repair]),
    setAttribute: (name, value) => { page.attributes[name] = value; },
  };
  global.window = {
    innerHeight: 812,
    scrollBy: ({ top, behavior }) => { page.scrollY += top; page.scrolls.push({ top, behavior }); },
    addEventListener: (type, fn) => page.listeners.push([type, fn]),
    removeEventListener: () => {},
    setTimeout: (fn) => { page.timers.push(fn); return page.timers.length; },
    clearTimeout: () => {},
  };
  page.timers = [];
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
  page.repairBox = () => repair.getBoundingClientRect();
  page.runTimers = () => { const due = page.timers.splice(0); due.forEach((fn) => fn()); };
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

// #319 (reopened 2 Nov): two owners scrolled the same page for a miss, on different clocks
// (a smooth scroll for the first card, instant jumps at 150 and 600 ms for the last repair),
// so where the page ended up depended on which ran last. One function now works out one
// position that satisfies both rules.
test('#319 · the 25 Oct boxes: one position puts the card above the sheet and the last repair clear of it', () => {
  // en A1.1 day 2: card 378–559, header ends 66, sheet starts 551 — and a repair below the card.
  const delta = scrollToKeepAbove({ cardTop: 378, cardBottom: 559, sheetTop: 551, headerBottom: 66, anchorBottom: 640 });
  assert.ok(378 - delta >= 66 + 12, 'the first card stays under the header');
  assert.ok(559 - delta <= 551 - 12, 'the card is above the sheet');
  assert.ok(640 - delta <= 551 - 12, 'the last repair clears the sheet');
});

test('#319 · when the card and the last repair cannot both fit, the first card wins', () => {
  const delta = scrollToKeepAbove({ cardTop: 200, cardBottom: 420, sheetTop: 551, headerBottom: 66, anchorBottom: 900 });
  assert.equal(200 - delta, 66 + 12, 'the card is aligned under the header, not pushed past it');
});

test('#319 · a repair that already clears the sheet changes nothing', () => {
  assert.equal(scrollToKeepAbove({ cardTop: 200, cardBottom: 420, sheetTop: 551, headerBottom: 66, anchorBottom: 500 }), 0);
});

test('#319 · a late repair that grows the card ends in the one position, not a second scroll fighting the first', () => {
  const { keepCardAboveSheet } = require('./keep-above-sheet.ts');
  withFakePage({ cardTop: 378, cardHeight: 181, sheetTop: 551, headerBottom: 66, repairTop: 560 }, (page) => {
    keepCardAboveSheet(page.feedback, { smooth: false });
    page.cardHeight = 261; // the notes under the right sentence arrive and the repair moves down with them
    page.resize();
    page.runTimers();
    const card = page.cardBox();
    const repair = page.repairBox();
    assert.ok(card.top >= 66 + 12, `the first card is under the header: ${card.top}`);
    assert.ok(card.bottom <= 551 - 12 || card.top === 66 + 12, `the card is above the sheet, or aligned under the header when too tall: ${card.top}-${card.bottom}`);
    assert.ok(repair.bottom <= 551 - 12 || card.top === 66 + 12, `the last repair clears the sheet: ends ${repair.bottom}`);
    assert.ok(page.scrolls.every((s) => s.behavior === 'auto' || s === page.scrolls[0]), 'only the first move may be smooth');
  });
});

test('#319 · the feedback says «settled» only once the scroll is quiet and the looks are done', () => {
  const { keepCardAboveSheet } = require('./keep-above-sheet.ts');
  withFakePage({}, (page) => {
    keepCardAboveSheet(page.feedback, { smooth: false });
    assert.equal(page.attributes['data-scroll'], 'settling', 'the walk must not measure yet');
    page.runTimers(); // the scheduled looks and the quiet check
    page.runTimers();
    page.runTimers();
    page.runTimers();
    assert.equal(page.attributes['data-scroll'], 'settled');
  });
});

test('#319 · only one module scrolls the page for a miss', () => {
  const fs = require('node:fs');
  const root = path.join(__dirname, '..');
  const sheet = fs.readFileSync(path.join(root, 'lib/sheet-clearance.ts'), 'utf8');
  const page = fs.readFileSync(path.join(root, 'pages/atelier.tsx'), 'utf8');
  const keep = fs.readFileSync(path.join(root, 'lib/keep-above-sheet.ts'), 'utf8');
  assert.doesNotMatch(sheet, /scrollBy\(|window\.scroll|clearTheSheet/, 'sheet-clearance is geometry only');
  assert.doesNotMatch(page, /clearTheSheet|\bscrollBy\(/, 'the page does not scroll on its own for a miss');
  assert.match(keep, /scrollBy\(/);
  assert.equal((page.match(/keepCardAboveSheet\(/g) || []).length, 1, 'one call site for the miss scroll');
});
