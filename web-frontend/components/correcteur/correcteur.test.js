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

// --- 6. La Une and the Relevé: «Le Correcteur · un brouillon t'attend» -------------

const fs = require('node:fs');
const path = require('node:path');
const { correcteurHomeChip, correcteurWaiting, withCorrecteurChip, correcteurHref } = require('../../lib/correcteur-une.ts');
const { radioHomeChip, withRadioChip } = require('../../lib/radio-une.ts');
const radioTypes = require('../../lib/radio-types.ts');
const { parseWeek } = require('../../lib/correcteur-types.ts');

const CR_WEEK = { enabled: true, week: parseWeek({ week: '2026-W40', label: 'Semaine 40', dossiers: [{ id: 'evergreen-greve-transports', title_fr: 'Grève', topic: 'work', evergreen: true }], corrected: [] }) };

test('the chip «Le Correcteur» to the waiting draft; none when off, nothing waits, or one was corrected this week', () => {
  const chip = correcteurHomeChip(CR_WEEK, 'fr');
  assert.deepEqual(chip, {
    id: 'correcteur',
    label: 'Le Correcteur',
    ariaLabel: 'Le Correcteur · un brouillon t’attend',
    href: '/correcteur?dossier=evergreen-greve-transports',
    shape: 'story',
  });
  assert.equal(correcteurHomeChip(CR_WEEK, 'en').ariaLabel, 'Le Correcteur · a draft is waiting for you');
  assert.equal(correcteurHomeChip(CR_WEEK, 'de').ariaLabel, 'Le Correcteur · ein Entwurf wartet auf dich');
  assert.equal(correcteurHomeChip({ enabled: false }, 'fr'), null);
  assert.equal(correcteurHomeChip({ enabled: true, week: { ...CR_WEEK.week, dossiers: [] } }, 'fr'), null);
  assert.equal(correcteurHomeChip({ enabled: true, week: { ...CR_WEEK.week, corrected: ['x'] } }, 'fr'), null);
  assert.deepEqual(correcteurWaiting(CR_WEEK), { id: 'evergreen-greve-transports', titleFr: 'Grève' });
  assert.equal(correcteurHref('a b'), '/correcteur?dossier=a%20b');
  // Its place: after the Radio, else the Revue, else the letter, else first; never on the Papier day.
  const ids = (chips) => chips.map((c) => c.id);
  const [letter, revue, radio, words, cr] = ['courrier', 'revue', 'radio', 'lexique', 'correcteur'].map((id) => ({ id }));
  assert.deepEqual(ids(withCorrecteurChip([letter, revue, radio, words], cr)), ['courrier', 'revue', 'radio', 'correcteur', 'lexique']);
  assert.deepEqual(ids(withCorrecteurChip([revue, words], cr)), ['revue', 'correcteur', 'lexique']);
  assert.deepEqual(ids(withCorrecteurChip([letter, words], cr)), ['courrier', 'correcteur', 'lexique']);
  assert.deepEqual(ids(withCorrecteurChip([words], cr)), ['correcteur', 'lexique']);
  assert.deepEqual(ids(withCorrecteurChip([words], cr, true)), ['lexique'], 'the Papier day keeps La Une whole');
  assert.deepEqual(ids(withCorrecteurChip([letter], null)), ['courrier']);
  const page = fs.readFileSync(path.join(__dirname, '..', '..', 'pages', 'atelier.tsx'), 'utf8');
  assert.match(page, /withCorrecteurChip<HomeChip>\(withRadioChip<HomeChip>\(/);
});

// HomeScreen's budget: at most two chips, in precedence letter · Papier · Radio · Correcteur · words due.
const { HomeScreen } = require('../atelier-v2/home/HomeScreen.tsx');
const { JourneyTodayCard } = require('../atelier-v2/journey/JourneyTodayCard.tsx');
const journeyState = require('../atelier-v2/journey/journey-state.ts');
const { dayMarkState } = require('../atelier-v2/journey/day-mark.ts');
const { atelierCopy } = require('../../lib/atelier-v2-copy.ts');
const revueTypes = require('../../lib/revue-types.ts');
const { revueHomeChip } = require('../revue/revue-home.ts');
const { WEB_ROOT } = require('../revue/revue-test-setup');

const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const DAY = JSON.parse(fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/first_day.json'), 'utf8')).response;
const REVUE = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, 'components/revue/fixtures/mock-wire.json'), 'utf8'));
const RADIO = { enabled: true, week: radioTypes.parseRadioWeek({ week: '2026-W40', current: { dossier_id: 'evergreen-greve-transports', title_fr: 'Grève', topic: 'work', evergreen: true }, queue: [], heard: [], heard_today: false, chip: true, seconds: 53 }) };
const wordCount = (text) => text.split(' ').filter((token) => /[\p{L}\p{N}]/u.test(token)).length;
const prose = (html) => visibleText(html.replace(/<span aria-hidden="true" data-level-figure="">[\s\S]*?<\/span>/g, ' '));
const primaries = (html) => (html.match(/av2-btn--primary/g) || []).length;

function home(language, chips, extra = {}) {
  const envelope = { ...DAY, control_language: language };
  const controller = {
    phase: journeyState.phaseFromEnvelope(envelope),
    feedback: { kind: 'idle' },
    envelope,
    journey: envelope.journey ?? null,
    step: null,
    respondPrompt: null,
    controlLanguage: language,
    legacyResume: envelope.legacy_resume ?? null,
    progress: journeyState.journeyProgress(envelope.journey ?? null),
    busy: false,
    help: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
  return render(
    h(HomeScreen, {
      dateLabel: 'mardi 23 septembre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      level: { band: 'A1.1', percent: 60 },
      language,
      day: dayMarkState(null, language),
      hero: h(JourneyTodayCard, { controller, onOpen: () => {} }),
      chips,
      ...extra,
    }),
  );
}

test('La Une budget: the Correcteur shows only when fewer than two of letter · Papier · Radio are on; ≤ 25 words, one press', () => {
  const revueWeek = { enabled: true, offer: revueTypes.parseOffer(REVUE.offer) };
  for (const language of ['en', 'de', 'fr']) {
    const copy = atelierCopy(language);
    const letter = { id: 'courrier', label: copy.home_letter, ariaLabel: copy.home_letter_aria, href: '/missions?mission=1', shape: 'story' };
    const words = { id: 'lexique', label: copy.home_words_many.replace('{n}', '3'), ariaLabel: copy.home_review_many.replace('{n}', '3'), href: '/vocabulary/review' };
    const revue = revueHomeChip(revueWeek, language);
    const radio = radioHomeChip(RADIO, language);
    const cr = correcteurHomeChip(CR_WEEK, language);
    const cases = [
      [[letter, revue, words], radio, ['courrier', 'revue']],
      [[revue, words], radio, ['revue', 'radio']],
      [[revue, words], null, ['revue', 'correcteur']],
      [[letter, words], null, ['courrier', 'correcteur']],
      [[words], radio, ['radio', 'correcteur']],
      [[words], null, ['correcteur', 'lexique']],
    ];
    for (const [base, radioChip, shown] of cases) {
      const chips = withCorrecteurChip(withRadioChip(base, radioChip), cr);
      const html = home(language, chips);
      const drawn = [...html.matchAll(/data-chip="([^"]+)"/g)].map((m) => m[1]);
      assert.deepEqual(drawn, shown, `${language}: ${base.map((c) => c.id).join('+')}${radioChip ? '+radio' : ''}`);
      const count = wordCount(prose(html));
      assert.ok(count <= 25, `${language}: ${count} words — ${prose(html)}`);
      assert.equal(primaries(html), 1, 'a chip is never a press');
    }
    const done = home(language, withCorrecteurChip([words], cr), { dayDone: true });
    assert.ok((done.match(/data-chip=/g) || []).length <= 1);
  }
});
