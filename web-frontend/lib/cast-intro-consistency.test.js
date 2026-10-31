// node --test lib/cast-intro-consistency.test.js
//
// #107, #124, #155: who the learner is introduced to, who greets them in the
// sign-up teaser, and the name and face a reaction line uses all come from the
// one cast. These tests tie the surfaces together so they cannot drift apart.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const taste = require('./onboarding-taste.ts');
const faces = require('./cast-faces.ts');
const { speakerOf, journeySpeaker, drillSpeaker } = require('../components/atelier-v2/journey/journey-faces.ts');

const intro = JSON.parse(
  fs.readFileSync(path.join(WEB_ROOT, '..', 'app', 'data', 'season', 's1', 'intro.json'), 'utf8'),
);
const introIds = intro.cast.map((row) => row.character_id);

test('the teaser speaker is in the cast intro shown after sign-up', () => {
  for (const item of taste.TASTE_ITEMS) {
    for (const line of [item.line, item.reply]) {
      assert.ok(introIds.includes(line.characterId), `${line.speaker} is not in the cast intro`);
      assert.equal(faces.castIdFor(line.characterId, line.speaker), line.characterId);
    }
  }
});

test('the teaser closing line names only people from the cast intro', () => {
  const names = new Set(intro.cast.map((row) => row.name));
  assert.deepEqual([...taste.CAST_INTRO_NAMES].sort(), [...names].sort());
  const known = ['Margaux', 'Gus', 'Marin', 'Lila', 'Camille', 'Romy', 'Odile'];
  for (const [lang, copy] of Object.entries(taste.TASTE_COPY)) {
    for (const name of known.filter((n) => copy.closing.includes(n))) {
      assert.ok(names.has(name), `${lang} closing names ${name}, who is not in the cast intro`);
    }
  }
});

test('Camille Marchand is in the cast intro, with a portrait of her own', () => {
  const camille = intro.cast.find((row) => row.character_id === 'camille_marchand');
  assert.ok(camille, 'Camille is introduced');
  for (const lang of ['en', 'de', 'fr']) {
    assert.ok(camille.role_native[lang] && camille.line_native[lang]);
  }
  assert.equal(faces.drawnCastIdFor('camille_marchand', 'Camille'), 'camille_marchand');
});

test('a reaction line and its face come from one entry: same id, one short name', () => {
  const full = { id: 'augustin_de_roncourt', name: 'Augustin « Gus » de Roncourt' };
  assert.deepEqual(speakerOf(full.id, full.name), { id: 'augustin_de_roncourt', name: 'Gus' });
  assert.deepEqual(speakerOf('stranger', 'Mme Diallo'), { id: 'stranger', name: 'Mme Diallo' });
  const journey = { scenario: { character_id: full.id, character_name: full.name } };
  assert.equal(journeySpeaker(journey).name, 'Gus');
  // A grammar drill is asked, and answered, by the rule card's coach, not the scene's character.
  const steps = [
    { kind: 'rule', prompt: { concept_id: 4, rule_card: { speaker: 'marin_leveque' } } },
    { kind: 'recall', prompt: { target: { kind: 'grammar', id: 4 } } },
  ];
  const asker = drillSpeaker({ ...journey, steps }, steps[1]);
  assert.deepEqual(asker, { id: 'marin_leveque', name: 'Marin' });
  assert.equal(faces.castIdFor(asker.id, asker.name), 'marin_leveque');
});

test('the journey hands the verdict the drill asker, not the scene character', () => {
  const source = fs.readFileSync(
    path.join(WEB_ROOT, 'components/atelier-v2/journey/JourneySession.tsx'),
    'utf8',
  );
  assert.match(source, /speaker=\{step\?\.kind === 'recall' && asker \? asker : speaker\}/);
});

test('#155: a drill cut from a line of the scene is asked by, and smiles as, that line’s speaker', () => {
  // Day of Gus; the recall item rebuilds Marin's line, and the server says so.
  const journey = {
    scenario: { character_id: 'augustin_de_roncourt', character_name: 'Augustin « Gus » de Roncourt' },
    steps: [{ kind: 'rule', prompt: { concept_id: 4, rule_card: { speaker: 'lila_bonnet' } } }],
  };
  const fromMarin = {
    kind: 'recall',
    prompt: {
      task_type: 'short_answer',
      source_fr: '…Vous allez vraiment … l’appartement d’Odile ?',
      target: { kind: 'grammar', id: 4 },
      speaker: { id: 'marin_leveque', name: 'Marin' },
    },
  };
  const asker = drillSpeaker(journey, fromMarin);
  assert.deepEqual(asker, { id: 'marin_leveque', name: 'Marin' }, 'the line’s speaker, before the rule’s coach and the day');
  assert.equal(faces.castIdFor(asker.id, asker.name), 'marin_leveque', 'the face is the one the name says');
  // A payload with the world bible's full name still reads the cast's short name.
  const full = { ...fromMarin, prompt: { ...fromMarin.prompt, speaker: { id: 'augustin_de_roncourt', name: 'Augustin « Gus » de Roncourt' } } };
  assert.deepEqual(drillSpeaker(journey, full), { id: 'augustin_de_roncourt', name: 'Gus' });
  // Without a line speaker the old order holds: the rule's coach, then the day's character.
  const plain = { ...fromMarin, prompt: { ...fromMarin.prompt, speaker: undefined } };
  assert.deepEqual(drillSpeaker(journey, plain), { id: 'lila_bonnet', name: 'Lila' });
  const word = { kind: 'recall', prompt: { task_type: 'choice', target: { kind: 'vocabulary', id: 9 } } };
  assert.deepEqual(drillSpeaker(journey, word), { id: 'augustin_de_roncourt', name: 'Gus' });
});

test('#155: the cheer under a right answer names the face beside the drill', () => {
  require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
  const apiPath = Module._resolveFilename('@/services/api', module, false);
  require.cache[apiPath] = require.cache[apiPath] || {
    id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} },
  };
  const { smileLine } = require('../components/atelier-v2/journey/ReplyStage.tsx');
  const asker = drillSpeaker(
    { scenario: { character_id: 'augustin_de_roncourt', character_name: 'Gus' }, steps: [] },
    { kind: 'recall', prompt: { task_type: 'unscramble', target: { kind: 'vocabulary', id: 1 }, speaker: { id: 'marin_leveque', name: 'Marin' } } },
  );
  assert.equal(smileLine(asker.name, 'fr'), 'Marin te sourit');
  assert.equal(smileLine(asker.name, 'en'), 'Marin smiles at you');
});
