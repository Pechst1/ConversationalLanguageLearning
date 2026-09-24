// node --test components/feuilleton/feuilleton-language.test.js
//
// WP-82 — the Feuilleton tab follows the one language rule.
//
//   1. the copy table is complete in en / de / fr and every column fills the
//      same placeholders;
//   2. an A1 English learner reads the season page's chrome in English, an A2
//      German learner in German, a B1 learner (whatever their language) in
//      French — and the story (titles, briefs, threads) stays French;
//   3. the pages wire it: `useChromeLanguage()` once, handed to AtelierV2Root
//      and to the readers, and none of the old French chrome is left inline;
//   4. the server's «why» note is re-picked in the chrome language.

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
  if (request === 'next/link') {
    return originalResolve.call(this, path.join(__dirname, 'reader/__fixtures__/next-link-stub.js'), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
global.React = React;

const { feuilletonCopy, fbFill, fbPlural } = require('./feuilleton-copy.ts');
const { SeasonPage } = require('./season/SeasonPage.tsx');
const model = require('./season/season-model.ts');
const { chromeLanguage, pickByLanguage } = require('@/lib/language-rule.ts');

const read = (rel) => fs.readFileSync(path.join(WEB_ROOT, rel), 'utf8');
const decode = (s) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"');

const SEASON = {
  thread_id: 't1',
  season_number: 1,
  chapter: { number: 2, title_fr: 'Les voisins' },
  today: {
    scene_id: 's9', number: 4, title_fr: 'La clé perdue', brief_fr: 'Lila cherche sa clé.',
    image_url: null, character: 'Lila', location: '', status: 'available',
  },
  commitments: [{ id: 'c1', text_fr: 'Rendre le livre à Gus.' }],
  threads: [{ key: 'k', text_fr: 'Qui a pris la clé ?', state: 'developing' }],
  read_episodes: [
    { scene_id: 's1', number: 3, title_fr: 'Le marché', brief_fr: '', image_url: null, character: 'Lila', location: 'le marché', status: 'completed' },
  ],
};

const LEARNERS = [
  { who: 'A1 English', language: chromeLanguage('en', 'A1'), expect: 'en', headline: 'The season so far', button: 'Open the session', episode: 'Episode 3', meta: 'with Lila' },
  { who: 'A2 German', language: chromeLanguage('de', 'A2'), expect: 'de', headline: 'Die Staffel bisher', button: 'Sitzung öffnen', episode: 'Folge 3', meta: 'mit Lila' },
  { who: 'B1 German', language: chromeLanguage('de', 'B1'), expect: 'fr', headline: 'La saison jusqu’ici', button: 'Ouvrir la séance', episode: 'Épisode 3', meta: 'avec Lila' },
];

test('the copy table is complete and every column fills the same placeholders', () => {
  const fr = feuilletonCopy('fr');
  const keys = Object.keys(fr);
  const holes = (text) => (text.match(/\{\w+\}/g) || []).sort().join(',');
  for (const lang of ['en', 'de']) {
    const table = feuilletonCopy(lang);
    assert.deepEqual(Object.keys(table).sort(), [...keys].sort(), `${lang} keys`);
    for (const key of keys) {
      assert.ok(String(table[key]).trim(), `${lang}.${key} is empty`);
      assert.equal(holes(table[key]), holes(fr[key]), `${lang}.${key} placeholders`);
    }
  }
  // Place names are French in every column.
  for (const lang of ['en', 'de', 'fr']) assert.equal(feuilletonCopy(lang).feuilleton, 'Le Feuilleton');
  // No language (a caller predating the rule) keeps French.
  assert.equal(feuilletonCopy().retry, 'Réessayer');
  assert.equal(fbPlural(feuilletonCopy('en'), 'credit', 1), 'One word from this episode joins your review.');
  assert.equal(fbPlural(feuilletonCopy('de'), 'season_count', 2, { season: 1 }), 'Staffel 1 · 2 Folgen erschienen');
  assert.equal(fbFill('{a}-{b}', { a: 1 }), '1-{b}');
});

for (const learner of LEARNERS) {
  test(`${learner.who}: the season page's chrome is ${learner.expect}, the story stays French`, () => {
    assert.equal(learner.language, learner.expect);
    const html = decode(renderToStaticMarkup(
      React.createElement(SeasonPage, { season: SEASON, language: learner.language, onOpenSeance: () => {} }),
    ));
    assert.ok(html.includes(learner.headline), html.slice(0, 300));
    assert.ok(html.includes(learner.button));
    assert.ok(html.includes(learner.episode));
    assert.ok(html.includes(learner.meta));
    // story content — French and marked so
    for (const fr of ['La clé perdue', 'Lila cherche sa clé.', 'Rendre le livre à Gus.', 'Qui a pris la clé ?', 'Le marché']) {
      assert.ok(html.includes(fr), `${fr} missing`);
    }
    assert.match(html, /lang="fr"[^>]*>La clé perdue/);
    if (learner.expect !== 'fr') {
      for (const chrome of ['La saison jusqu’ici', 'Ouvrir la séance', 'Engagement en cours', 'ça bouge', 'Épisode 3']) {
        assert.ok(!html.includes(chrome), `${learner.who} still reads «${chrome}»`);
      }
    }
    assert.equal(
      model.seasonTodayLabel(SEASON.today, learner.language),
      fbFill(feuilletonCopy(learner.language).season_today, { n: 4 }),
    );
  });
}

test('the season labels keep French when no language is given (legacy callers)', () => {
  assert.equal(model.seasonThreadLabel('closed'), 'réglé');
  assert.equal(model.seasonThreadLabel('closed', 'en'), 'settled');
  assert.equal(model.seasonStoryLabel(SEASON, 'de'), 'Staffel 1 · Kapitel 2 · Les voisins');
});

test('the Feuilleton pages resolve the chrome language once and hand it on', () => {
  const pages = {
    'pages/graphic-novel.tsx': read('pages/graphic-novel.tsx'),
    'pages/serial/index.tsx': read('pages/serial/index.tsx'),
    'pages/serial/cast.tsx': read('pages/serial/cast.tsx'),
    'pages/serial/episode/[index].tsx': read('pages/serial/episode/[index].tsx'),
  };
  const stripComments = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  for (const [name, source] of Object.entries(pages)) {
    assert.equal((stripComments(source).match(/useChromeLanguage\(\)/g) || []).length, 1, `${name} resolves the language once`);
    assert.ok(source.includes('language={language}'), `${name} hands the language to AtelierV2Root`);
  }
  const gn = pages['pages/graphic-novel.tsx'];
  // both readers get the chrome language
  assert.match(gn, /<StoryEpisodeReader[\s\S]*?language=\{language\}/);
  assert.match(gn, /<FeuilletonReader[\s\S]*?language=\{language\}/);
  assert.ok(gn.includes('<SeasonPage season={season} language={language}'));
  // the «why» note is re-picked from the server's three versions
  assert.ok(gn.includes('task.recommendation_reason?.text_by_language'));

  const oldChrome = [
    'Retour à l’Atelier', 'Retour à La Une', 'Réessayer', 'Chargement de la saison', 'Terminer l’épisode',
    'Composer la première scène', 'Feuilleton terminé.', 'Écouter l’épisode', 'Rester en POV',
    'Proximité', 'Les archives n’ont pas répondu.', 'Private model sheet', 'Avis de la rédaction',
  ];
  for (const [name, source] of Object.entries(pages)) {
    const code = stripComments(source);
    for (const phrase of oldChrome) {
      assert.ok(!code.includes(phrase), `${name} still prints «${phrase}» inline`);
    }
  }
});

test('the server’s «why» note is re-picked in the chrome language', () => {
  const reason = {
    text: 'Choisie pour vérifier le point de langue de cette planche.',
    text_by_language: {
      fr: 'Choisie pour vérifier le point de langue de cette planche.',
      en: 'Chosen to check this page’s language point.',
      de: 'Ausgewählt, um den Sprachpunkt dieser Seite zu prüfen.',
    },
  };
  assert.equal(pickByLanguage(reason.text_by_language, chromeLanguage('en', 'A1'), reason.text), reason.text_by_language.en);
  assert.equal(pickByLanguage(reason.text_by_language, chromeLanguage('de', 'A2'), reason.text), reason.text_by_language.de);
  assert.equal(pickByLanguage(reason.text_by_language, chromeLanguage('en', 'B1'), reason.text), reason.text_by_language.fr);
  assert.equal(pickByLanguage(undefined, 'en', reason.text), reason.text);
});
