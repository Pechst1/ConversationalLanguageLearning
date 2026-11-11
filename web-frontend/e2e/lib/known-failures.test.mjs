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

test('#717 is fixed: a tentpole off its day fails the walk again', () => {
  assert.equal(knownFailure('season-tentpole-on-its-day', "t2.a: «Tu devais partir aujourd'hui.» seen on day(s) none (expected one of 7, 8, 9)", {}), null);
});

test('#718: a reload that serves the batch plus refills is known; one that drops or reorders is not', () => {
  const id = 'drill-reload-keeps-the-batch';
  const d = (served) => `answered 1, 2; expected {"fragile_words":[5,6],"new_words":[9]}, the reload served ${JSON.stringify(served)}`;
  assert.equal(knownFailure(id, d({ fragile_words: [5, 6, 7], new_words: [9, 10] }), {})?.issue, 718);
  assert.equal(knownFailure(id, d({ fragile_words: [6, 5], new_words: [9] }), {}), null);
  assert.equal(knownFailure(id, d({ fragile_words: [5], new_words: [9] }), {}), null);
  assert.equal(knownFailure(id, d({ fragile_words: [5, 6], new_words: [9] }), {}), null);
});

test('#196: an English sentence quoted by a French drill is known; English chrome is not', () => {
  const id = 'no-english-on-french-b1';
  assert.equal(knownFailure(id, 'English chrome on a French screen: at, the, you — «ègleComplète la phrase : « Last night, when Margaux arrived at the flea market, you had already closed Le Mistral. »Vérifier»', {})?.issue, 196);
  assert.equal(knownFailure(id, 'English chrome on a French screen: to, the, answer — «Tap to turnShow the answer»', {}), null);
  assert.equal(knownFailure(id, 'English chrome: — «Complète la phrase : « Hier, Margaux est arrivée au marché. »»', {}), null);
});
