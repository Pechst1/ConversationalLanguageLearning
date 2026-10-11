// node --test components/stories/bibliotheque-copy.test.js
//
// WP-82 — La Bibliothèque (shelf, text, chapter session, chapter-end sheet,
// book import) and the La Une press components follow the one-language rule:
// the learner's language up to A2, French from B1. Texts, chapters and the
// conversation stay content.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { BIBLIOTHEQUE_COPY, bibliothequeCopy, fill } = require('./bibliotheque-copy.ts');
const { LAUNE_COPY, launeCopy } = require('../laune/laune-copy.ts');
const { chromeLanguage } = require('../../lib/language-rule.ts');

const read = (relative) => fs.readFileSync(path.join(WEB_ROOT, relative), 'utf8');
const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');

for (const [name, tables] of [['bibliotheque', BIBLIOTHEQUE_COPY], ['laune', LAUNE_COPY]]) {
  test(`${name}: en/de/fr are complete, with the same keys and placeholders`, () => {
    const fr = tables.fr;
    for (const language of ['en', 'de']) {
      const table = tables[language];
      assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
      for (const [key, value] of Object.entries(table)) {
        assert.equal(typeof value, 'string', `${language}.${key}`);
        assert.ok(value.trim(), `${language}.${key} is empty`);
        assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
      }
    }
  });
}

test('A1 reads English, A2 German, B1 French', () => {
  assert.equal(chromeLanguage('en', 'A1'), 'en');
  assert.equal(chromeLanguage('de', 'A2'), 'de');
  assert.equal(chromeLanguage('en', 'B1'), 'fr');
  assert.equal(bibliothequeCopy(chromeLanguage('en', 'A1')).retry, 'Try again');
  assert.equal(bibliothequeCopy(chromeLanguage('de', 'A2')).retry, 'Erneut versuchen');
  assert.equal(bibliothequeCopy(chromeLanguage('en', 'B1')).retry, 'Réessayer');
  assert.equal(launeCopy(chromeLanguage('en', 'A1')).retry, 'Try again');
  assert.equal(launeCopy(chromeLanguage('de', 'A2')).continue, 'Weiter');
  assert.equal(launeCopy(chromeLanguage('de', 'B2')).continue, 'Continuer');
  assert.equal(
    fill(bibliothequeCopy('de').reach_goals_many, { n: 2 }),
    'Erreichen Sie mindestens 2 Ziele, um es abzuschließen.',
  );
  assert.equal(fill(bibliothequeCopy('fr').shelf_count_many, { n: 3 }), '3 textes sur l’étagère');
});

test('the French tables keep the shipped wording', () => {
  const fr = BIBLIOTHEQUE_COPY.fr;
  assert.equal(fr.shelf_empty_title, 'L’étagère est encore vide.');
  assert.equal(fr.shelf_empty_action, 'Importer un premier livre');
  assert.equal(fr.text_opening, 'Ouverture du texte…');
  assert.equal(fr.chapter_opening, 'Ouverture du chapitre…');
  assert.equal(fr.goals_missing, 'Encore quelques objectifs à atteindre');
  assert.ok(fr.reach_goals_many.startsWith('Atteignez au moins'));
  assert.equal(LAUNE_COPY.fr.retry, 'Réessayer');
  assert.equal(LAUNE_COPY.fr.adjust_time, 'Ajuster le temps de l’édition');
});

const SURFACES = {
  'pages/bibliotheque.tsx': [
    'Ouverture de la bibliothèque…', 'Importer un livre', 'Réessayer', 'L’étagère est encore vide.',
    'Reprendre la lecture', 'Commencer la lecture', "'Verrouillé'", '"Verrouillé"', 'Sur l’étagère', 'En cours :',
  ],
  'pages/bibliotheque/[storyId].tsx': [
    'Retour à la bibliothèque', 'Ouverture du texte…', 'Ce texte est introuvable.', 'À propos de ce texte',
    '>Les chapitres<', 'Tous les chapitres sont lus.', 'Retour à l’étagère', 'Ouverture…',
  ],
  'pages/bibliotheque/[storyId]/chapter/[chapterId].tsx': [
    'Ouverture du chapitre…', 'Ouverture de la séance…', 'Ce chapitre est introuvable.', 'Retour au texte',
    'La séance n’a pas pu s’ouvrir.',
  ],
  'components/stories/ChapterCompletionModal.tsx': [
    'Texte terminé', 'Chapitre sans faute', 'XP gagnés', 'Distinctions débloquées', 'Chapitre suivant',
    'Voir le récapitulatif', 'Continuer', 'Revenir au texte',
  ],
  'components/stories/ChapterProgressCard.tsx': [
    'Progression dans le chapitre', 'Objectifs atteints', 'Mots employés', 'Terminer le chapitre',
    'Encore quelques objectifs à atteindre', 'Atteignez au moins', 'Clôture…',
  ],
  'components/stories/StorySessionLayout.tsx': [
    'Quitter le chapitre', 'À reprendre', 'Rien à reprendre.', 'En train d’écrire…', 'Mots suggérés',
    'Votre réponse, en français', 'Écrivez en français…', '"Envoyer"', 'En liaison', 'Liaison en cours…',
  ],
  'components/story/UploadBookModal.tsx': [
    'Choisissez d’abord un fichier.', 'Envoi en cours…', 'Déposez un fichier ici', 'Titre (facultatif)',
    'Auteur (facultatif)', 'Niveaux visés', 'par ex.', 'Importer le livre', 'Annuler', 'Traitement du livre',
  ],
  'components/laune/LaUne.tsx': [
    '>Réessayer<', 'Continuer <IcoArrow', 'Ajuster le temps de l’édition', 'Plus long que les',
    'À vous d’écrire', 'Sous presses', 'Illustration retardée', 'jours de suite', 'lecture du soir',
    "'Lire l’épisode — '",
  ],
};

test('each surface reads its chrome from the copy table, never inline French', () => {
  for (const [relative, phrases] of Object.entries(SURFACES)) {
    const source = read(relative);
    assert.ok(source.includes('useChromeLanguage('), `${relative} resolves the chrome language`);
    assert.ok(/bibliothequeCopy\(|launeCopy\(/.test(source), `${relative} reads the copy table`);
    for (const phrase of phrases) {
      assert.ok(!source.includes(phrase), `${relative}: inline French chrome ${phrase}`);
    }
  }
});

test('texts and chapters stay content', () => {
  const detail = read('pages/bibliotheque/[storyId].tsx');
  assert.ok(detail.includes('{story.title}'));
  assert.ok(detail.includes('{story.description}'));
  const session = read('components/stories/StorySessionLayout.tsx');
  assert.ok(session.includes('{chapter.title}'));
  assert.ok(session.includes('{message.content}'));
});
