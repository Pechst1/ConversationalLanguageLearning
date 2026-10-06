// node --test components/courrier/courrier-one-language.test.js
//
// 2026-09-24 — the one-language rule reaches the intake task card, the letter
// headline fallback and the placement's evidence note:
//
//   * A1 English / A2 German: the task's label, instruction and success line,
//     the document type and a fallback counterpart are said in the learner's
//     language; the counterpart the document names stays French;
//   * B1: all of it is French;
//   * «Une lettre du Courrier.» is chrome; a real headline is French content;
//   * the grader's note is shown in the learner's language when it was
//     written in it, else its French, marked `lang="fr"`.

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

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { CrArtefactTaskCard, crArtefactChrome, crArtefactLabel } = require('./Courrier.tsx');
const { CrCorrespondent } = require('./Correspondance.tsx');
const { courrierCopy, crLetterHeadline } = require('./courrier-copy.ts');
const { AtelierV2Root } = require('@/components/atelier-v2/ui/AtelierV2Root.tsx');
const { chromeLanguage } = require('@/lib/language-rule.ts');
const { placementEvidenceNote } = require('@/lib/placement-copy.ts');

const h = React.createElement;
const decode = (s) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"');
const render = (language, element) => decode(renderToStaticMarkup(h(AtelierV2Root, { language }, element)));

const TASK = {
  kind: 'decide',
  kind_label_fr: 'Choisir',
  kind_label_by_language: { fr: 'Choisir', en: 'Choose', de: 'Auswählen' },
  instruction_fr: 'Commandez votre formule du midi auprès du serveur.',
  instruction_by_language: {
    fr: 'Commandez votre formule du midi auprès du serveur.',
    en: 'Order your lunch menu from the waiter.',
  },
  success_fr: 'Le serveur sait ce que vous prenez.',
  success_by_language: { fr: 'Le serveur sait ce que vous prenez.' },
  counterpart_fr: 'le serveur',
};
const ARTEFACT = {
  id: 'a1',
  status: 'read',
  artefact: {
    type: 'menu',
    type_label_fr: 'Un menu',
    type_label_by_language: { fr: 'Un menu', en: 'A menu', de: 'Eine Speisekarte' },
  },
  task: TASK,
};

test('an A1 English learner reads the task card in English, the counterpart in French', () => {
  const lang = chromeLanguage('en', 'A1.1');
  const html = render(lang, h(CrArtefactTaskCard, { task: TASK }));
  assert.match(html, /<span lang="en">Choose<\/span>/);
  assert.match(html, /lang="en">Order your lunch menu from the waiter\.</);
  assert.match(html, /<span lang="fr"> · le serveur<\/span>/);
  // No English success line was written: the French one, marked so.
  assert.match(html, /lang="fr">Le serveur sait ce que vous prenez\.</);
  assert.ok(!html.includes('>Choisir<'));
  assert.equal(crArtefactLabel(ARTEFACT, lang), 'A menu · le serveur');
});

test('an A2 German learner reads the labels in German and the fallback counterpart as chrome', () => {
  const lang = chromeLanguage('de', 'A2');
  const said = crArtefactChrome(
    {
      ...ARTEFACT,
      task: {
        ...TASK,
        counterpart_fr: 'votre correspondant',
        counterpart_by_language: { fr: 'votre correspondant', en: 'your correspondent', de: 'dein Gegenüber' },
      },
    },
    lang,
  );
  assert.deepEqual(said.kind, { text: 'Auswählen', lang: 'de' });
  assert.deepEqual(said.type, { text: 'Eine Speisekarte', lang: 'de' });
  assert.deepEqual(said.who, { text: 'dein Gegenüber', lang: 'de' });
  // No German instruction: the French one, labelled French.
  assert.equal(said.instruction.lang, 'fr');
  // An older payload with no label table still says the kind in German.
  const older = crArtefactChrome({ task: { kind: 'ask', instruction_fr: 'Posez la question.' } }, lang);
  assert.deepEqual(older.kind, { text: 'Nachfragen', lang: 'de' });
});

test('a B1 learner reads all of it in French', () => {
  const lang = chromeLanguage('en', 'B1.1');
  assert.equal(lang, 'fr');
  const html = render(lang, h(CrArtefactTaskCard, { task: TASK }));
  assert.match(html, /<span lang="fr">Choisir<\/span>/);
  assert.match(html, /lang="fr">Commandez votre formule/);
  assert.equal(crArtefactLabel(ARTEFACT, lang), 'Un menu · le serveur');
});

test('the letter headline fallback is chrome; a real headline stays French', () => {
  assert.deepEqual(crLetterHeadline({ summary_fr: 'Une lettre du Courrier.' }, 'en'), {
    text: 'A letter from Le Courrier.',
    lang: 'en',
  });
  assert.deepEqual(
    crLetterHeadline(
      { summary_fr: 'Une lettre du Courrier.', summary_by_language: { de: 'Ein Brief aus Le Courrier.' } },
      'de',
    ),
    { text: 'Ein Brief aus Le Courrier.', lang: 'de' },
  );
  assert.deepEqual(crLetterHeadline({ summary_fr: 'Une lettre du Courrier.' }, 'fr'), {
    text: 'Une lettre du Courrier.',
    lang: 'fr',
  });
  assert.deepEqual(crLetterHeadline({ summary_fr: 'Le radiateur' }, 'en'), { text: 'Le radiateur', lang: 'fr' });
  for (const language of ['en', 'de', 'fr']) assert.ok(courrierCopy(language).letter_fallback.trim());

  const html = render(
    'en',
    h(CrCorrespondent, {
      correspondent: { id: 's', name: 'Samira', role: 'boulangère' },
      history: [
        { mission_id: 'm1', summary_fr: 'Une lettre du Courrier.', outcome: 'kept' },
        { mission_id: 'm2', summary_fr: 'Le pain de samedi', outcome: 'kept' },
      ],
    }),
  );
  assert.match(html, /lang="en">A letter from Le Courrier\.</);
  assert.match(html, /lang="fr">Le pain de samedi</);
  assert.ok(!html.includes('Une lettre du Courrier.'));
});

test('the placement note is said in the learner language when the grader wrote it', () => {
  const item = {
    evidence_fr: 'phrase complète : « je voudrais un café »',
    evidence_native: 'A complete sentence: « je voudrais un café »',
    evidence_language: 'en',
  };
  assert.deepEqual(placementEvidenceNote(item, 'en'), {
    text: 'A complete sentence: « je voudrais un café »',
    lang: 'en',
  });
  // A German reader of an English note, or an older note: the French, marked so.
  assert.equal(placementEvidenceNote(item, 'de').lang, 'fr');
  assert.equal(placementEvidenceNote({ evidence_fr: 'réponse complète' }, 'fr').text, 'réponse complète');
  assert.equal(placementEvidenceNote({}, 'en'), null);
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/placement.tsx'), 'utf8');
  assert.ok(page.includes('placementEvidenceNote(item, language)'));
});
