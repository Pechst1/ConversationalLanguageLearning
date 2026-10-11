// node --test components/epreuve/forge-followup.test.js
//
// WP-103 — La Forge's answers say what to do and what happened.
//
//   T3  a Forge item states its goal (or the scene line it is cut from);
//   T9  free production: «Je relis…» with the grading character's face, never
//       «Right / Well done» before the model has read the line;
//   T8  «À corriger» leads to «Corrigez la phrase»: the wrong sentence quoted,
//       a field (tiles at A1), «Passer» shows the right one — the right
//       sentence is always seen; and the page wires all of it.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const Ep = require('./Epreuve.tsx');
const Fu = require('./ForgeFollowUp.tsx');
const { epreuveCopy } = require('./epreuve-copy.ts');
const { classifyRepair } = require('@/lib/forge-followup.ts');
const { drillGoalLine } = require('@/components/atelier-v2/journey/drill-frame.ts');

const h = React.createElement;
const decode = (html) =>
  html.replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/[  ]/g, ' ');
const inShell = (language, child) => decode(renderToStaticMarkup(h(Ep.EpShell, { language }, child)));

const ITEM = {
  id: 'c1',
  prompt: 'Lila cherche un poster grand (Lila is looking for a big poster)',
  labels: ['Correct', 'À corriger'],
  correct_label: 'À corriger',
  classify_kind: 'judgement',
};
const FOLLOW_UP = { kind: 'correct_it', source_fr: 'Lila cherche un poster grand.', goal_native: 'Correct the sentence.' };
const CORRECTED = 'Lila cherche un grand poster.';
const FIELD = classifyRepair(ITEM, { corrected_fr: CORRECTED, follow_up: FOLLOW_UP }).followUp;
const TILES = classifyRepair(ITEM, {
  corrected_fr: CORRECTED,
  follow_up: { ...FOLLOW_UP, options: ['Lila', 'cherche', 'un', 'grand', 'poster', 'petit'] },
}).followUp;

const draft = (extra = {}) => ({ ...Fu.FOLLOW_UP_EMPTY, ...extra });
const followUp = (language, spec, state) =>
  inShell(language, h(Fu.ForgeFollowUp, { followUp: spec, draft: state, onDraft() {} }));

// ---------------------------------------------------------------------------
// T3 · the goal line
// ---------------------------------------------------------------------------

test('T3 · a Forge item prints its goal, or the scene line it is cut from', () => {
  const goal = drillGoalLine({ goal_native: 'Build: "A small white table is in the kitchen."', instruction_native: 'x', prompt_fr: 'y' });
  const html = inShell('en', h(Fu.ForgeGoalLine, { goal }));
  assert.match(html, /<p class="av2-goal ep-goal" data-goal="goal">Build: "A small white table is in the kitchen\."<\/p>/);

  const source = drillGoalLine({ source_fr: 'Une petite table blanche est dans la cuisine.' });
  const scene = inShell('de', h(Fu.ForgeGoalLine, { goal: source }));
  assert.ok(scene.includes('Aus der Szene'));
  assert.ok(scene.includes('Une petite table blanche est dans la cuisine.'));
  assert.equal(inShell('en', h(Fu.ForgeGoalLine, { goal: null })).includes('av2-goal'), false, 'nothing when there is none');
});

// ---------------------------------------------------------------------------
// T9 · «Je relis…»
// ---------------------------------------------------------------------------

test('T9 · while the model reads, the character’s face says «Je relis…» in the chrome language', () => {
  const coach = { id: 'romy_tremblay', name: 'Romy' };
  for (const [language, line] of [['fr', 'Je relis…'], ['en', 'Let me read it again…'], ['de', 'Ich lese es noch einmal …']]) {
    const html = inShell(language, h(Fu.ForgeReading, { coach, onSkip() {} }));
    assert.ok(html.includes(line), `${language}: ${line}`);
    assert.match(html, /data-verdict="checking"/);
    assert.match(html, /role="status"/);
    assert.ok(/romy/i.test(html), 'the grading character’s face is there');
    // No verdict of any kind while it waits.
    const t = epreuveCopy(language);
    for (const word of [t.verdict_correct, t.verdict_wrong, t.stamp_correct, t.line_set]) {
      assert.ok(!html.includes(`>${word}<`), `${language}: no «${word}» while reading`);
    }
  }
});

test('T9 · without a coach the wait still has a mark, and it never becomes a wall', () => {
  const html = inShell('fr', h(Fu.ForgeReading, { coach: null, onSkip() {} }));
  assert.ok(html.includes('Je relis…'));
  assert.ok(html.includes('av2-feedback__icon'));
  // The way on appears after a while (never at once, so the wait reads as a wait).
  assert.ok(!html.includes('ep-reading__skip'), 'not at first');
  assert.ok(Fu.READING_PATIENCE_MS >= 15000 && Fu.READING_PATIENCE_MS <= 60000);
});

test('T9 · the page holds «Right / Well done» back while the model reads, and freezes what was shown', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'atelier.tsx'), 'utf8');
  assert.match(page, /production && productionPhase\(correction\) === 'checking'/, 'a wait, not a verdict');
  assert.match(page, /settleShownCorrection\(prev\[key\], correction\)/, 'a shown verdict is never reversed');
  assert.match(page, /reviewIsPending\(correction\)/, 'the poll asks until the model has read it');
  assert.match(page, /const secondCheck = production \? null : secondCheckChange\(correction\);/, 'no second-check reversal on production');
  assert.match(page, /forgeCorrectionNotes\(correction\)/, 'one block, notes deduplicated');
  // «3 corrections» only when there are three distinct notes.
  assert.match(page, /whyLines\.length > 1/);
});

// ---------------------------------------------------------------------------
// T8 · the follow-up
// ---------------------------------------------------------------------------

test('T8 · after «À corriger»: the wrong sentence quoted, a field, «Passer»', () => {
  const html = followUp('en', FIELD, draft());
  assert.ok(html.includes('Correct the sentence'), 'the title (and the server’s goal)');
  assert.match(html, /<blockquote class="ep-follow__quote" lang="fr">/);
  assert.ok(html.includes('Lila cherche un poster grand.'), 'the wrong sentence is quoted');
  assert.match(html, /<textarea class="ep-composed-input ep-follow__input" lang="fr"/);
  assert.ok(html.includes('>Skip<'), 'and «Passer» is one tap');
  assert.ok(!html.includes(CORRECTED), 'the right sentence is not shown before a try or a skip');
  assert.match(html, /data-outcome="open"/);
  // The check is the secondary; the screen’s one primary is the footer’s.
  assert.ok(!html.includes('av2-btn--primary'));
  assert.match(html, /av2-btn--secondary[^>]*disabled/, 'nothing to check yet');
});

test('T8 · in French: «Corrigez la phrase» and «Passer»', () => {
  const html = followUp('fr', FIELD, draft());
  assert.ok(html.includes('Corrigez la phrase'));
  assert.ok(html.includes('>Passer<'));
});

test('T8 · at A1, an item that carries options is tiles', () => {
  const html = followUp('en', TILES, draft({ placed: [0, 1] }));
  assert.ok(!html.includes('<textarea'), 'no field');
  assert.equal((html.match(/class="av2-tile ep-slug"/g) || []).length, 2 + 6, 'the placed tiles and the bank');
  assert.equal((html.match(/data-spent="true"/g) || []).length, 2, 'placed tiles are spent in the bank');
  assert.ok(Fu.followUpReady(TILES, draft({ placed: [0] })));
  assert.ok(!Fu.followUpReady(TILES, draft()));
  assert.deepEqual(Fu.followUpAnswer(TILES, draft({ placed: [0, 1, 2] })), ['Lila', 'cherche', 'un']);
  assert.equal(Fu.followUpAnswer(FIELD, draft({ text: 'abc' })), 'abc');
  assert.ok(Fu.followUpReady(FIELD, draft({ text: 'abc' })));
  assert.ok(!Fu.followUpReady(FIELD, draft({ text: '   ' })));
});

test('T8 · «Passer» shows the corrected sentence', () => {
  const html = followUp('en', FIELD, draft({ outcome: 'revealed', skipped: true }));
  assert.ok(html.includes(CORRECTED));
  assert.ok(html.includes('The right sentence'));
  assert.match(html, /data-outcome="revealed"/);
  assert.ok(!html.includes('<textarea'), 'settled: the field is gone');
  assert.ok(!html.includes('>Skip<'));
});

test('T8 · a wrong try shows the right one, a right try says so — either way the sentence is seen', () => {
  const wrong = followUp('en', FIELD, draft({ text: 'Lila cherche un poster', outcome: 'revealed' }));
  assert.ok(wrong.includes('Not quite'));
  assert.ok(wrong.includes(CORRECTED));
  const right = followUp('en', FIELD, draft({ text: 'lila cherche un grand poster', outcome: 'right' }));
  assert.ok(right.includes('That is the right sentence'));
  assert.ok(right.includes(CORRECTED));
  assert.match(right, /data-outcome="right"/);
});

test('T8 · without a follow-up the corrected sentence is a plain «La bonne phrase» line', () => {
  const html = inShell('fr', h(Fu.ForgeCorrectedLine, { fr: CORRECTED }));
  assert.ok(html.includes('La bonne phrase'));
  assert.ok(html.includes(CORRECTED));
  assert.equal(inShell('fr', h(Fu.ForgeCorrectedLine, { fr: '' })).includes('ep-follow'), false);
  assert.equal(inShell('fr', h(Fu.ForgeCorrectedLine, { fr: null })).includes('ep-follow'), false);
});

test('T8 · the page gates «Continue» on the follow-up, and never on a payload without one', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'atelier.tsx'), 'utf8');
  assert.match(page, /const followGate = Boolean\(repairOf\.followUp\) && followDraft\.outcome === null;/);
  assert.match(page, /\{!followGate && <EpBar icon="check" onClick=\{onNext\}>\{nextLabel\}<\/EpBar>\}/);
  assert.match(page, /classifyRepair\(classifyItem, correction\)/);
  assert.match(page, /<ForgeCorrectedLine fr=\{repairOf\.correctedFr\} \/>/);
  // The gate is per exercise, so a return finds the draft where it was left.
  assert.match(page, /followUps\[feedbackKey\]/);
});

test('WP-103 · every new Épreuve key exists in en, de and fr', () => {
  const keys = [
    'from_scene', 'reading', 'follow_title', 'follow_wrong_label', 'follow_placeholder',
    'follow_skip', 'follow_right', 'follow_not_quite', 'corrected_sentence',
  ];
  for (const language of ['en', 'de', 'fr']) {
    const table = epreuveCopy(language);
    for (const key of keys) {
      assert.equal(typeof table[key], 'string', `${language}.${key}`);
      assert.ok(table[key].trim().length > 0, `${language}.${key}`);
    }
  }
  assert.equal(epreuveCopy('fr').reading, 'Je relis…');
  assert.equal(epreuveCopy('fr').follow_title, 'Corrigez la phrase');
  assert.equal(epreuveCopy('fr').follow_skip, 'Passer');
});
