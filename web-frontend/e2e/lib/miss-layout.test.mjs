// node --test e2e/lib/miss-layout.test.mjs
//
// #282 and #285 on the walk's side: the layout checks of a miss screen, and the one
// definition of a field the walk may type into.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { TYPEABLE_FIELD } from './driver.mjs';
import { missLayoutChecks, namedWrongWords } from './miss-layout.mjs';

const MISS = {
  height: 812,
  exercise: [{ left: 20, right: 355, top: 205, bottom: 520 }],
  bubbles: [],
  sheet: [{ left: 0, right: 375, top: 551, bottom: 794 }],
  compare: [{ left: 36, right: 147, top: 440, bottom: 496 }],
  gaps: ['à le'],
  hints: ['Replace «à le» with «au» here.'],
};
const byName = (layout) => Object.fromEntries(missLayoutChecks(layout).map((check) => [check.name, check]));

test('a clean miss screen passes every check it has the parts for', () => {
  const checks = byName(MISS);
  assert.deepEqual(Object.keys(checks).sort(), ['miss-action-above-the-sheet', 'repair-field-matches-the-instruction']);
  assert.ok(Object.values(checks).every((check) => check.ok));
});

test('a bubble on the prompt is named', () => {
  const checks = byName({ ...MISS, bubbles: [{ left: 59, right: 269, top: 232, bottom: 305 }] });
  assert.equal(checks['miss-prompt-not-covered'].ok, false);
  assert.equal(byName({ ...MISS, bubbles: [{ left: 59, right: 269, top: 20, bottom: 93 }] })['miss-prompt-not-covered'].ok, true);
});

test('«Compare» behind or below the verdict sheet is named', () => {
  const behind = byName({ ...MISS, compare: [{ left: 36, right: 147, top: 1000, bottom: 1056 }] });
  assert.equal(behind['miss-action-above-the-sheet'].ok, false);
  const half = byName({ ...MISS, compare: [{ left: 36, right: 147, top: 520, bottom: 576 }] });
  assert.equal(half['miss-action-above-the-sheet'].ok, false, 'partly behind it');
});

test('the field must hold the words the instruction names', () => {
  assert.equal(namedWrongWords('Replace «à le» with «au» here.'), 'à le');
  assert.equal(namedWrongWords('Ersetze « à le » durch « au ».'), 'à le');
  assert.equal(namedWrongWords('Add the accent.'), null);
  const wide = byName({ ...MISS, gaps: ['à le marché aux puces'] });
  assert.equal(wide['repair-field-matches-the-instruction'].ok, false);
  assert.match(wide['repair-field-matches-the-instruction'].detail, /names «à le»/);
});

// #381 (live walks 30 and 31 Oct): «Line fixed. It comes back later.» above a red «Not yet».
test('#381 · a line whose every repair is accepted has no «Not yet» band under it', () => {
  const fixed = byName({ ...MISS, repairs: ['ok'], failBands: 0 });
  assert.equal(fixed['repaired-line-has-no-failure-banner'].ok, true);
  const both = byName({ ...MISS, repairs: ['ok'], failBands: 1 });
  assert.equal(both['repaired-line-has-no-failure-banner'].ok, false);
  assert.match(both['repaired-line-has-no-failure-banner'].detail, /«Not yet»/);
  // A repair still open, or none on screen: the «Not yet» is the verdict, nothing to check.
  assert.equal(byName({ ...MISS, repairs: ['ok', 'no'], failBands: 1 })['repaired-line-has-no-failure-banner'], undefined);
  assert.equal(byName({ ...MISS, repairs: [], failBands: 1 })['repaired-line-has-no-failure-banner'], undefined);
});

test('off a miss screen there is nothing to check', () => {
  assert.deepEqual(missLayoutChecks(null), []);
  assert.deepEqual(missLayoutChecks({ height: 812, exercise: [], bubbles: [], sheet: [], compare: [], gaps: [], hints: [] }), []);
});

// #285: «typing-stays-in-the-field» failed on a screen that holds a graded, read-only
// «Tape la forme» gap above the repair field: the walk clicked the first field that was
// not disabled, which was the graded gap.
test('#285 · the field the walk types into is never a read-only one', () => {
  assert.match(TYPEABLE_FIELD, /\[readonly\]/);
  assert.match(TYPEABLE_FIELD, /\[disabled\]/);
  for (const part of TYPEABLE_FIELD.split(',')) {
    assert.match(part, /:not\(\[readonly\]\)/, `${part.trim()} leaves read-only fields in`);
    assert.match(part, /:not\(\[disabled\]\)/);
  }
});
