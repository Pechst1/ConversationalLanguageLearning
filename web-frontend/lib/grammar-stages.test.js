// node --test lib/grammar-stages.test.js
//
// WP-130 A — one vocabulary for a grammar unit's state on every surface.
//   1. the level line: «Grammaire : 6 en route · 0 tenue», localized, «introduced» only when there is one;
//   2. German has one word per state, and no state word is used for another;
//   3. a practice score qualifies the stage, never replaces it («en route · solide à l’entraînement»);
//   4. without a server stage the page never guesses «held»;
//   5. the missing evidence is said plainly, dated only when the date is ahead;
//   6. the Dossier shows the band's rules in the same words, from the level's own counts.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const S = require('./grammar-stages.ts');
const { coverageRows } = require('../components/atelier-v2/dossier/dossier-state.ts');

test('the level line names the counts in the learner’s language', () => {
  const counts = { introduced: 0, practising: 6, held: 0 };
  assert.equal(S.grammarLine(counts, 'fr'), 'Grammaire : 6 en route · 0 tenue');
  assert.equal(S.grammarLine(counts, 'en'), 'Grammar: 6 practising · 0 held');
  assert.equal(S.grammarLine(counts, 'de'), 'Grammatik: 6 in Übung · 0 gefestigt');
  assert.equal(S.grammarLine({ introduced: 1, practising: 2, held: 3 }, 'fr'), 'Grammaire : 1 découverte · 2 en route · 3 tenues');
  assert.equal(S.stageCountsText(null, 'en'), '0 practising · 0 held');
});

test('one word per state, the same keys in every language', () => {
  for (const language of ['en', 'de', 'fr']) {
    const copy = S.grammarStageCopy(language);
    const words = S.VISIBLE_STAGES.map((stage) => copy.stage[stage][0]);
    assert.equal(new Set(words).size, 3, `${language}: three distinct words`);
    assert.deepEqual(Object.keys(copy).sort(), Object.keys(S.grammarStageCopy('en')).sort());
  }
  const de = S.grammarStageCopy('de');
  // «gefestigt» is «held» and nothing else; the score's «solid» is «sicher».
  assert.equal(de.stage.held[0], 'gefestigt');
  for (const key of Object.keys(de)) {
    if (key === 'stage') continue;
    assert.doesNotMatch(String(de[key]), /gefestigt/, key);
  }
  for (const language of ['en', 'de', 'fr']) {
    const copy = S.grammarStageCopy(language);
    const notHeld = [copy.stage.introduced, copy.stage.practising, copy.practice_solid, copy.practice_fragile, copy.not_met].flat().join(' | ');
    assert.doesNotMatch(notHeld, /held|tenue|acquis|maîtris|mastered|gefestigt|gemeistert|beherrscht/i, language);
  }
});

test('a practice score qualifies the stage, never replaces it', () => {
  const solid = { stage: 'practising', state: 'gefestigt', mastery: 8.5 };
  assert.equal(S.stageLabel(solid, 'fr'), 'en route · solide à l’entraînement');
  assert.equal(S.stageLabel(solid, 'en'), 'practising · solid in practice');
  assert.equal(S.stageLabel(solid, 'de'), 'in Übung · in der Übung sicher');
  assert.equal(S.stageLabel({ stage: 'practising', state: 'gemeistert' }, 'fr'), 'en route · solide à l’entraînement');
  assert.equal(S.stageLabel({ stage: 'held', state: 'gemeistert' }, 'fr'), 'tenue');
  assert.equal(S.stageLabel({ stage: 'new', state: 'neu' }, 'en'), 'not met yet');
});

test('without a server stage the page never guesses «held»', () => {
  assert.equal(S.stageOf({ mastery: 9.5, state: 'gemeistert' }), 'practising');
  assert.equal(S.stageOf({ mastery: 0 }), 'new');
  assert.equal(S.stageOf({ stage: 'held' }), 'held');
  assert.deepEqual(
    S.countStages([{ stage: 'held' }, { stage: 'practising' }, { stage: 'introduced' }, { stage: 'new' }, { mastery: 9 }]),
    { introduced: 1, practising: 2, held: 1 },
  );
});

test('the missing evidence is said plainly, dated only when the date is ahead', () => {
  const today = new Date('2026-10-04T10:00:00Z');
  const missing = [
    { code: 'free_use_second', not_before: '2026-10-09' },
    { code: 'spaced', not_before: '2026-10-01' },
  ];
  assert.equal(S.missingLine(missing, 'fr', today), 'Encore : un 2ᵉ emploi libre à partir du 9 oct. · un rappel réussi');
  assert.equal(S.missingLine(missing, 'en', today), 'Still needed: a second unaided use, from 9 Oct · one successful review');
  assert.match(S.missingLine(missing, 'de', today), /^Noch nötig: eine zweite freie Verwendung ab dem 9\. Okt\.? · eine gelungene Wiederholung$/);
  assert.equal(S.missingLine([{ code: 'free_use_first', not_before: null }], 'fr', today), 'Encore : un emploi libre dans une réponse');
  assert.equal(S.missingLine([], 'fr', today), null);
  assert.equal(S.missingLine([{ code: 'unknown' }], 'fr', today), null);
});

test('the Dossier shows the band’s rules in the same words, from the level’s counts', () => {
  const level = {
    available: true,
    estimate: 'A1.1',
    coverage: {
      band: 'A1.1',
      units: { held: 0, practising: 6, introduced: 0, total: 20, required: 17, met: false },
      words: { known: 0, total: 0, required: 0, met: true },
    },
    checkpoint: null,
  };
  const rows = coverageRows(level, 'fr');
  const stages = rows.find((row) => row.key === 'stages');
  assert.ok(stages, 'a stages row');
  assert.equal(stages.value, '6 en route · 0 tenue');
  assert.equal(rows.find((row) => row.key === 'units').label, 'Notions tenues');
  assert.equal(coverageRows(level, 'de').find((row) => row.key === 'units').label, 'Gefestigte Regeln');
  // An older level payload has no stage counts: no row, rather than a guess.
  const old = { ...level, coverage: { ...level.coverage, units: { held: 0, total: 20, required: 17, met: false } } };
  assert.equal(coverageRows(old, 'fr').find((row) => row.key === 'stages'), undefined);
});
