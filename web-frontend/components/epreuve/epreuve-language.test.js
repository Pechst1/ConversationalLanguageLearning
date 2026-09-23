// node --test components/epreuve/epreuve-language.test.js
//
// WP-82 — «Plus de pratique» (L'Épreuve) follows the one language rule.
//
//   1. an A1 English learner reads the drill loop's chrome in English: the
//      buttons, the confidence chips, the rule pill, the verdicts, the notices
//      and the recap — and none of the French chrome it used to print;
//   2. a B1 learner (whatever their own language) reads it in French;
//   3. the exercise itself stays French for both (`lang="fr"` on the content);
//   4. the three copy tables are complete and never empty;
//   5. the page wires it: SessionView and the recap take the chrome language
//      from `useChromeLanguage(journeyLevel(journey))`, and no French chrome
//      literal is left inline in the Épreuve's part of pages/atelier.tsx.

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
  if (request.startsWith('@/')) {
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
const { epreuveCopy, wordRangeText } = require('./epreuve-copy.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');

const h = React.createElement;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

/** One Épreuve screen's worth of chrome, rendered the way SessionView mounts it. */
function renderEpreuve(language) {
  return renderToStaticMarkup(
    h(Ep.EpShell, { language },
      h(Ep.EpTopbar, { groups: [{ total: 10, set: 3 }], cap: ['3/10', ''], run: 2, partial: true }),
      h(Ep.EpEyebrow, { round: 'x', i: 1, n: 3, retour: true }),
      h(Ep.EpConcept, { title: 'Le passé composé' }),
      h(Ep.EpPrompt, null, 'Hier, je ___ au marché.'),
      h(Ep.EpOpts, null, h(Ep.EpOpt, { chosen: true, wrong: true }, 'suis allé')),
      h(Ep.EpConfidence, { value: null }),
      h(Ep.EpRepair, { target: 'Hier, je suis allé au marché.', typed: '', status: 'no', onChange: () => undefined, onSubmit: () => undefined }),
      h(Ep.EpRecord, { status: 'idle' }),
      h(Ep.EpRelecture, { status: 'failed', onRetry: () => undefined }),
      h(Ep.EpSkeleton),
      h(Ep.EpNotice, { onRetry: () => undefined }),
      h(Ep.EpBatStage, { sub: null }),
      h(Ep.EpStreak, { was: 1, now: 2 }),
      h(Ep.EpHandoff, { onHome: () => undefined }),
    ),
  );
}

// The chrome the Épreuve printed in French at every level before WP-82.
const FRENCH_CHROME = [
  'Terminer',
  'La règle',
  'Vous êtes…',
  'sûr·e',
  'Recopiez la correction',
  'Comparer',
  'Touchez pour parler',
  'Relecture interrompue.',
  'Relancer',
  'Préparation de la séance…',
  'Réessayer',
  'Séance terminée',
  'jours de suite',
  'Retour à La Une',
  'Fermer la séance',
];

test('an A1 English learner reads the Épreuve chrome in English', () => {
  const language = chromeLanguage('en', 'A1.1');
  assert.equal(language, 'en');
  const html = renderEpreuve(language);
  const t = epreuveCopy('en');
  for (const word of [t.finish, t.rule, t.confidence_ask, t.sure, t.unsure, t.repair_label, t.repair_submit,
    t.record_idle, t.relecture_failed, t.relaunch, t.skeleton, t.retry, t.recap_title, t.back_home, t.close_session, t.retour]) {
    assert.ok(html.includes(escapeHtml(word)), `missing English chrome: ${word}`);
  }
  for (const french of FRENCH_CHROME) {
    assert.ok(!html.includes(escapeHtml(french)), `French chrome leaked for an A1 learner: ${french}`);
  }
  assert.ok(html.includes('2 days in a row'));
  // The exercise stays French content.
  assert.ok(html.includes('lang="fr"'));
  assert.ok(html.includes('Le passé composé'));
  assert.ok(html.includes(`class="av2 ep-shell`));
});

test('an A1 German learner reads it in German', () => {
  const html = renderEpreuve(chromeLanguage('de', 'A2'));
  const t = epreuveCopy('de');
  for (const word of [t.finish, t.rule, t.sure, t.recap_title, t.back_home]) {
    assert.ok(html.includes(escapeHtml(word)), `missing German chrome: ${word}`);
  }
  assert.ok(!html.includes('Terminer'));
});

test('a B1 learner reads the Épreuve chrome in French, whatever their own language', () => {
  for (const control of ['en', 'de', 'fr']) {
    const language = chromeLanguage(control, 'B1.1');
    assert.equal(language, 'fr');
    const html = renderEpreuve(language);
    for (const french of FRENCH_CHROME) {
      assert.ok(html.includes(escapeHtml(french)), `B1 (${control}) is missing French chrome: ${french}`);
    }
    for (const english of ['Finish', 'The rule', 'Are you…', 'Try again', 'Back to La Une']) {
      assert.ok(!html.includes(escapeHtml(english)), `English chrome leaked for a B1 learner: ${english}`);
    }
  }
});

test('the three Épreuve copy tables are complete and never empty', () => {
  const fr = epreuveCopy('fr');
  const keys = Object.keys(fr).sort();
  for (const language of ['en', 'de', 'fr']) {
    const table = epreuveCopy(language);
    assert.deepEqual(Object.keys(table).sort(), keys, `${language} table keys differ`);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(typeof value === 'string' && value.trim().length > 0, `${language}.${key} is empty`);
      // Sentence case, no shouted labels (design rule: no tracked caps).
      assert.ok(!/^[^a-zà-ÿ]*[A-ZÀ-Ý]{3}[^a-zà-ÿ]*$/.test(value), `${language}.${key} is all caps`);
    }
  }
  assert.equal(epreuveCopy('de-AT').finish, 'Beenden');
  assert.equal(epreuveCopy(null).finish, 'Finish');
  assert.equal(wordRangeText(epreuveCopy('en'), 3, 10, 20), '3 / 10–20 words · 7 more');
  assert.equal(wordRangeText(epreuveCopy('fr'), 4, null, null), '4 mots');
});

test('the practice page takes its chrome language from the rule, and prints no inline French chrome', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.ok(page.includes('const pageChromeLanguage = useChromeLanguage(journeyLevel(journey));'));
  assert.ok(page.includes('language={pageChromeLanguage}'));
  assert.ok(page.includes('<EpShell className="atelier-do-mode" language={language}>'));
  assert.ok(page.includes('<AtelierV2Root as="section" language={language} className="ep ep-recap"'));
  const start = page.indexOf('function SessionView(');
  const end = page.indexOf('function CropMarks()');
  assert.ok(start > 0 && end > start);
  const epreuve = page.slice(start, end);
  for (const literal of [
    "'Vérification…'", "'Vérifier'", '>Bien joué !<', '>À reprendre<', '>Réessayer la ligne<',
    '>Passer cet exercice<', '>Signaler cet exercice<', '>Ajouté au carnet<', "'Terminer'", "'Continuer'",
    '>Passer sans évaluation<', "'Composez votre ligne…'", 'Aucune parole détectée',
  ]) {
    assert.ok(!epreuve.includes(literal), `inline French chrome left in the Épreuve: ${literal}`);
  }
});
