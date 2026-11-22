// node --test components/revue/choix/choix.test.js
//
// «Papier · le choix» (2026-11-22): the learner chooses the story.
//
//   1. the wire: `choices`, `why_language` and each card's `why` are read; absent, the offer is as before;
//   2. the why line says only what the record holds, in the mother tongue (fr / de / en);
//   3. RvChoix sets up to three stories as a front page — the lead, then the columns — each one
//      button with its rubric and its line, and nothing is said for a story picked for no reason;
//   4. the journey's Papier opens on the front page when the week carries one (`choose`), else as before;
//   5. the mock (`?mock=1&choix=1`) offers three and starts the one tapped in its rubric.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render, visibleText } = require('../revue-test-setup');

const types = require('../../../lib/revue-types.ts');
const { createMockRevueClient } = require('../../../lib/revue-mock.ts');
const { revueCopy } = require('../revue-copy.ts');
const { whyLine, whyParts } = require('./choix-copy.ts');
const { RvChoix } = require('./RvChoix.tsx');
const { papierEntryAction } = require('../RvJourneyPapier.tsx');

const card = (id, extra = {}) => ({
  dossier_id: id,
  title_fr: `Titre ${id}`,
  summary_fr: `Résumé ${id}`,
  topic: 'culture',
  place_fr: 'Paris',
  plate_url: null,
  evergreen: true,
  stage: { place_id: 'p', place_fr: 'Paris', plate_url: null, cast: [] },
  ...extra,
});
const WEEK = { iso: '2026-W47', label: 'Semaine 47', range: 'du 16 au 22 nov.' };

test('the wire: choices and their why are read, and an offer without them is as before', () => {
  const raw = {
    week: WEEK,
    recommended: card('a'),
    recommended_reason: 'interests',
    alternatives: [],
    evergreen_only: false,
    choices: [
      card('a', { assignment: { key: 'comptoir', name_fr: 'Au comptoir' }, why: { due_words: ['le concert', ''], rule: { id: 'R', name: 'Meinung sagen', today: true }, interest: null, score: 9 } }),
      card('b', { why: { due_words: [], rule: null, interest: { topic: 'food', word: 'kochen' }, score: 5 } }),
    ],
    why_language: 'de',
  };
  const offer = types.parseOffer(raw);
  assert.equal(offer.whyLanguage, 'de');
  assert.deepEqual(offer.choices[0].why, { dueWords: ['le concert'], rule: { id: 'R', name: 'Meinung sagen', today: true }, interest: null });
  assert.deepEqual(offer.choices[1].why.interest, { topic: 'food', word: 'kochen' });
  const before = types.parseOffer({ ...raw, choices: undefined, why_language: undefined });
  assert.equal(before.choices, null);
  assert.equal(before.whyLanguage, null);
  assert.equal(before.recommended.why, null);
});

test('the why line says only what the record holds, in the mother tongue', () => {
  const why = { dueWords: ['a', 'b', 'c'], rule: { id: 'R', name: 'Seine Meinung sagen', today: true }, interest: null };
  assert.equal(whyLine(why, 'de'), 'Mit 3 deiner Wörter · Regel des Tages: Seine Meinung sagen');
  assert.equal(whyLine({ ...why, rule: { ...why.rule, name: 'Giving your opinion', today: false } }, 'en'), 'With 3 of your words · this week’s rule: Giving your opinion');
  assert.equal(whyLine({ dueWords: ['x'], rule: null, interest: null }, 'fr'), 'Avec un de tes mots');
  assert.equal(whyLine({ dueWords: [], rule: null, interest: { topic: 'sport', word: 'Fußball' } }, 'de'), 'Dein Thema: Sport');
  assert.equal(whyLine({ dueWords: [], rule: null, interest: { topic: '', word: 'jazz' } }, 'en'), 'Your topic: jazz');
  assert.deepEqual(whyParts(null, 'de'), []);
  assert.equal(whyLine({ dueWords: [], rule: null, interest: null }, 'de'), '');
});

test('RvChoix: a front page of up to three, each one button with its rubric and its line', () => {
  const offer = types.parseOffer({
    week: WEEK, recommended: card('a'), recommended_reason: 'first', alternatives: [], evergreen_only: false,
    choices: [
      card('a', { assignment: { key: 'comptoir', name_fr: 'Au comptoir' }, question_fr: 'Ça te plaît ?', cast: ['x', 'y', 'z'], why: { due_words: ['le concert', 'revenir'], rule: { id: 'R', name: 'Seine Meinung sagen', today: true }, interest: null } }),
      card('b', { assignment: { key: 'titre', name_fr: 'Le titre' }, why: { due_words: [], rule: null, interest: { topic: 'culture', word: 'Musik' } } }),
      card('c', { topic: 'food' }),
      card('d'),
    ],
    why_language: 'de',
  });
  const html = render(h(RvChoix, { choices: offer.choices, week: offer.week, whyLanguage: 'de', language: 'de', onPick: () => {}, copy: revueCopy('de') }));
  const text = visibleText(html);
  assert.equal((html.match(/<button/g) || []).length, 3, 'three stories, three buttons, no fourth');
  assert.match(html, /class="pp-choix__lead"[^>]*data-dossier="a"/);
  assert.match(html, /class="pp-choix__cols" data-n="2"/);
  assert.match(text, /Le Papier/);
  assert.match(text, /Au comptoir Kultur Ça te plaît \?/, 'the counter leads with its question');
  assert.match(text, /Mit 2 deiner Wörter Regel des Tages: Seine Meinung sagen le concert · revenir/);
  assert.match(text, /Le titre Titre b Dein Thema: Kultur/);
  assert.match(text, /Essen Titre c/, 'no assignment: the topic is the kicker');
  assert.equal((html.match(/pp-choix__why/g) || []).length, 2, 'nothing is said for a story picked for no reason');
  assert.match(html, /lang="de">Dein Thema/);
});

test('the journey opens on the front page when the week carries one, else as before', () => {
  const base = { week: WEEK, recommended: { dossierId: 'a' }, recommendedReason: 'first', alternatives: [], evergreenOnly: false, resume: null, filed: null, choices: null, whyLanguage: null };
  assert.equal(papierEntryAction({ enabled: true, offer: base }), 'start');
  assert.equal(papierEntryAction({ enabled: true, offer: { ...base, choices: [] } }), 'start');
  assert.equal(papierEntryAction({ enabled: true, offer: { ...base, choices: [{ dossierId: 'a' }] } }), 'choose');
  assert.equal(papierEntryAction({ enabled: true, offer: { ...base, choices: [{ dossierId: 'a' }], resume: { sessionId: 's' } } }), 'resume');
  assert.equal(papierEntryAction({ enabled: true, offer: { ...base, choices: [{ dossierId: 'a' }], filed: { sessionId: 's' } } }), 'done');
});

test('the mock offers three and starts the tapped one in the rubric it showed', async () => {
  const client = createMockRevueClient({ language: 'de', choix: true, persist: false });
  const week = await client.week();
  assert.equal(week.offer.choices.length, 3);
  assert.equal(week.offer.whyLanguage, 'de');
  for (const choice of week.offer.choices.filter((c) => c.assignment)) {
    const fresh = createMockRevueClient({ language: 'de', choix: true, persist: false });
    const session = await fresh.start({ dossierId: choice.dossierId });
    assert.equal(session.dossier.id, choice.dossierId);
    assert.equal(session.mode, choice.assignment.key);
  }
  const plain = await createMockRevueClient({ language: 'de', persist: false }).week();
  assert.equal(plain.offer.choices, null, 'without ?choix=1 the mock is as before');
});
