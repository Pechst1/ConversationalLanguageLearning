// node --test lib/forge-coach.test.js
//
// WP-S5 — every rule has a coach. The server puts the coach on the concept,
// on the forge's next item and rules, and on each observed answer
// (`correction.forge.coach_mood`). The rule card and the feedback band show the
// coach's portrait: happy on a checked right answer, cross on a checked wrong
// one, moved when the rule became held. The free-use scene's byline wears it.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { coachFor, coachMood, sceneLines } = require('./forge-coach.ts');

const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');

const margaux = { id: 'margaux_barman', name: 'Margaux', register: 'tu' };
const gus = { id: 'augustin_de_roncourt', name: 'Gus', register: 'tu' };

test('the forge names the coach first, then the rule, then the concept', () => {
  assert.equal(coachFor({ coach: gus }, { coach: margaux }, { coach: null }), gus);
  assert.equal(coachFor(null, { coach: margaux }, { coach: gus }), margaux);
  assert.equal(coachFor(null, undefined, { coach: gus }), gus);
  assert.equal(coachFor(null, { coach: { id: '' } }, {}), null, 'a malformed coach is no coach');
});

test("the coach's face follows the answer", () => {
  assert.equal(coachMood({ forge: { coach_mood: 'moved' } }, { correct: true }), 'moved', 'the server decides when it says');
  assert.equal(coachMood({ forge: { held: true } }, { correct: true }), 'moved');
  assert.equal(coachMood({ assessment_status: 'checked' }, { correct: true }), 'happy');
  assert.equal(coachMood({ assessment_status: 'checked' }, { correct: false }), 'cross');
  assert.equal(coachMood({ assessment_status: 'provisional' }, { correct: true }), 'neutral', 'unchecked: no reaction yet');
  assert.equal(coachMood(null, {}), 'neutral');
  assert.equal(coachMood({ forge: { coach_mood: 'furious' } }, { correct: false }), 'cross', 'an unknown mood falls back');
});

test('a free-use scene has the coach line and the reply', () => {
  const item = {
    scene: {
      lines: [
        { speaker: 'marin_leveque', name: 'Marin', fr: 'Tu prends le sac ?', en: 'Are you taking the bag?' },
        { speaker: 'learner', fr: 'Oui, je le prends.', en: 'Yes, I am taking it.' },
      ],
    },
  };
  const lines = sceneLines(item);
  assert.equal(lines.length, 2);
  assert.equal(lines[0].speaker, 'marin_leveque');
  assert.deepEqual(sceneLines({}), []);
});

test('the rule card shows the coach when the card has no speaker of its own', () => {
  const card = read('components/atelier-v2/rule/RuleCard.tsx');
  assert.match(card, /coach\?: \{ id: string; name: string \} \| null;/);
  assert.match(card, /const speakerId = card\.speaker \|\| coach\?\.id \|\| null;/);
  assert.match(card, /<CastPortrait characterId=\{speakerId\} name=\{speakerName\} mood=\{speakerMood\}/);
});

test('the feedback band shows the coach reacting in place of the badge', () => {
  const epreuve = read('components/epreuve/Epreuve.tsx');
  assert.match(epreuve, /coach\?: \{ id: string; name: string \} \| null;/);
  assert.match(epreuve, /<CastPortrait characterId=\{coach\.id\} name=\{coach\.name\} mood=\{coachMood \|\| 'neutral'\}/);
});

test('the séance passes the rule coach to the card, the feedback and the scene byline', () => {
  const page = read('pages/atelier.tsx');
  assert.match(page, /const ruleCoach = coachFor\(forgeNext, forgeRule, activeConcept\);/);
  assert.equal((page.match(/coach=\{ruleCoach\}/g) || []).length, 3, 'intro card, inline card, feedback');
  assert.match(page, /const mood = coachMood\(correction, \{ correct: feedback\.correct \}\);/);
  assert.match(page, /<EpVerdict tone="go" sub=\{rule\} coach=\{coach\} coachMood=\{mood\}>/);
  assert.match(page, /<EpVerdict tone="no" sub=\{rule\} coach=\{coach\} coachMood=\{mood\}>/);
  assert.match(page, /item\.scene && character\.id && \(\s*<CastPortrait/);
});
