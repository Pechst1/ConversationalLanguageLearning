// node --test components/cahiers/cahier-copy.test.js
//
// WP-82 — Le Cahier (grammar index and fiche, the /notebook shell and its
// library, the journal, the legacy Cahiers kit, the word biography and the
// fragility chip) follows the one-language rule: its chrome is the learner's
// language up to A2 and French from B1. Content stays French.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { cahierCopy, countLabel, fill } = require('./cahier-copy.ts');
const { chromeLanguage } = require('../../lib/language-rule.ts');

const read = (relative) => fs.readFileSync(path.join(WEB_ROOT, relative), 'utf8');
const code = (relative) =>
  read(relative)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

const flat = (table, prefix = '') =>
  Object.entries(table).flatMap(([key, value]) =>
    typeof value === 'string' ? [[`${prefix}${key}`, value]] : flat(value, `${prefix}${key}.`),
  );
const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');

test('the three Cahier tables are complete and fill the same placeholders', () => {
  const fr = Object.fromEntries(flat(cahierCopy('fr')));
  assert.ok(Object.keys(fr).length > 200, 'the table covers the whole cluster');
  for (const language of ['en', 'de']) {
    const table = Object.fromEntries(flat(cahierCopy(language)));
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
    }
  }
  for (const [key, value] of Object.entries(fr)) assert.ok(value.trim(), `fr.${key} is empty`);
});

test('the learner level picks the table: A1 English, A2 German, B1 French', () => {
  assert.equal(chromeLanguage('en', 'A1'), 'en');
  assert.equal(chromeLanguage('de', 'A2'), 'de');
  assert.equal(chromeLanguage('en', 'B1'), 'fr');

  assert.equal(cahierCopy(chromeLanguage('en', 'A1')).grammar.chip_due, 'To review');
  assert.equal(cahierCopy(chromeLanguage('de', 'A2')).journal.send, 'Senden');
  assert.equal(cahierCopy(chromeLanguage('en', 'B1')).journal.send, 'Envoyer');
  assert.equal(cahierCopy('en-US').cahier.mode_grammar, 'Rules');
  assert.equal(cahierCopy(null).cahier.mode_grammar, 'Rules');
});

test('counts and placeholders read naturally in each language', () => {
  assert.equal(countLabel(cahierCopy('fr').grammar, 'sheets', 1), '1 fiche');
  assert.equal(countLabel(cahierCopy('fr').grammar, 'sheets', 3), '3 fiches');
  assert.equal(countLabel(cahierCopy('en').grammar, 'sheets_due', 2), '2 rule cards to review');
  assert.equal(countLabel(cahierCopy('de').cahier, 'concepts', 54), '54 Konzepte');
  assert.equal(fill(cahierCopy('en').journal.days_ago, { n: 3 }), '3 days ago');
  assert.equal(fill(cahierCopy('fr').journal.with, { name: 'Augustin' }), 'avec Augustin');
});

test('place names stay French in every column', () => {
  for (const language of ['en', 'de', 'fr']) {
    const t = cahierCopy(language);
    assert.equal(t.cahier.mode_releve, 'Relevé');
    assert.equal(t.library.lexique, 'Lexique');
    assert.equal(t.notebook.title_library, 'Le Cahier · Bibliothèque');
    assert.match(t.grammar.cta, /[Ll]’Atelier/, `${language}: L’Atelier`);
  }
});

test('the journal helpers speak the table they are given, French by default', () => {
  const { cueLine, recallLine, correctionLine } = require('./JournalTab.tsx');
  const entry = {
    cue: { character_name: 'Augustin', location_name: 'Le Mistral', days_ago: 1 },
    content_recall: { status: 'scored', matched: [1], facts_total: 3 },
    correction: { assessment_status: 'checked', errata: [{}, {}] },
  };
  assert.equal(cueLine(entry), 'Hier · Le Mistral · avec Augustin');
  assert.equal(cueLine(entry, cahierCopy('en').journal), 'Yesterday · Le Mistral · with Augustin');
  assert.equal(recallLine(entry, cahierCopy('de').journal), 'Sie haben 1 von 3 Details wiedergefunden.');
  assert.equal(correctionLine(entry), '2 choses à revoir.');
  assert.equal(correctionLine(entry, cahierCopy('en').journal), '2 things to review.');
});

test('the fragility chip restates the server’s French in the chrome language', () => {
  const { fragilityLabel } = require('../mobile/FragilityBadge.tsx');
  const server = { fragility_level: 'new', fragility_label: 'Nouveau', fragility_reason: 'Pas encore révisé par vous.' };
  assert.deepEqual(fragilityLabel(server), { level: 'new', label: 'Nouveau', reason: 'Pas encore révisé par vous.' });
  assert.deepEqual(fragilityLabel(server, new Date(), 'en'), {
    level: 'new',
    label: 'New',
    reason: 'You have not reviewed it yet.',
  });
  assert.equal(fragilityLabel(null, new Date(), 'de').label, 'Neu');
  assert.equal(fragilityLabel({ state: 'mastered', reps: 4 }, new Date(), 'fr').label, 'Tient');
  // An unknown level keeps the server's words rather than guessing.
  const odd = { fragility_level: 'mystery', fragility_label: 'Étrange', fragility_reason: null };
  assert.equal(fragilityLabel(odd, new Date(), 'en').label, 'Étrange');
});

test('each screen reads its chrome from the copy module, not from inline French', () => {
  const files = {
    'pages/grammar.tsx': [
      'Chercher une règle, un piège…',
      'Filtrer les règles',
      'Index des règles',
      'Le cahier s’ouvre à la première séance',
      'Aucune fiche ne correspond à ce filtre',
      'Exemples d’ancrage',
      'Pièges principaux',
      'Notes en marge',
      'Travailler cette règle à l’Atelier',
      'Prochaine révision',
      "'Réessayer'",
    ],
    'pages/notebook.tsx': [
      'Le Cahier · Le journal de bord',
      'Le feuilleton · classé au dossier',
      'Reprendre le feuilleton',
      'Retrouver la preuve',
      'Le passage fait foi',
      'Terminer l’épisode',
      'Écrivez votre réponse en français',
      'Consignes de l’épisode',
      '>\n            Vérifier',
    ],
    'components/cahiers/CahierV2.tsx': ["'Règles'", "'Mots'", 'Rubriques du cahier', 'Effacer les filtres', "'Filtrer'"],
    'components/cahiers/JournalTab.tsx': [
      'Rien à raconter aujourd’hui',
      'Le journal n’a pas pu être ouvert',
      'Ce dont vous vous souvenez',
      'La scène, telle qu’elle était',
      'Passer cette scène',
      'Relire la scène après l’envoi',
      "'Hier, en français'",
      'Tout voir',
    ],
    'components/cahiers/Cahiers.tsx': [
      "'Grammaire'",
      "'Vocabulaire'",
      'Progression indisponible',
      'Avis du bureau des archives',
      'Aucune note pour l’instant',
      'Effacer les filtres',
      "'À revoir'",
    ],
    'components/mobile/WordBiographySheet.tsx': [
      'Sans date',
      'Paquet importé',
      'Le fil du mot',
      'L’histoire est indisponible.',
      'État de la mémoire',
      'Ce mot n’a pas encore laissé de trace.',
    ],
    'components/mobile/FragilityBadge.tsx': ["'Mémoire fragile'", "'En formation'", 'Pas encore révisé'],
  };
  for (const [file, literals] of Object.entries(files)) {
    const source = code(file);
    assert.ok(source.includes('cahier-copy'), `${file} imports the copy module`);
    for (const literal of literals) assert.ok(!source.includes(literal), `${file}: inline chrome ${literal}`);
  }
  // The pages hand the chrome language to the root the Cahier primitives read.
  assert.ok(code('pages/notebook.tsx').includes('language={language}'));
  assert.ok(code('pages/grammar.tsx').includes('language={language}'));
  assert.ok(code('components/mobile/WordBiographySheet.tsx').includes('language={language}'));
});
