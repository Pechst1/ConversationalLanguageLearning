/**
 * WP-65 — «Le Courrier, surface»: the correspondence.
 *
 * Same harness as `courrier-intake.test.js`: a plain node script with
 * `node:assert/strict` and sucrase, no test framework, no new dependency.
 *
 * These are failure-mode tests, not snapshots. What they hold down:
 *
 *   1. the honest-numbers rule — the debrief prints only what `recap.measured`
 *      counted, never a percentage, and the deleted `readiness.overall`
 *      (`55 + words * 0.45`) has no successor anywhere on the screen;
 *   2. the mood line is labelled with WHEN it was measured. The payload carries
 *      the mood the letter was *written* with, so a debrief that said
 *      «maintenant» would be inventing the very number this package removed;
 *   3. a soft deadline is a sentence that ends in «si vous pouvez», never a
 *      countdown, and a deadline already past prints nothing at all;
 *   4. a lapsed letter is never a fail screen: no «échec», no score, no retry;
 *   5. one primary press per screen — nothing in this file is a press. The
 *      waiting letter is a ROW, because it is the day's second action;
 *   6. chain progress is French and ordinal («2ᵉ lettre sur 3»), and a chain of
 *      one is not a chain;
 *   7. status is never colour alone — every outcome carries its word;
 *   8. every new rule is scoped `.av2 .cr-…` and uses `--av2-*` tokens only, so
 *      dark mode comes free and no legacy page reset can outrank it.
 *
 * Run: `node components/courrier/courrier-correspondance.test.js`
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

// `<style jsx global>` is compiled by Next's own transform; sucrase leaves the
// props on the element, so React warns about them once per render here. The
// warning is about this harness, not about the components, and drowns the
// results — everything else still reaches the console. Installed before React
// loads, because the warning path binds `console.error` on first use.
const passThroughError = console.error;
console.error = (...args) => {
  const message = args.map((part) => String(part)).join(' ');
  if (/non-boolean attribute/.test(message) && /\b(jsx|global)\b/.test(message)) return;
  passThroughError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const {
  CrCorrespondent,
  CrDebrief,
  CrLapsedNotice,
  CrLetterRow,
  crChainLabel,
  crExpiryLine,
  crLetterHint,
  crMeasuredRows,
  crOutcomeLabel,
} = require('./Correspondance.tsx');

const { AtelierV2Root } = require('@/components/atelier-v2/ui/AtelierV2Root.tsx');

const SOURCE = fs.readFileSync(path.join(HERE, 'Correspondance.tsx'), 'utf8');
const WAITING = fs.readFileSync(path.join(HERE, 'courrier-waiting.tsx'), 'utf8');
const MISSIONS = fs.readFileSync(path.join(WEB_ROOT, 'pages/missions.tsx'), 'utf8');
const h = React.createElement;
// WP-82: the Courrier's chrome follows the root's chrome language. These tests
// hold down the French (B1+) reading, so every component renders inside a
// French root; the root's own wrapper is peeled off so an empty component
// still renders as ''. The English/German reading is
// `courrier-language.test.js`.
const render = (element) =>
  renderToStaticMarkup(h(AtelierV2Root, { language: 'fr' }, element))
    .replace(/^<div[^>]*>/, '')
    .replace(/<\/div>$/, '');

const TODAY = new Date('2026-09-21T10:00:00Z');
const SAMIRA = { id: 'samira', name: 'Samira', role: 'boulangère', mood_line: 'Un peu distant(e) en ce moment.' };

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

/* ---------------------------------------------------------------- chains */

test('a chain says which instalment this is, with a French ordinal', () => {
  assert.equal(crChainLabel({ index: 2, total: 3 }), '2ᵉ lettre sur 3');
  assert.equal(crChainLabel({ index: 1, total: 4 }), '1ʳᵉ lettre sur 4');
  assert.equal(crChainLabel({ index: 4, total: 4 }), '4ᵉ lettre sur 4');
});

test('a letter that is not part of a chain says nothing about chains', () => {
  assert.equal(crChainLabel(null), null);
  assert.equal(crChainLabel({ index: 1, total: 1 }), null);
  const markup = render(h(CrCorrespondent, { correspondent: SAMIRA, chain: { index: 1, total: 1 } }));
  assert.ok(!markup.includes('lettre sur'));
});

/* --------------------------------------------------------- soft deadline */

test('the deadline is a soft sentence, never a countdown', () => {
  assert.equal(crExpiryLine('2026-09-21T18:00:00Z', TODAY), 'Répondez aujourd’hui, si vous pouvez.');
  assert.equal(crExpiryLine('2026-09-22T18:00:00Z', TODAY), 'Répondez d’ici demain, si vous pouvez.');
  assert.equal(crExpiryLine('2026-09-24T18:00:00Z', TODAY), 'Répondez avant jeudi, si vous pouvez.');
  const far = crExpiryLine('2026-10-03T18:00:00Z', TODAY);
  assert.ok(far.startsWith('Répondez avant le 3 octobre'), far);
  for (const line of [
    crExpiryLine('2026-09-21T18:00:00Z', TODAY),
    crExpiryLine('2026-09-24T18:00:00Z', TODAY),
  ]) {
    assert.ok(!/\d+\s*(h|heures?|jours? restants?)/.test(line), line);
  }
});

test('a deadline already past prints nothing — the lapse notice speaks instead', () => {
  assert.equal(crExpiryLine('2026-09-19T18:00:00Z', TODAY), null);
  assert.equal(crExpiryLine(null, TODAY), null);
  assert.equal(crExpiryLine('pas une date', TODAY), null);
  const markup = render(h(CrCorrespondent, {
    correspondent: SAMIRA,
    expiresAt: '2026-09-24T18:00:00Z',
    lapsed: true,
    now: TODAY,
  }));
  assert.ok(!markup.includes('Répondez avant'));
});

/* ------------------------------------------------------------- the lapse */

test('a lapsed letter is a fact, not a fail screen', () => {
  const markup = render(h(CrLapsedNotice, { name: 'Samira' }));
  assert.ok(markup.includes('Restée sans réponse'));
  assert.ok(markup.includes('Samira'));
  // No verdict vocabulary, no score, and nothing to press: the delay is past
  // and a retry would be pretending it is not.
  for (const forbidden of ['échec', 'Échec', 'raté', 'perdu', 'Réessayer', '<button']) {
    assert.ok(!markup.includes(forbidden), `lapse notice must not contain ${forbidden}`);
  }
  assert.ok(!/\d+\s?%/.test(markup));
});

test('the page takes the composer off a lapsed letter and keeps one quiet way on', () => {
  assert.ok(MISSIONS.includes("const lapsed = mission?.status === 'lapsed'"));
  assert.ok(MISSIONS.includes('{!completed && !lapsed && ('));
  assert.ok(MISSIONS.includes('<CrLapsedNotice name={correspondent?.name} />'));
});

/* ---------------------------------------------------------- the debrief */

test('the debrief prints only what was counted', () => {
  const rows = crMeasuredRows({
    objectives_met: 1,
    objectives_total: 2,
    repairs: 2,
    phrases_saved: 3,
    words_written: 64,
  });
  assert.deepEqual(rows.map((row) => row.label), [
    'Objectifs tenus',
    'Réparations',
    'Phrases mises de côté',
    'Mots écrits',
  ]);
  assert.equal(rows[0].value, '1 sur 2');
  assert.equal(rows[3].value, '64');
});

test('no percentage, no readiness, no formula over word count survives', () => {
  const markup = render(h(CrDebrief, {
    outcome: 'partial',
    measured: { objectives_met: 1, objectives_total: 2, repairs: 1, words_written: 80 },
    correspondent: SAMIRA,
    storySummary: 'Vous avez promis de passer samedi matin.',
  }));
  assert.ok(!/\d+\s?%/.test(markup), 'the debrief must never print a percentage');
  for (const dead of ['Prêt pour la vraie vie', 'readiness', 'naturalness', 'clarté', 'Registre']) {
    assert.ok(!markup.includes(dead), `${dead} was deleted by WP-64 and must not come back`);
  }
  assert.ok(!MISSIONS.includes('mission.recap.readiness'));
  assert.ok(!MISSIONS.includes('cr-readiness'));
});

test('the outcome is a French word, and never colour alone', () => {
  assert.equal(crOutcomeLabel('kept'), 'Parole tenue');
  assert.equal(crOutcomeLabel('partial'), 'En partie');
  assert.equal(crOutcomeLabel('missed'), 'Manqué cette fois');
  assert.equal(crOutcomeLabel('ignored'), 'Restée sans réponse');
  assert.equal(crOutcomeLabel('quelque chose'), null);
  for (const outcome of ['kept', 'partial', 'missed']) {
    const markup = render(h(CrDebrief, { outcome, measured: { objectives_met: 1, objectives_total: 1 } }));
    assert.ok(markup.includes(crOutcomeLabel(outcome)), outcome);
    assert.ok(markup.includes('av2-shape'), `${outcome} must carry its shape token, not colour alone`);
  }
});

test('the mood line is labelled with when it was measured, never as "now"', () => {
  const markup = render(h(CrDebrief, {
    outcome: 'kept',
    measured: { objectives_met: 2, objectives_total: 2 },
    correspondent: SAMIRA,
    storySummary: 'Vous avez promis de passer samedi matin.',
  }));
  assert.ok(markup.includes('À la réception de votre lettre'));
  assert.ok(markup.includes(SAMIRA.mood_line));
  assert.ok(markup.includes('Ce que Samira retient'));
  assert.ok(!markup.includes('maintenant'));
});

test('a debrief with nothing measured renders nothing rather than an empty card', () => {
  assert.equal(render(h(CrDebrief, {})), '');
  assert.deepEqual(crMeasuredRows(null), []);
  // A zero objective count is still a fact the learner is owed; a zero repair
  // count is an absence and has no row.
  assert.deepEqual(
    crMeasuredRows({ objectives_met: 0, objectives_total: 2, repairs: 0, words_written: 0 }),
    [{ label: 'Objectifs tenus', value: '0 sur 2' }],
  );
});

/* ----------------------------------------------------- the correspondent */

test('the correspondent view is the thread with one person over weeks', () => {
  const markup = render(h(CrCorrespondent, {
    correspondent: SAMIRA,
    chain: { index: 2, total: 3 },
    expiresAt: '2026-09-24T18:00:00Z',
    now: TODAY,
    history: [
      { mission_id: 'a', summary_fr: 'Le pain mis de côté', outcome: 'kept', at: '2026-09-12T09:00:00Z' },
      { mission_id: 'b', summary_fr: 'La commande à changer', outcome: 'partial', at: '2026-09-16T09:00:00Z' },
    ],
  }));
  assert.ok(markup.includes('Samira'));
  assert.ok(markup.includes('boulangère'));
  assert.ok(markup.includes('Un peu distant'));
  assert.ok(markup.includes('2ᵉ lettre sur 3'));
  assert.ok(markup.includes('Répondez avant jeudi, si vous pouvez.'));
  assert.ok(markup.includes('Vos 2 lettres précédentes'));
  assert.ok(markup.includes('Le pain mis de côté'));
  assert.ok(markup.includes('Parole tenue'));
  assert.ok(markup.includes('En partie'));
});

test('a letter with nobody behind it renders no correspondent card', () => {
  assert.equal(render(h(CrCorrespondent, { correspondent: null })), '');
  assert.equal(render(h(CrCorrespondent, { correspondent: { name: '  ' } })), '');
});

test('the answered letter leaves the mood to the debrief, which dates it', () => {
  const markup = render(h(CrCorrespondent, { correspondent: SAMIRA, showMood: false }));
  assert.ok(markup.includes('Samira'));
  assert.ok(!markup.includes('Un peu distant'));
  assert.ok(MISSIONS.includes('showMood={!completed}'));
});

test('an answered letter is one seal, not a debrief stacked under a recap (Appendix A)', () => {
  // The seal owns the verdict, one sentence and ≤ 3 numbers; the debrief
  // card, the credit rows, the objectives and the repeated last message are
  // gone from the page.
  assert.ok(MISSIONS.includes('<CrSeal'));
  for (const gone of ['<CrDebrief', 'cr-credit', 'cr-objectives', 'cr-recap-grid', 'cr-next"', 'resolutionCredit']) {
    assert.ok(!MISSIONS.includes(gone), `${gone} must not come back to the answered letter`);
  }
});

/* ------------------------------------------------- the waiting letter row */

test('the waiting letter is a row, never a second press', () => {
  const markup = render(h(CrLetterRow, { name: 'Samira', hint: 'Samira attend votre réponse.' }));
  assert.ok(markup.includes('av2-row'));
  assert.ok(!markup.includes('av2-btn--primary'));
  assert.ok(!markup.includes('<button'));
  assert.ok(markup.includes('Une lettre vous attend'));
});

test('the hint says which letter it is, then how long there is', () => {
  assert.equal(
    crLetterHint({ name: 'Samira', chain: { index: 2, total: 3 }, expiresAt: '2026-09-24T18:00:00Z', now: TODAY }),
    '2ᵉ lettre sur 3, de Samira · répondez avant jeudi, si vous pouvez.',
  );
  assert.equal(
    crLetterHint({ name: 'Romy', origin: 'story_born' }),
    'Romy vous écrit après l’épisode.',
  );
  assert.equal(crLetterHint({ name: 'Samira' }), 'Samira attend votre réponse.');
  assert.equal(crLetterHint({}), 'Le Courrier vous attend.');
});

test('both Home and the Feuilleton read the letter through /missions/today', () => {
  // WP-64 materialises the chain instalment and the story-born letter inside
  // that call; anything cheaper would leave them unopened.
  assert.ok(WAITING.includes("COURRIER_TODAY_KEY = 'missions/today'"));
  assert.ok(WAITING.includes('apiService.getMissionsToday()'));
  assert.ok(WAITING.includes('oncePerLoad(COURRIER_TODAY_KEY'));
  // A finished or lapsed letter is not waiting on anybody.
  assert.ok(WAITING.includes("mission.status === 'available' || mission.status === 'in_progress'"));
  // Only a story-born letter reaches the Feuilleton.
  assert.ok(WAITING.includes("=== 'story_born'"));
});

/* -------------------------------------------------------------- the CSS */

test('every new rule is scoped .av2 .cr-… and can never reach a legacy page', () => {
  const block = SOURCE.slice(SOURCE.indexOf('export function CourrierCorrespondanceStyles'));
  const selectors = block.match(/^\s*\.[^\n{]*\{/gm) || [];
  assert.ok(selectors.length > 10, 'expected the style block to be found');
  selectors.forEach((selector) => {
    assert.ok(selector.trim().startsWith('.av2 .cr-'), `unscoped selector: ${selector.trim()}`);
  });
});

test('colours come from --av2 tokens only, so dark mode comes free', () => {
  const block = SOURCE.slice(SOURCE.indexOf('export function CourrierCorrespondanceStyles'));
  const literals = block.match(/#[0-9a-fA-F]{3,8}\b|\brgba?\(/g) || [];
  assert.deepEqual(literals, [], `hard-coded colours: ${literals.join(', ')}`);
  assert.ok(block.includes('var(--av2-'));
});

test('nothing in the correspondence is French-free or English chrome', () => {
  const markup = [
    render(h(CrCorrespondent, { correspondent: SAMIRA, now: TODAY })),
    render(h(CrLapsedNotice, { name: 'Samira' })),
    render(h(CrDebrief, { outcome: 'kept', measured: { objectives_met: 1, objectives_total: 1 } })),
    render(h(CrLetterRow, { name: 'Samira' })),
  ].join(' ');
  for (const english of ['Letter', 'Reply', 'Outcome', 'Deadline', 'Score', 'Progress']) {
    assert.ok(!markup.includes(english), `English chrome: ${english}`);
  }
});

let failed = 0;
tests.forEach(([name, fn]) => {
  try {
    fn();
    console.log(`  ok  ${name}`);
  } catch (error) {
    failed += 1;
    console.error(`FAIL  ${name}`);
    console.error(`      ${error.message}`);
  }
});
console.log(`\n${tests.length - failed}/${tests.length} passed`);
process.exit(failed ? 1 : 0);
