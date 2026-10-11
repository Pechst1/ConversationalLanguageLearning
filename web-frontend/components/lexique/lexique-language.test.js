// node --test components/lexique/lexique-language.test.js
//
// WP-82 / WP-83 — Le Lexique follows the one language rule.
//
//   1. an A1 English learner reads the Lexique chrome (the registre, the review
//      deck, the conjugation drill, les mots du jour) in English, and none of
//      the French chrome it used to print for everyone;
//   2. an A2 German learner reads it in German;
//   3. a B1 learner, whatever their own language, reads it in French;
//   4. the French words stay French for all three (content is never chrome);
//   5. the three copy tables are complete and never empty or shouted;
//   6. Appendix A «Mots»: the due count is said once, on the one primary;
//   7. each page wires it: `useChromeLanguage()` once, `language=` on its
//      AtelierV2Root, and no French chrome literal left inline.
//
// The pages are rendered server-side with the profile hook stubbed to the
// learner under test (the real hook starts at `en` until the profile loads).

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
  const first = String(args[0] || '');
  if (first.includes('non-boolean attribute') || first.includes('useLayoutEffect')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { RouterContext } = require('next/dist/shared/lib/router-context.shared-runtime');

const { chromeLanguage } = require('@/lib/language-rule.ts');

// The learner under test: the pages ask `useChromeLanguage()`, which is the
// profile's native language and CEFR estimate through `chromeLanguage`.
let learner = { language: 'en', level: 'A1.1' };
const learnerLanguagePath = require.resolve('@/lib/learner-language.ts');
const realLearnerLanguage = require(learnerLanguagePath);
require.cache[learnerLanguagePath].exports = {
  ...realLearnerLanguage,
  useChromeLanguage: () => chromeLanguage(learner.language, learner.level),
  useLearnerLanguage: () => learner.language,
};

const {
  lexiqueCopy,
  landingCounts,
  partOfSpeechLabel,
  nextReviewText,
  PART_OF_SPEECH_LABELS,
} = require('./lexique-copy.ts');
const MotsDuJour = require('./MotsDuJour.tsx').default;
const VocabularyPage = require('@/pages/vocabulary.tsx').default;
const ReviewPage = require('@/pages/vocabulary/review.tsx').default;
const ConjugationPage = require('@/pages/vocabulary/conjugation.tsx').default;

const h = React.createElement;

const fakeRouter = {
  pathname: '/vocabulary',
  route: '/vocabulary',
  asPath: '/vocabulary',
  basePath: '',
  query: {},
  isReady: false,
  isFallback: false,
  isPreview: false,
  isLocaleDomain: false,
  push: async () => true,
  replace: async () => true,
  reload: () => undefined,
  back: () => undefined,
  forward: () => undefined,
  prefetch: async () => undefined,
  beforePopState: () => undefined,
  events: { on: () => undefined, off: () => undefined, emit: () => undefined },
};

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

function render(element) {
  return renderToStaticMarkup(h(RouterContext.Provider, { value: fakeRouter }, element));
}

const SLATE = {
  words: [
    { word_id: 1, word: 'réapprovisionnement', translation: 'restocking', gender: 'm', part_of_speech: 'noun', bucket: 'new', stamps: { lu: true }, triple: false, anchor: null },
    { word_id: 2, word: 'la boulangerie', translation: 'the bakery', gender: 'f', part_of_speech: 'noun', bucket: 'due', stamps: { lu: true, retrouve: true, place: true }, triple: true, anchor: null },
  ],
};

/** Everything the Lexique prints on first paint, for one learner. */
function renderLexique(nextLearner) {
  learner = nextLearner;
  return [
    render(h(VocabularyPage)),
    render(h(ReviewPage)),
    render(h(ConjugationPage)),
    render(h(MotsDuJour, { slate: SLATE, due: 4, language: chromeLanguage(learner.language, learner.level) })),
  ].join('\n');
}

// The chrome the Lexique printed in French at every level before WP-82.
const FRENCH_CHROME = [
  'Chercher un mot',
  'Filtrer le registre',
  'Ouvrir la révision',
  'Tous',
  'Nouveaux',
  'File du jour',
  'Registre des mots',
  'Ouverture du registre',
  'Quitter la révision',
  'Progression de la révision',
  'Ouverture du paquet…',
  'Revenir au registre',
  'Les formes irrégulières',
  'L’exercice se prépare.',
  'les mots du jour',
  'Retrouvé',
  'Placé',
  'Triplé',
  'Édition triplée',
  'à revoir',
];

test('an A1 English learner reads the Lexique chrome in English', () => {
  const language = chromeLanguage('en', 'A1.1');
  assert.equal(language, 'en');
  const html = renderLexique({ language: 'en', level: 'A1.1' });
  const t = lexiqueCopy('en');
  for (const word of [
    t.search_placeholder, t.search_label, t.filter_group, t.chip_all, t.chip_due, t.chip_new, t.cta_open_review,
    t.queue_title, t.registre_title, t.count_loading, t.close_review, t.progress_aria, t.opening_deck,
    t.conj_close, t.conj_title, t.conj_loading, t.mdj_label, t.stamp_lu, t.stamp_retrouve, t.stamp_place,
    t.stamp_triple, t.mdj_open,
  ]) {
    assert.ok(html.includes(escapeHtml(word)), `missing English chrome: ${word}`);
  }
  for (const french of FRENCH_CHROME) {
    assert.ok(!html.includes(escapeHtml(french)), `French chrome leaked for an A1 learner: ${french}`);
  }
  assert.ok(html.includes('4 to review'));
  // Place names stay French: «Le lexique» is the screen's name, Grammaire /
  // Vocabulaire the Cahier's own tabs.
  assert.ok(html.includes('Le lexique'));
  assert.ok(html.includes('Grammaire'));
});

test('an A2 German learner reads it in German', () => {
  const language = chromeLanguage('de', 'A2');
  assert.equal(language, 'de');
  const html = renderLexique({ language: 'de', level: 'A2' });
  const t = lexiqueCopy('de');
  for (const word of [t.search_placeholder, t.chip_all, t.cta_open_review, t.queue_title, t.close_review, t.conj_title, t.mdj_label, t.stamp_retrouve]) {
    assert.ok(html.includes(escapeHtml(word)), `missing German chrome: ${word}`);
  }
  for (const french of FRENCH_CHROME) {
    assert.ok(!html.includes(escapeHtml(french)), `French chrome leaked for an A2 learner: ${french}`);
  }
  for (const english of ['Search for a word', 'Open the review', 'Leave the review', 'Irregular forms']) {
    assert.ok(!html.includes(escapeHtml(english)), `English chrome leaked for a German learner: ${english}`);
  }
});

test('a B1 learner reads the Lexique chrome in French, whatever their own language', () => {
  for (const control of ['en', 'de', 'fr']) {
    const language = chromeLanguage(control, 'B1.1');
    assert.equal(language, 'fr');
    const html = renderLexique({ language: control, level: 'B1.1' });
    // «Édition triplée» only shows when every word of the slate is tripled.
    for (const french of FRENCH_CHROME.filter((word) => word !== 'à revoir' && word !== 'Édition triplée')) {
      assert.ok(html.includes(escapeHtml(french)), `B1 (${control}) is missing French chrome: ${french}`);
    }
    assert.ok(html.includes('4 à revoir'));
    for (const foreign of ['Search for a word', 'Open the review', 'Wort suchen', 'Wiederholung öffnen', 'words of the day']) {
      assert.ok(!html.includes(escapeHtml(foreign)), `non-French chrome leaked for a B1 learner: ${foreign}`);
    }
  }
});

test('the French words stay French for every learner', () => {
  for (const nextLearner of [{ language: 'en', level: 'A1.1' }, { language: 'de', level: 'A2' }, { language: 'en', level: 'B2' }]) {
    const html = renderLexique(nextLearner);
    assert.ok(html.includes('réapprovisionnement'), 'a French word was translated');
    assert.ok(html.includes('la boulangerie'), 'a French word was translated');
    assert.ok(html.includes('lang="fr"'), 'the French word is not marked as French');
    // The gloss is the server's, already in the learner's language: kept as sent.
    assert.ok(html.includes('the bakery'));
  }
});

test('the three Lexique copy tables are complete and never empty', () => {
  const fr = lexiqueCopy('fr');
  const keys = Object.keys(fr).sort();
  for (const language of ['en', 'de', 'fr']) {
    const table = lexiqueCopy(language);
    assert.deepEqual(Object.keys(table).sort(), keys, `${language} table keys differ`);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(typeof value === 'string' && value.trim().length > 0, `${language}.${key} is empty`);
      // Sentence case, no shouted labels (design rule: no tracked caps).
      assert.ok(!/^[^a-zà-ÿ]*[A-ZÀ-Ý]{3}[^a-zà-ÿ]*$/.test(value), `${language}.${key} is all caps`);
      // A placeholder is the same in every language.
      const placeholders = (text) => (text.match(/\{\w+\}/g) || []).sort().join();
      assert.equal(placeholders(value), placeholders(fr[key]), `${language}.${key} placeholders differ`);
    }
    // Every whitelisted part of speech has a label.
    for (const raw of Object.keys(PART_OF_SPEECH_LABELS)) {
      assert.ok(partOfSpeechLabel(table, raw), `${language} has no label for ${raw}`);
    }
    assert.equal(partOfSpeechLabel(table, 'x'), '');
  }
  assert.equal(lexiqueCopy('de-AT').chip_all, 'Alle');
  assert.equal(lexiqueCopy(null).chip_all, 'All');
  assert.equal(partOfSpeechLabel(lexiqueCopy('fr'), 'Noun'), 'nom');
  assert.equal(nextReviewText(lexiqueCopy('en'), null), 'Review saved');
  assert.equal(nextReviewText(lexiqueCopy('fr'), '2026-10-03T08:00:00Z'), 'Reprise le 3 octobre');
});

test('Appendix A «Mots»: the due count is said once, on the one primary', () => {
  const summary = { due: 7, due_total: 7, fragile: 2, new: 3 };
  const expected = { en: 'Review · 7 words', de: 'Wiederholen · 7 Wörter', fr: 'Réviser · 7 mots' };
  for (const [language, cta] of Object.entries(expected)) {
    const counts = landingCounts(lexiqueCopy(language), summary);
    assert.equal(counts.cta, cta);
    assert.equal(counts.due, 7);
    // The masthead names the other piles and never the due count.
    assert.ok(!/\b7\b/.test(counts.countLine), `${language} count line repeats the due count: ${counts.countLine}`);
    assert.equal(`${counts.countLine} ${counts.cta}`.match(/\b7\b/g).length, 1);
  }
  assert.equal(landingCounts(lexiqueCopy('en'), { due: 1 }).cta, 'Review · 1 word');
  assert.equal(landingCounts(lexiqueCopy('en'), { due: 0 }).cta, 'Open the review');
  assert.equal(landingCounts(lexiqueCopy('fr'), { fragile: 2, new: 1 }).countLine, '2 fragiles · 1 nouveau');

  // The page prints the count through that helper only: the pills carry no
  // counts, and neither the queue head nor the live line counts cards.
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/vocabulary.tsx'), 'utf8');
  assert.ok(page.includes('const { countLine, cta } = landingCounts(t, summary, loading);'));
  assert.ok(!page.includes('lx-chip__n'));
  assert.ok(!page.includes('summary?.due'));
  assert.ok(!/todayItems\.length === 1 \? /.test(page));
  assert.ok(page.includes('<LxSectionHead title={t.queue_title} />'));
});

test('each Lexique page takes its chrome language from the rule, and prints no inline French chrome', () => {
  const pages = {
    'pages/vocabulary.tsx': ['<AtelierV2Root as="div" language={language}', '<AtelierV2Root as="main" language={language}'],
    'pages/vocabulary/review.tsx': ['<AtelierV2Root as="main" language={language}'],
    'pages/vocabulary/conjugation.tsx': ['<AtelierV2Root as="main" language={language}'],
  };
  for (const [file, roots] of Object.entries(pages)) {
    const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
    assert.equal(source.split('useChromeLanguage()').length - 1, 1, `${file} must compute the chrome language once`);
    assert.ok(source.includes('const t = lexiqueCopy(language);'), file);
    for (const root of roots) assert.ok(source.includes(root), `${file}: ${root}`);
    // Only what a learner could see: comments may still name a removed string.
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n')
      .filter((line) => !line.trim().startsWith('//'))
      .join('\n');
    for (const literal of [
      "'Réessayer'", "'Encore'", '>Encore<', 'Je sais', "'Bien'", "'Facile'", "'À revoir'", 'Touche pour retourner',
      'Chercher un mot', 'Ouverture du paquet', 'Paquet vidé', 'Actualiser', 'Écouter', 'Voir le tableau',
      'Les formes irrégulières', 'La biographie du mot', 'Registre des mots', "toLocaleDateString('fr-FR'",
      "NumberFormat('fr-FR'", 'Noter :', 'Révéler la réponse', 'Mot du jour',
    ]) {
      assert.ok(!code.includes(literal), `inline French chrome left in ${file}: ${literal}`);
    }
  }
  const mots = fs.readFileSync(path.join(WEB_ROOT, 'components/lexique/MotsDuJour.tsx'), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '');
  assert.ok(mots.includes('language={chromeLanguage}'));
  for (const literal of ["'Lu'", "'Retrouvé'", "'Placé'", '>Triplé<', 'Édition triplée', 'à revoir', 'sur 3']) {
    assert.ok(!mots.includes(literal), `inline French chrome left in MotsDuJour: ${literal}`);
  }
});

test('WP-83: the Lexique pages keep 320px, the tap floor and the theme tokens', () => {
  for (const file of ['pages/vocabulary.tsx', 'pages/vocabulary/review.tsx', 'pages/vocabulary/conjugation.tsx', 'components/lexique/MotsDuJour.tsx']) {
    const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
    // Dark theme parity: colours only through the av2 / app tokens.
    assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(source.replace(/href=\{?`?[^\s>]*#/g, '')), `${file} hard-codes a colour`);
    assert.ok(!/\brgba?\(/.test(source), `${file} hard-codes a colour`);
    // No tracked, shouted labels.
    assert.ok(!/text-transform:\s*uppercase/.test(source), `${file} shouts a label`);
    assert.ok(!/letter-spacing:\s*0\.\d/.test(source), `${file} tracks a label`);
  }
  const registre = fs.readFileSync(path.join(WEB_ROOT, 'pages/vocabulary.tsx'), 'utf8');
  // The filter pills wrap instead of scrolling the 320px screen sideways.
  assert.ok(registre.includes('.av2 .lx-chips { display: flex; flex-wrap: wrap;'));
  assert.ok(!registre.includes('overflow-x: auto'));
  // The 32px clear disc has a 44px target around it.
  assert.ok(registre.includes('.av2 .lx-search__clear::after'));
  // One Garamond headline: the weekly dossier's title is set in sans.
  assert.ok(registre.includes('<h2 className="lx-dossier__title">'));
  assert.equal((registre.match(/className="av2-headline av2-headline--/g) || []).length, 1);
  // Long French words break inside the card instead of widening the page.
  const review = fs.readFileSync(path.join(WEB_ROOT, 'pages/vocabulary/review.tsx'), 'utf8');
  assert.ok(/\.av2 \.lx-card__word \{[^}]*overflow-wrap: anywhere;/.test(review));
  assert.ok(review.includes('padding-bottom: calc(14px + var(--av2-safe-bottom))'));
  assert.ok(registre.includes('padding: 0 0 calc(24px + var(--av2-safe-bottom));'));
});
