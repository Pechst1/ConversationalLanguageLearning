// node --test components/courrier/courrier-language.test.js
//
// WP-82 / WP-83 — Le Courrier follows the one language rule.
//
//   1. an A1 English learner reads the Courrier's chrome in English — the
//      header's back label, the situation, the ribbon, the repair note, the
//      memo, the composer pill, the seal, the correspondence, the intake —
//      and none of the French chrome it used to print;
//   2. a B1 learner (whatever their own language) reads it in French;
//   3. the letter itself — the correspondent's name, the situation, the
//      character's line, the words to place — stays French with `lang="fr"`;
//   4. the three copy tables are complete, never empty, and fill the same
//      placeholders;
//   5. the composer renders collapsed, as one «Reply» / «Répondre» pill, and
//      is never sticky over the letter;
//   6. the page wires it: `useChromeLanguage()` once, handed to AtelierV2Root.

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

const Cr = require('./Courrier.tsx');
const Corr = require('./Correspondance.tsx');
const Waiting = require('./courrier-waiting.tsx');
const { courrierCopy } = require('./courrier-copy.ts');
const { AtelierV2Root } = require('@/components/atelier-v2/ui/AtelierV2Root.tsx');
const { chromeLanguage } = require('@/lib/language-rule.ts');

const h = React.createElement;
const noop = () => undefined;
const TODAY = new Date('2026-09-21T10:00:00Z');
const SAMIRA = { id: 'samira', name: 'Samira', role: 'boulangère', mood_line: 'Un peu distante en ce moment.' };
const FRAME = 'La boulangerie ferme plus tôt samedi.';
const ASK = 'Demandez une heure pour vendredi.';
const LINE = 'Bonjour ! Vous passez quand ?';

const decode = (s) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"');
const text = (html) => decode(html.replace(/<[^>]+>/g, ' '));
/** What a learner reads or hears: the text, plus aria-labels, titles and placeholders. */
const heard = (html) =>
  `${text(html)} ${[...html.matchAll(/(?:aria-label|title|placeholder)="([^"]*)"/g)].map((m) => decode(m[1])).join(' ')}`;

/** The Courrier's pieces, as missions.tsx mounts them for one letter. */
function renderCourrier(language) {
  return renderToStaticMarkup(
    h(AtelierV2Root, { as: 'main', language, className: 'cr' },
      h(Cr.CrDesk, { name: 'Samira', line: 'x · La boulangerie' }),
      h(Corr.CrCorrespondent, {
        correspondent: SAMIRA,
        chain: { index: 2, total: 3 },
        expiresAt: '2026-09-24T18:00:00Z',
        now: TODAY,
        history: [{ mission_id: 'm0', summary_fr: 'Le pain mis de côté', outcome: 'kept', at: '2026-09-12T09:00:00Z' }],
      }),
      h(Cr.CrSituation, { frame: FRAME, ask: ASK, translate: async () => '' }),
      h(Cr.CrRibbon, { words: [{ t: 'fermer', used: true }, { t: 'samedi' }] }),
      h('div', { className: 'cr-thread' },
        h(Cr.CrSlip, { who: 'Samira', translate: async () => '' }, LINE),
        h(Cr.CrRepair, { correctedAnswer: 'Je passe vendredi.', lines: [{ fixed: 'vendredi' }], savedCount: 2 }),
        h(Cr.CrMemo, { rows: [['x', 'Samira']], transcript: LINE, stamp: 'y' }),
      ),
      h(Cr.CrComposer, { canFinish: true, onFinish: noop }, h('textarea', { lang: 'fr' })),
      h(Cr.CrSeal, {
        verdict: Corr.crOutcomeLabel('kept', language),
        sentence: Corr.crOutcomeSentence('kept', 'Samira', language),
        numbers: Cr.crSealNumbers({ objectives_met: 1, objectives_total: 2, repairs: 2, words_written: 40 }, {}, language),
      }),
      h(Corr.CrLapsedNotice, { name: 'Samira' }),
      h(Cr.CrIntakeLink, {}),
      h(Cr.CrIntakeEntry, { cap: { limit: 5, used: 1, remaining: 4, enabled: true }, onRead: noop }),
      h(Cr.CrArtefactUnread, { onRetry: noop, onDelete: noop }),
    ),
  );
}

// The chrome the Courrier printed in French at every level before WP-82.
const FRENCH_CHROME = [
  'Retour à la Une',
  'Traduire',
  'À faire',
  'À placer',
  'Bien dit',
  'réparations enregistrées',
  'Message téléphonique',
  'Répondre',
  'Parole tenue',
  'Vous avez fait ce que',
  'objectifs tenus',
  'si vous pouvez',
  'lettre sur 3',
  'lettre précédente',
  'Le délai est passé',
  'Apportez votre français',
  'Coller un texte',
  'Photographier',
  'Non lu',
  'Réessayer',
];

const ENGLISH_CHROME = [
  'Back to La Une',
  'Translate',
  'To do',
  'Use',
  'Well said',
  '2 fixes saved',
  'Phone message',
  'Reply',
  'Promise kept',
  'You did what Samira asked.',
  'goals met',
  'Reply by Thursday if you can.',
  'Letter 2 of 3',
  'Your previous letter',
  'The time ran out',
  'Bring your own French',
  'Paste a text',
  'Take a photo',
  'Not read',
  'Try again',
];

test('an A1 English learner reads the Courrier chrome in English', () => {
  const language = chromeLanguage('en', 'A1.1');
  assert.equal(language, 'en');
  const html = heard(renderCourrier(language));
  for (const phrase of ENGLISH_CHROME) assert.ok(html.includes(phrase), `missing English chrome: ${phrase}`);
  for (const phrase of FRENCH_CHROME) assert.ok(!html.includes(phrase), `French chrome leaked for an A1 learner: ${phrase}`);
});

test('an A2 German learner reads it in German', () => {
  const html = heard(renderCourrier(chromeLanguage('de', 'A2')));
  for (const phrase of ['Zurück zu La Une', 'Antworten', 'Wort gehalten', 'Brief 2 von 3', 'Nicht gelesen']) {
    assert.ok(html.includes(phrase), `missing German chrome: ${phrase}`);
  }
  for (const phrase of ['Traduire', 'Parole tenue', 'Promise kept', 'Reply']) {
    assert.ok(!html.includes(phrase), `wrong chrome for a German A2 learner: ${phrase}`);
  }
});

test('a B1 learner reads French chrome, whatever their own language', () => {
  const language = chromeLanguage('en', 'B1');
  assert.equal(language, 'fr');
  const html = heard(renderCourrier(language));
  for (const phrase of ['Retour à la Une', 'Répondre', 'Parole tenue', '2ᵉ lettre sur 3', 'Répondez avant jeudi, si vous pouvez.', 'Non lu']) {
    assert.ok(html.includes(phrase), `missing French chrome: ${phrase}`);
  }
  for (const phrase of ENGLISH_CHROME.filter((p) => !['Use'].includes(p))) {
    assert.ok(!html.includes(phrase), `English chrome leaked for a B1 learner: ${phrase}`);
  }
});

test('the letter stays French with lang="fr" at every level', () => {
  for (const language of ['en', 'de', 'fr']) {
    const html = renderCourrier(language);
    assert.match(html, /<h1 class="cr-name" lang="fr">Samira<\/h1>/);
    assert.ok(html.includes(`<p class="cr-sit-frame" lang="fr">${FRAME}</p>`), 'the situation is content');
    assert.ok(html.includes(`<span lang="fr">${ASK}</span>`), 'the ask is content');
    assert.match(html, /class="av2-bubble" lang="fr">.*Bonjour ! Vous passez quand \?/);
    assert.match(html, /<span lang="fr">fermer<\/span>/);
    assert.match(html, /<p class="cr-corr-mood" lang="fr">/);
    assert.match(html, /<span class="cr-corr-past" lang="fr">Le pain mis de côté/);
  }
});

test('the composer is collapsed to one Reply pill, the screen’s one press', () => {
  for (const [language, label] of [['en', 'Reply'], ['de', 'Antworten'], ['fr', 'Répondre']]) {
    const html = renderToStaticMarkup(
      h(AtelierV2Root, { language }, h(Cr.CrComposer, {}, h('textarea', { lang: 'fr' }))),
    );
    assert.match(html, /cr-composer--closed/);
    assert.ok(text(html).includes(label), `${language}: the pill says ${label}`);
    assert.ok(!html.includes('<textarea'), 'the well is closed until asked for');
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, 'the pill is the one 3D press');
    assert.match(html, /aria-expanded="false"/);
  }
  // Something already in it (a restored draft, a recording) keeps it open.
  const open = renderToStaticMarkup(
    h(AtelierV2Root, { language: 'en' }, h(Cr.CrComposer, { open: true }, h('textarea', { lang: 'fr' }))),
  );
  assert.ok(open.includes('<textarea'));
  assert.ok(!open.includes('cr-composer--closed'));
});

test('the composer is never sticky over the letter, and the header is one line', () => {
  const source = fs.readFileSync(path.join(__dirname, 'Courrier.tsx'), 'utf8');
  const rule = source.match(/\.av2 \.cr-composer \{[^}]*\}/);
  assert.ok(rule, 'the composer rule exists');
  assert.ok(!/position:\s*(sticky|fixed)/.test(rule[0]), 'the composer must sit in the flow');
  assert.ok(source.includes('env(safe-area-inset-bottom'), 'it scrolls clear of the home indicator');
  assert.ok(!source.includes('.av2 .cr-line'), 'no second kicker line under the name');
  const desk = renderToStaticMarkup(h(AtelierV2Root, { language: 'en' }, h(Cr.CrDesk, { name: 'Samira', line: 'Le Courrier · x' })));
  assert.ok(!desk.includes('cr-line'));
  assert.match(desk, /class="av2-sr">Le Courrier · x/);
  // The 44px floor on the controls this file owns.
  assert.match(source, /\.cr-quick-chip \{[^}]*min-height: var\(--av2-tap\)/);
  assert.match(source, /\.cr-reply-pill \{[^}]*min-height: var\(--av2-tap\)/);
  // 320px: long French words wrap instead of widening the page.
  assert.match(source, /\.cr-turn \.av2-bubble \{[^}]*overflow-wrap: anywhere/);
});

test('the seal is one card: verdict, one sentence, three numbers at most', () => {
  const numbers = Cr.crSealNumbers(
    { objectives_met: 1, objectives_total: 2, repairs: 3, phrases_saved: 4, words_written: 40 },
    {},
    'en',
  );
  assert.deepEqual(numbers.map((n) => n.value), ['1/2', '3', '40']);
  assert.equal(Cr.crSealNumbers({ objectives_total: 2, assessed: false }, {}, 'en').length, 0, 'no verdict nobody gave');
  assert.equal(Cr.crSealNumbers(null, { turns: 2, errata: 1, saved: 0 }, 'fr').length, 3);
  const html = renderToStaticMarkup(
    h(AtelierV2Root, { language: 'en' }, h(Cr.CrSeal, { verdict: 'Promise kept', sentence: 'You did what Samira asked.', numbers: numbers.concat(numbers) })),
  );
  assert.equal((html.match(/<dd>/g) || []).length, 3);
  assert.equal((html.match(/class="cr-seal-sub"/g) || []).length, 1);
});

test('the waiting-letter rows take a language and default to French', () => {
  assert.equal(
    Corr.crLetterHint({ name: 'Samira', chain: { index: 2, total: 3 }, expiresAt: '2026-09-24T18:00:00Z', now: TODAY, language: 'en' }),
    'Letter 2 of 3, from Samira · reply by Thursday if you can.',
  );
  assert.equal(Corr.crLetterHint({ name: 'Samira' }), 'Samira attend votre réponse.');
  const letter = { id: 'm1', status: 'in_progress', correspondent: { name: 'Samira' } };
  assert.equal(Waiting.courrierHomeEntry(letter).label, 'Votre réponse est commencée');
  assert.equal(Waiting.courrierHomeEntry(letter, undefined, 'en').label, 'You started your reply');
  assert.equal(Waiting.courrierHomeEntry({ ...letter, status: 'available' }, undefined, 'de').label, 'Ein Brief wartet auf dich');
  const fr = renderToStaticMarkup(h(Corr.CrLetterRow, { name: 'Samira' }));
  assert.ok(fr.includes('Une lettre vous attend'));
  const en = renderToStaticMarkup(h(Corr.CrLetterRow, { name: 'Samira', language: 'en' }));
  assert.ok(en.includes('A letter is waiting') && en.includes('Samira is waiting for your reply.'));
  assert.equal(Cr.crReadAndReplyLabel(8), 'Lire et répondre · 8 min');
  assert.equal(Cr.crReadAndReplyLabel(8, 'en'), 'Read and reply · 8 min');
});

test('the three copy tables are complete and fill the same placeholders', () => {
  const fr = courrierCopy('fr');
  const keys = Object.keys(fr).sort();
  const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
  for (const language of ['en', 'de']) {
    const table = courrierCopy(language);
    assert.deepEqual(Object.keys(table).sort(), keys, `${language} has exactly the French keys`);
    for (const key of keys) {
      assert.ok(String(table[key]).trim().length > 0, `${language}.${key} is empty`);
      // French ordinals are written out; English and German count instead.
      if (key === 'chain_label') continue;
      assert.equal(holes(table[key]), holes(fr[key]), `${language}.${key} fills other placeholders`);
    }
  }
  // Place names are French in every column.
  for (const language of ['en', 'de', 'fr']) {
    assert.equal(courrierCopy(language).courrier, 'Le Courrier');
  }
});

test('the page computes the chrome language once and hands it to its root', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/missions.tsx'), 'utf8');
  assert.equal((page.match(/useChromeLanguage\(\)/g) || []).length, 1);
  assert.match(page, /<AtelierV2Root\s+as="main"\s+language=\{chromeLang\}/);
  // The mic follows the same chrome language, never a second one.
  assert.ok(page.includes('atelierChrome(useControlLanguage())'));
  assert.ok(!page.includes('useLearnerLanguage'));
  // No French chrome literal is left inline in the JSX.
  for (const phrase of ['Retour à l’Atelier</', 'Nouveau courrier</', 'Courrier passé</', 'Chargement du courrier', '>Bouclé<', 'rédige sa réponse']) {
    assert.ok(!page.includes(phrase), `inline French chrome: ${phrase}`);
  }
});
