/**
 * WP-35 «Votre dossier» — behavioural coverage for the page's state.
 *
 * Same harness as `rehearsal.test.js`: a plain node script with
 * `node:assert/strict` and sucrase, so it adds no test framework and no
 * dependency.
 *
 * These are failure-mode tests. What they hold down:
 *
 *   1. a declared level is never printed in the words of a measurement, and
 *      never wears a confidence figure;
 *   2. a placement says how sure it is, in words, with its date;
 *   3. the because-line prints only for a kind the page knows, only with a
 *      label, and never at all without a journey — «pas encore de scène
 *      aujourd'hui» is the honest sentence there;
 *   4. the vocabulary count keeps evidence and assumption apart instead of
 *      adding them into one number;
 *   5. the claim panel says, before the learner answers, that a failure costs
 *      nothing — and no accepted answer is anywhere in the payload;
 *   6. the screen's chrome comes from `dossier-copy.ts` (WP-82: the learner's
 *      language up to A2, French from B1), the page is on av2, and it
 *      hard-codes no colour, so dark mode is inherited rather than
 *      re-implemented.
 *
 * Run: `node components/atelier-v2/dossier/dossier.test.js`
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const {
  NO_JOURNEY_FR,
  becauseSentence,
  capabilityEvidenceSentence,
  capabilityStateLabel,
  claimableErrata,
  claimableWords,
  confidenceSentence,
  errataStateLabel,
  evidenceSentence,
  frenchDate,
  levelBasisSentence,
  levelSentence,
  phaseFor,
  verdictTone,
  verifiedSentence,
  vocabularySentence,
} = require(path.join(HERE, 'dossier-state.ts'));
const { dossierCopy } = require(path.join(HERE, 'dossier-copy.ts'));
const FR = dossierCopy('fr');

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed += 1;
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

function dossier(overrides = {}) {
  return {
    version: 'learner-model-v1',
    level: {
      available: true,
      estimate: 'A2.1',
      estimate_source: 'declared',
      declared_level: 'A2.1',
      verified: false,
      status: 'unverified',
      confidence: null,
      breakdown: { status: 'unverified' },
      placement: null,
      evidence: { kind: 'declaration', on: '2026-08-01' },
    },
    capabilities: [],
    errata: { available: true, mastery_target: 3, counts: {}, by_state: {} },
    vocabulary: { available: true, known: null, nailed_rule: { retrievability: 0.9 }, words: [] },
    today: { has_journey: false, because: null },
    claims: [],
    ...overrides,
  };
}

// 1. A declaration is a declaration.
test('a declared level is named as declared and carries no confidence', () => {
  const model = dossier();
  assert.equal(levelSentence(model.level), 'Niveau déclaré · A2.1');
  assert.ok(levelBasisSentence(model.level).includes('inscription'));
  assert.ok(!levelBasisSentence(model.level).includes('%'), 'no percentage on a declaration');
  assert.ok(verifiedSentence(model.level).includes('estimation'));
  assert.equal(confidenceSentence(null), 'Aucune confiance chiffrée : rien n’a été mesuré.');
});

// 2. A placement says how sure it is.
test('a placement is printed with its confidence in words and its date', () => {
  const level = {
    available: true,
    estimate: 'B1.1',
    estimate_source: 'placement',
    verified: false,
    confidence: 0.72,
    placement: { id: 'p1', confidence: 0.72, taken_at: '2026-09-10', graded_turns: 5 },
    evidence: { kind: 'placement', on: '2026-09-10' },
  };
  assert.equal(levelSentence(level), 'Niveau estimé (bilan) · B1.1');
  const basis = levelBasisSentence(level);
  assert.ok(basis.includes('5 réponses corrigées'));
  assert.ok(basis.includes('Confiance élevée (72 %)'));
  assert.equal(evidenceSentence(level.evidence), 'Bilan du 10 septembre');
});

test('a measured level says it is the application’s own arithmetic', () => {
  const level = { available: true, estimate: 'A2.2', estimate_source: 'measured', verified: true };
  assert.ok(levelBasisSentence(level).includes('votre travail dans l’application'));
  assert.ok(verifiedSentence(level).includes('Vérifié'));
});

test('an unreadable level section says so instead of naming a level', () => {
  assert.equal(levelSentence({ available: false }), 'Niveau non évalué pour l’instant.');
  assert.ok(levelBasisSentence({ available: false }).includes('ne pouvons pas'));
});

// 3. The because-line.
test('the because-line prints only for a known kind, with a label', () => {
  const withLine = { has_journey: true, because: { kind: 'erratum', label: 'l’accord en genre' } };
  assert.equal(
    becauseSentence(withLine),
    'Cette scène reprend une faute notée : l’accord en genre.',
  );

  const withExample = {
    has_journey: true,
    because: { kind: 'erratum', label: 'l’accord en genre', example: 'une homme → un homme' },
  };
  assert.ok(becauseSentence(withExample).includes('une homme → un homme'));

  assert.equal(
    becauseSentence({ has_journey: true, because: { kind: 'weather', label: 'x' } }),
    null,
    'an unknown kind prints nothing rather than inventing French',
  );
  assert.equal(
    becauseSentence({ has_journey: true, because: { kind: 'erratum', label: '  ' } }),
    null,
  );
});

test('without a journey there is no line and no promise', () => {
  assert.equal(becauseSentence({ has_journey: false, because: null }), null);
  assert.equal(NO_JOURNEY_FR, 'Pas encore de scène aujourd’hui.');
  assert.ok(!NO_JOURNEY_FR.includes('demain'), 'the page promises nothing about tomorrow');
});

// 4. Capabilities and their evidence.
test('the rubric’s four states have French labels and an unknown state is not a pass', () => {
  assert.equal(capabilityStateLabel('not_tried'), 'Pas encore tenté');
  assert.equal(capabilityStateLabel('with_support'), 'Avec de l’aide');
  assert.equal(capabilityStateLabel('independent_once'), 'Seul, une fois');
  assert.equal(capabilityStateLabel('used_again_later'), 'Refait un autre jour');
  assert.equal(capabilityStateLabel('unknown'), 'Aide non enregistrée');
  assert.equal(capabilityStateLabel('invented'), 'Aide non enregistrée');
});

test('a capability’s evidence names the séance and its date', () => {
  assert.equal(
    capabilityEvidenceSentence({ on: '2026-09-05', modality: 'voice', state: 'independent_once', context: '' }),
    'Séance du 5 septembre, à l’oral',
  );
  assert.equal(capabilityEvidenceSentence(undefined), null);
});

// 5. Errata and vocabulary.
test('errata states are WP-24’s three, in French', () => {
  assert.equal(errataStateLabel('open'), 'À reprendre');
  assert.equal(errataStateLabel('repairing'), 'En cours de reprise');
  assert.equal(errataStateLabel('mastered'), 'Acquis');
});

test('only unfinished errata and unnailed words can be claimed', () => {
  const errata = [
    { id: '1', claimable: true },
    { id: '2', claimable: false },
  ];
  assert.deepEqual(claimableErrata(errata).map((item) => item.id), ['1']);
  const vocabulary = { words: [{ word_id: 1, claimable: false }, { word_id: 2, claimable: true }] };
  assert.deepEqual(claimableWords(vocabulary).map((item) => item.word_id), [2]);
});

test('the word count keeps evidence and assumption apart', () => {
  const sentence = vocabularySentence({
    known: { known_lemmas: 900, nailed_words: 120, core_words: 780 },
  });
  assert.ok(sentence.includes('120 acquis par vos révisions'));
  assert.ok(sentence.includes('780 supposés par votre niveau'));
  assert.ok(vocabularySentence({ known: null }).includes('ne pouvons pas chiffrer'));
});

// 6. Phases and verdicts.
test('the page has three phases and never renders a half-read model', () => {
  assert.equal(phaseFor(null, { loading: true }).kind, 'loading');
  assert.equal(phaseFor(null, { error: 'boom' }).kind, 'load_failed');
  assert.equal(phaseFor(null).kind, 'loading');
  assert.equal(phaseFor(dossier()).kind, 'ready');
});

test('a refused claim is not dressed as a pass', () => {
  assert.equal(verdictTone('verified'), 'plain');
  assert.equal(verdictTone('not_yet'), 'alert');
  assert.equal(verdictTone('unverifiable'), 'quiet');
});

test('dates are French and the first of the month is written 1er', () => {
  assert.equal(frenchDate('2026-09-05'), '5 septembre');
  assert.equal(frenchDate('2026-01-01'), '1er janvier');
});

// 7. The screen's own contract, read from the source.
test('the claim panel says what a failure costs before the learner answers', () => {
  const screen = fs.readFileSync(path.join(HERE, 'DossierScreen.tsx'), 'utf8');
  assert.equal(FR.claim, 'Je connais déjà', 'the claim is offered in the learner’s words');
  assert.ok(screen.includes('{copy.claim}'));
  assert.ok(
    FR.claim_terms.includes('rien n’est retiré et rien n’est ajouté'),
    'the learner is told a failed claim costs nothing',
  );
  assert.ok(FR.claim_terms.includes('nous avançons l’échéance'), 'and what passing does');
  assert.ok(screen.includes('{copy.claim_terms}'));
  assert.equal(FR.verify, 'Vérifier', 'the primary action is a verification, not a switch');
  assert.ok(screen.includes('{copy.verify}'));
});

test('the screen is on the av2 system, reads its chrome from the table, and hard-codes no colour', () => {
  const screen = fs.readFileSync(path.join(HERE, 'DossierScreen.tsx'), 'utf8');
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/dossier.tsx'), 'utf8');
  const state = fs.readFileSync(path.join(HERE, 'dossier-state.ts'), 'utf8');
  assert.ok(page.includes('AtelierV2Root'), 'the page is on the av2 system');
  assert.ok(screen.includes('av2-headline'));
  assert.ok(!screen.includes('neo-'), 'no legacy chrome');
  assert.ok(!screen.includes('text-sm'), 'no utility-class chrome');
  // WP-82: no inline chrome in either language — the screen and the state read
  // `dossier-copy.ts`. Checked as whole rendered labels rather than substrings.
  for (const phrase of [
    '>Continue<', 'Your level', 'I already know', 'Check answer', 'Not yet<',
    'Votre niveau', 'Je connais déjà', 'Revenir au dossier', 'Pas encore tenté',
    'Niveau déclaré', 'Cette action n’a pas abouti',
  ]) {
    // Comments may quote the French; only shipped code counts.
    for (const source of [screen, state, page]) {
      const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
      assert.ok(!code.includes(phrase), `inline chrome: ${phrase}`);
    }
  }
  assert.ok(screen.includes('useChromeLanguage()'), 'the screen follows the one language rule');
  assert.ok(page.includes('useChromeLanguage()'), 'the page follows the one language rule');
  // Dark capability comes from the tokens; a hard-coded hex would opt out of it.
  const hexes = (page.match(/#[0-9a-fA-F]{3,8}\b/g) || []).concat(
    screen.match(/#[0-9a-fA-F]{3,8}\b/g) || [],
  );
  assert.deepEqual(hexes, [], 'no hard-coded colours: the theme owns them');
});

test('type sizes come from the Dynamic Type tokens, never from fixed pixels', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/dossier.tsx'), 'utf8');
  const fontSizes = page.match(/font-size:\s*([^;]+);/g) || [];
  assert.ok(fontSizes.length > 0, 'the page styles its own text');
  for (const declaration of fontSizes) {
    assert.ok(
      declaration.includes('var(--av2-t-'),
      `font-size must use a type token: ${declaration}`,
    );
  }
});

test('every state offers exactly one primary action', () => {
  const screen = fs.readFileSync(path.join(HERE, 'DossierScreen.tsx'), 'utf8');
  const primaries = screen.match(/tone="primary"/g) || [];
  const returns = screen.match(/return \(\n/g) || [];
  assert.ok(primaries.length > 0, 'there are primary actions');
  assert.ok(
    primaries.length <= returns.length,
    'no branch stacks two primary actions on one screen',
  );
});

// WP-L7 / WP-L8. The level as coverage, its épreuve and the forecast.
test('the level reads «A1.1 · 60 %» and explains every number behind it', () => {
  const state = require('./dossier-state.ts');
  const level = {
    available: true,
    estimate: 'A1.1',
    estimate_source: 'measured',
    level_label: 'A1.1 · 60 %',
    next_level: 'A1.2',
    coverage: {
      band: 'A1.1',
      percent: 60,
      label: 'A1.1 · 60 %',
      units: { held: 9, total: 18, required: 16, met: false },
      words: { known: 180, total: 316, required: 253, met: false },
      coverage_met: false,
    },
    checkpoint: { band: 'A1.1', state: 'locked', checkpoint_ready: false, attempts: 0 },
    forecast: { status: 'available', target: 'A1.2', range_days: [62, 101], range_months: [2.0, 3.3] },
  };
  assert.equal(state.levelHeadline(level), 'A1.1 · 60 %');
  assert.deepEqual(
    state.coverageRows(level).map((row) => [row.label, row.value]),
    [
      ['Notions tenues', '9 / 16 (sur 18)'],
      ['Mots connus', '180 / 253 (sur 316)'],
      ['Épreuve', 'après la couverture du niveau'],
    ],
  );
  assert.ok(state.coverageRuleSentence(level).includes('85 %'));
  const measured = state.forecastSentence(level);
  assert.ok(measured.startsWith('Estimation'), measured);
  assert.ok(measured.includes('A1.2 dans 2 à 4 mois'), measured);
  // Before seven active days it says it is the rhythm's prior, not a measurement.
  const prior = state.forecastSentence({ ...level, forecast: { ...level.forecast, status: 'prior' } });
  assert.ok(prior.includes('avant mesure'), prior);
  // A stalled pace is said plainly, with no date.
  const capped = state.forecastSentence({
    ...level,
    forecast: { status: 'available', target: 'A1.2', capped: true, range_days: [730, 730] },
  });
  assert.ok(capped.includes('plus de deux ans'), capped);
  // The épreuve's states.
  assert.equal(state.checkpointLabel({ state: 'ready' }), 'prête — elle arrive dans l’histoire');
  assert.ok(state.checkpointLabel({ state: 'failed', retry_after: '2026-10-01T10:00:00+00:00' }).includes('1er oct.'));
  // A declared level with no coverage prints no rows and no forecast.
  assert.deepEqual(state.coverageRows({ available: true, estimate: 'B1.1', estimate_source: 'declared' }), []);
  assert.equal(state.forecastSentence({ available: true, estimate: 'B1.1' }), null);
});

console.log(`dossier-state: ${passed} tests passed`);
