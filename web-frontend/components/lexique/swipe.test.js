// node --test components/lexique/swipe.test.js
//
// Owner, 4 Nov: «the vocab cards should be more intuitive and less taps to say whether one
// knew it or not, maybe by swiping». A turned card swiped right is «Je sais», left
// «Encore»; a tap is a tap, a vertical move scrolls, a short drag springs back.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

require(path.resolve(__dirname, '../../node_modules/sucrase/register/ts'));
const swipe = require('./swipe.ts');

test('right files «Je sais» (grade 2), left «Encore» (grade 0)', () => {
  assert.deepEqual(swipe.SWIPE_RATING, { know: 2, again: 0 });
  assert.equal(swipe.swipeVerdict({ dx: 140, velocity: 0, width: 360 }), 'know');
  assert.equal(swipe.swipeVerdict({ dx: -140, velocity: 0, width: 360 }), 'again');
});

test('a short drag springs back; a quick flick counts', () => {
  assert.equal(swipe.swipeVerdict({ dx: 50, velocity: 0.1, width: 360 }), null);
  assert.equal(swipe.swipeVerdict({ dx: 50, velocity: 0.8, width: 360 }), 'know');
  assert.equal(swipe.swipeVerdict({ dx: -45, velocity: -0.9, width: 360 }), 'again');
  assert.equal(swipe.swipeVerdict({ dx: 30, velocity: 2, width: 360 }), null, 'too short to be a flick');
  assert.equal(swipe.swipeVerdict({ dx: 60, velocity: -0.9, width: 360 }), null, 'a flick back is no verdict');
});

test('the threshold follows the card, within 70–120px', () => {
  assert.equal(swipe.swipeThreshold(200), 70);
  assert.equal(swipe.swipeThreshold(360), 90);
  assert.equal(swipe.swipeThreshold(700), 120);
  assert.equal(swipe.swipeThreshold(0), 70);
});

test('a drag starts only sideways; a vertical move is the page scrolling', () => {
  assert.equal(swipe.dragStarts(4, 2), null, 'a tap');
  assert.equal(swipe.dragStarts(14, 3), 'drag');
  assert.equal(swipe.dragStarts(-14, 3), 'drag');
  assert.equal(swipe.dragStarts(5, 16), 'scroll');
  assert.equal(swipe.dragStarts(6, 10), null, 'not yet clear');
});

test('the stamps fade in with the drag, capped at full', () => {
  assert.equal(swipe.swipeProgress(0, 360), 0);
  assert.equal(swipe.swipeProgress(45, 360), 0.5);
  assert.equal(swipe.swipeProgress(-400, 360), -1);
  assert.equal(swipe.swipeProgress(400, 360), 1);
});

test('the review page is a flip card with no fill-in, filed by the swipe', () => {
  const page = fs.readFileSync(path.join(__dirname, '..', '..', 'pages', 'vocabulary', 'review.tsx'), 'utf8');
  // No typed or spoken answer on the card any more.
  assert.doesNotMatch(page, /lx-card__input|typedAnswer|startRecording|getUserMedia/);
  assert.match(page, /onPointerDown=\{onCardPointerDown\}/);
  assert.match(page, /swipeVerdict\(/);
  assert.match(page, /handleRatingClick\(SWIPE_RATING\[side\]\)/);
  // A flip card reports a self-rated flashcard: no gold for it (owner, 4 Nov).
  assert.match(page, /format: 'flashcard' as const/);
  // The example and its translation are on the back, and only there.
  assert.doesNotMatch(page, /faces\.frontExample|faces\.frontTranslation/);
  assert.match(page, /faces\.backTranslation/);
  // The lag: nothing slow runs on the tap that files a card.
  const body = page.slice(page.indexOf('const fileGrade = '), page.indexOf('const returnToAtelier'));
  assert.match(body, /afterPaint\(\(\) => writeReviewContextCache/);
  assert.doesNotMatch(body, /toast\.success/);
  // The drag never goes through React state.
  const move = page.slice(page.indexOf('const onCardPointerMove'), page.indexOf('const onCardPointerEnd'));
  assert.doesNotMatch(move, /\bset(?!DragVisual|PointerCapture|Attribute)[A-Z]\w*\(/);
});
