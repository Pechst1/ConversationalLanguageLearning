import assert from 'node:assert/strict';
import test from 'node:test';

import { Findings } from './assertions.mjs';
import { KNOWN_FAILURES, knownFailure } from './known-failures.mjs';

test('every known failure names its check and an issue, and is narrow', () => {
  for (const entry of KNOWN_FAILURES) {
    assert.ok(entry.id && Number.isInteger(entry.issue) && entry.issue > 0 && entry.why, JSON.stringify(entry));
    // Narrow: it never covers a failure with no detail and no place.
    assert.equal(entry.when('', {}), false, `#${entry.issue} matches any failure of ${entry.id}`);
  }
});

test('#715: a pairs drill whose appeal was unread is known; a choice drill is not', () => {
  assert.equal(knownFailure('appeal-upheld-turns-the-verdict', 'appeal unread: wrong → wrong', { drill: 'match' })?.issue, 715);
  assert.equal(knownFailure('appeal-upheld-turns-the-verdict', 'appeal unread: wrong → wrong', { drill: 'choice' }), null);
  assert.equal(knownFailure('appeal-upheld-turns-the-verdict', 'appeal refused: wrong → wrong', { drill: 'match' }), null);
});

test('a known failure is reported but does not fail the walk; others still do', () => {
  const f = new Findings({ known: (id) => (id === 'k' ? { issue: 1 } : null) });
  f.check('k', false, 'covered', {});
  f.check('other', false, 'not covered', {});
  assert.deepEqual(f.failures.map((r) => r.id), ['other']);
  assert.deepEqual(f.known.map((r) => [r.id, r.known]), [['k', 1]]);
  assert.deepEqual(f.summary().find((r) => r.id === 'k'), { id: 'k', pass: 0, fail: 0, known: 1 });
});
