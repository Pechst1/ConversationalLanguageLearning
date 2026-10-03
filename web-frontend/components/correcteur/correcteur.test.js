// node --test components/correcteur/correcteur.test.js
//
// WP-122 B · Le Correcteur, the page's pieces:
//   1. a tap selects one unit and opens the field «Corrige»; a drag selects a span;
//   2. options at A1–A2 (the right form among three), none at B1;
//   3. the marks: one per span, a later mark replaces an overlapping one;
//   4. the result: each span in its outcome's colour with its word, the false alarm
//      shown kindly («celui-là était bon»), Romy's line, «Dans le Relevé»;
//   5. the client: snake_case marks, a bare 404 is «switched off».

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render, visibleText } = require('../revue/revue-test-setup');

const { createCorrecteurClient } = require('../../lib/correcteur-api.ts');
const { marksWire, parseDraft } = require('../../lib/correcteur-types.ts');
const model = require('./correcteur-model.ts');
const { createMockCorrecteurClient, mockDraft, mockKey } = require('./correcteur-mock.ts');
const { CorrecteurDesk, CrField, CrResultView, correcteurCopy } = require('./index.ts');
const fixture = require('./fixtures/mock-draft.json');

const FR = correcteurCopy('fr');
const EN = correcteurCopy('en');
const KEY = mockKey();

function unitIndexOf(draft, sentenceIndex, span) {
  return model.unitsOf(draft, sentenceIndex).findIndex((u) => u.span[0] === span[0] && u.span[1] === span[1]);
}

test('the mock draft is the backend draft: three classiques, every seed a unit', () => {
  const draft = mockDraft('A2');
  assert.equal(draft.errorsCount, 3);
  assert.equal(KEY.length, 3);
  assert.ok(KEY.every((seed) => seed.source === 'classique'));
  for (const seed of KEY) {
    assert.equal(draft.sentences[seed.sentenceIndex].slice(seed.span[0], seed.span[1]), seed.wrongFr);
    assert.ok(unitIndexOf(draft, seed.sentenceIndex, seed.span) >= 0, seed.wrongFr);
  }
  // The draft's wire carries no key.
  assert.equal(JSON.stringify(fixture.draft).includes('correct_fr'), false);
});

test('a tap selects one unit and opens the field «Corrige»', () => {
  const draft = mockDraft('A2');
  const seed = KEY[0]; // «à le» → «au»
  const unit = unitIndexOf(draft, seed.sentenceIndex, seed.span);
  const selection = model.selectUnits(draft, seed.sentenceIndex, unit);
  assert.deepEqual(selection.span, seed.span);
  assert.equal(selection.text, 'à le');
  const html = render(h(CorrecteurDesk, { draft, copy: FR, onSubmit: async () => null, initialSelection: selection }));
  assert.match(html, /data-correcteur-field/);
  assert.match(visibleText(html), /Corrige « à le »/);
  // The selected unit is outlined; one red press on the screen: «Bon à tirer».
  assert.match(html, /data-selected=""[^>]*>à le</);
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  assert.match(visibleText(html), /Bon à tirer/);
  // Without a selection there is no field.
  assert.doesNotMatch(render(h(CorrecteurDesk, { draft, copy: FR, onSubmit: async () => null })), /data-correcteur-field/);
});

test('a drag selects a span across units (either direction), with no options', () => {
  const draft = mockDraft('A1');
  const forward = model.selectUnits(draft, 0, 2, 4);
  const backward = model.selectUnits(draft, 0, 4, 2);
  assert.deepEqual(forward, backward);
  assert.equal(forward.text, 'transports publics, un');
  assert.equal(forward.options, null);
  assert.equal(model.selectUnits(draft, 9, 0), null);
});

test('options at A1–A2: three forms with the right one; none at B1', () => {
  for (const band of ['A1', 'A2']) {
    const draft = mockDraft(band);
    for (const seed of KEY) {
      const selection = model.selectUnits(draft, seed.sentenceIndex, unitIndexOf(draft, seed.sentenceIndex, seed.span));
      assert.ok(selection.options, `${band} ${seed.wrongFr}`);
      assert.ok(selection.options.includes(seed.correctFr) && selection.options.includes(seed.wrongFr));
      assert.ok(selection.options.length >= 2 && selection.options.length <= 3);
    }
  }
  const a1 = mockDraft('A1');
  const seed = KEY[0];
  const selection = model.selectUnits(a1, seed.sentenceIndex, unitIndexOf(a1, seed.sentenceIndex, seed.span));
  const html = render(h(CrField, { selection, copy: FR, onMark: () => {}, onCancel: () => {} }));
  assert.match(html, /role="radiogroup"/);
  for (const option of selection.options) assert.ok(visibleText(html).includes(option), option);

  const b1 = mockDraft('B1');
  assert.ok(b1.units.every((u) => u.options === null));
  const plain = model.selectUnits(b1, seed.sentenceIndex, unitIndexOf(b1, seed.sentenceIndex, seed.span));
  assert.equal(plain.options, null);
  assert.doesNotMatch(render(h(CrField, { selection: plain, copy: FR, onMark: () => {}, onCancel: () => {} })), /radiogroup/);
});

test('marks: one per span; a later mark replaces an overlapping one; marked words say so', () => {
  let marks = [];
  marks = model.upsertMark(marks, { sentenceIndex: 0, span: [66, 70], fixFr: 'du', picked: false });
  marks = model.upsertMark(marks, { sentenceIndex: 0, span: [63, 70], fixFr: 'au', picked: true });
  marks = model.upsertMark(marks, { sentenceIndex: 0, span: [66, 70], fixFr: 'au', picked: true });
  marks = model.upsertMark(marks, { sentenceIndex: 2, span: [43, 48], fixFr: null, picked: false });
  assert.equal(marks.length, 2);
  assert.equal(marks[0].fixFr, 'au');
  assert.equal(model.markIndexAt(marks, 2, [44, 45]), 1);
  assert.deepEqual(model.removeMark(marks, 0), [marks[1]]);
  const html = render(h(CorrecteurDesk, { draft: mockDraft('A2'), copy: FR, onSubmit: async () => null, initialMarks: marks }));
  // «à le» is one unit (the contraction pair), «greve» another: two marked units.
  assert.equal((html.match(/data-marked=""/g) || []).length, 2);
  assert.match(visibleText(html), /à le → au/);
  assert.match(visibleText(html), /greve → à revoir/);
});

test('the result: outcome colours with their words, a false alarm shown kindly', () => {
  const draft = mockDraft('A2');
  const [contraction, agreement] = KEY;
  const marks = [
    { sentenceIndex: contraction.sentenceIndex, span: contraction.span, fixFr: 'au', picked: true },
    { sentenceIndex: agreement.sentenceIndex, span: agreement.span, fixFr: 'réorganisés', picked: false },
    { sentenceIndex: 0, span: [0, 4], fixFr: null, picked: false }, // «Dans»: correct
  ];
  const result = model.gradeLocally(draft, KEY, marks, fixture.romy_lines);
  assert.deepEqual(result.counts, { seeded: 3, repaired: 1, noticed: 1, missed: 1, falseAlarms: 1 });
  assert.deepEqual(result.outcomes.map((o) => o.outcome), ['repaired', 'noticed', 'missed']);
  assert.equal(result.romyLineFr, fixture.romy_lines.A.most);

  const html = render(h(CrResultView, { result, kickerFr: draft.kickerFr, titleFr: draft.titleFr, bylineFr: draft.bylineFr, copy: FR }));
  for (const outcome of ['repaired', 'noticed', 'missed', 'false_alarm']) assert.match(html, new RegExp(`data-outcome="${outcome}"`), outcome);
  const text = visibleText(html);
  assert.match(text, /celui-là était bon/);
  assert.match(text, /mieux vaut une marque de trop/);
  assert.doesNotMatch(text, /faux|erreur de ta part|-1/); // never a penalty
  assert.match(text, /1 corrigées · 1 repérées · 1 manquées/);
  assert.ok(text.includes(result.romyLineFr));
  assert.match(html, /href="\/notebook\?mode=releve"/);
  assert.match(text, /Dans le Relevé/);
  // Each coloured span carries its correction and its word (not colour alone).
  assert.match(html, /<s class="cr-out__wrong">greve<\/s> <span class="cr-out__right">grève<\/span><span class="av2-sr"> \(manquée\)/);
  // English chrome, French draft.
  const en = visibleText(render(h(CrResultView, { result, kickerFr: draft.kickerFr, titleFr: draft.titleFr, bylineFr: draft.bylineFr, copy: EN })));
  assert.match(en, /that one was right/);
  assert.match(en, /In Le Relevé/);
});

test('a typed fix over a wider span repairs; a wrong fix only notices', () => {
  const draft = mockDraft('B1');
  const [contraction] = KEY;
  const wide = { sentenceIndex: 0, span: [contraction.span[0], contraction.span[1] + 6], fixFr: 'au moins', picked: false };
  assert.equal(model.gradeLocally(draft, KEY, [wide], fixture.romy_lines).outcomes[0].outcome, 'repaired');
  const wrong = { ...wide, fixFr: 'du moins' };
  assert.equal(model.gradeLocally(draft, KEY, [wrong], fixture.romy_lines).outcomes[0].outcome, 'noticed');
  const none = model.gradeLocally(draft, KEY, [], fixture.romy_lines);
  assert.equal(none.romyLineFr, fixture.romy_lines.B.none);
});

test('the client: snake_case marks, parse, a bare 404 is switched off', async () => {
  const calls = [];
  const transport = {
    get: async (url) => {
      calls.push(['get', url]);
      throw { response: { status: 404, data: { detail: 'Not Found' } } };
    },
    post: async (url, body) => {
      calls.push(['post', url, body]);
      if (url.endsWith('/marks')) return { id: 'x', dossier_id: 'd', sentences: [], outcomes: [], false_alarms: [], counts: {}, romy_line_fr: 'Bien.', releve_href: '/notebook?mode=releve' };
      return fixture.draft;
    },
  };
  const client = createCorrecteurClient(transport);
  assert.deepEqual(await client.week(), { enabled: false });
  const draft = await client.draft('evergreen-greve-transports');
  assert.equal(draft.units.length, parseDraft(fixture.draft).units.length);
  await client.marks('abc', [{ sentenceIndex: 0, span: [1, 3], fixFr: ' au ', picked: true }]);
  assert.deepEqual(calls.at(-1), ['post', '/revue/correcteur/abc/marks', { marks: [{ sentence_index: 0, span: [1, 3], fix_fr: 'au', picked: true }] }]);
  assert.deepEqual(marksWire([{ sentenceIndex: 1, span: [0, 2], fixFr: '  ', picked: false }]).marks[0].fix_fr, null);
});

test('the mock client grades with the same rules', async () => {
  const client = createMockCorrecteurClient({ band: 'A1', latency: 0 });
  const week = await client.week();
  assert.equal(week.enabled, true);
  const draft = await client.draft(week.week.dossiers[0].id);
  const result = await client.marks(draft.id, KEY.map((seed) => ({ sentenceIndex: seed.sentenceIndex, span: seed.span, fixFr: seed.correctFr, picked: true })));
  assert.equal(result.counts.repaired, 3);
  assert.equal(result.romyLineFr, fixture.romy_lines.A.all_repaired);
});
