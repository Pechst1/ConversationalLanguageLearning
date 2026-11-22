// node --test components/revue/comptoir/pourquoi.test.js
//
// «Papier · Le pourquoi» (owner 2026-11-20), the client:
//
//   1. the model: one why open at a time, each underlined run knows its mark, a mark
//      without a why opens nothing, La Forge's line only for a slip with a rule;
//   2. the wire: `why` and `notes` parsed when sent, the shape unchanged when not;
//   3. the marks rendered: without a why exactly today's markup; with one, the words are
//      buttons (44 px rows beside them) and the open why sits under the sentence;
//   4. the settled notes: the full why, «Dans l'article : …», the quiet line; nothing without notes;
//   5. the copy: fr, en and de say every line.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render } = setup;

const types = require('../../../lib/revue-types.ts');
const model = require('./pourquoi.ts');
const { markSegments } = require('./comptoir-model.ts');
const { comptoirCopy } = require('./comptoir-copy.ts');
const { RvProofMarks } = require('./RvProofMarks.tsx');
const { RvProofNotes } = require('./RvProofNotes.tsx');

const DRAFT = 'le gens sont content au marché';
const KINDS = comptoirCopy('en').mark_kinds;
const HINT = 'In French the article agrees with its noun in number.';
const MARKS = [
  { spanFr: 'le', start: 0, kind: 'accord', why: HINT },
  { spanFr: 'content', start: 13, kind: 'accord', why: 'The adjective after «être» agrees with the subject.' },
];

// ---------------------------------------------------------------------------
// 1. The model
// ---------------------------------------------------------------------------

test('one why open at a time; a mark without a why opens nothing', () => {
  assert.equal(model.toggleWhy(null, 0), 0);
  assert.equal(model.toggleWhy(0, 1), 1, 'another mark moves the panel');
  assert.equal(model.toggleWhy(1, 1), null, 'the open mark closes');
  assert.equal(model.openWhy(MARKS, 1).mark.spanFr, 'content');
  assert.equal(model.openWhy(MARKS, 5), null);
  assert.equal(model.openWhy([{ spanFr: 'le', start: 0, kind: 'accord' }], 0), null);
  assert.equal(model.hasWhy(MARKS), true);
  assert.equal(model.hasWhy([{ spanFr: 'le', start: 0, kind: 'accord' }]), false);
});

test('each underlined run knows its mark, cut as the marks are cut', () => {
  const segments = model.whySegments(DRAFT, MARKS);
  assert.deepEqual(segments.map((s) => [s.text, s.index]), [['le', 0], [' gens sont ', null], ['content', 1], [' au marché', null]]);
  assert.deepEqual(segments.map(({ text, kind }) => ({ text, kind })), markSegments(DRAFT, MARKS));
});

test('La Forge comes back only for a slip with a rule', () => {
  assert.deepEqual(model.settledNotes(undefined), { rows: [], forge: false });
  const notes = [
    { spanFr: 'le', kind: 'accord', why: 'full', exampleFr: null, ruleId: 'plural_s' },
    { spanFr: 'au', kind: 'mot', why: null, exampleFr: null, ruleId: null },
  ];
  assert.deepEqual(model.settledNotes(notes), { rows: [notes[0]], forge: true });
  assert.equal(model.settledNotes([{ ...notes[0], ruleId: null }]).forge, false);
});

// ---------------------------------------------------------------------------
// 2. The wire
// ---------------------------------------------------------------------------

const RAW_OPINION = {
  stance: 'contre',
  learner_fr: DRAFT,
  draft_fr: DRAFT,
  proof: 'marked',
  marks: [{ span_fr: 'le', start: 0, kind: 'accord' }],
  tries: 0,
  max_tries: 2,
  printed_fr: null,
  reply: null,
  comebacks: [],
  comeback: null,
};

test('the wire: why and notes when sent, today\'s shape when not', () => {
  const parse = (opinion) => types.parseComptoirView({ step: 'opinion', steps: [], band: 'a2', cast: [], opinion }).opinion;
  const today = parse(RAW_OPINION);
  assert.deepEqual(today.marks, [{ spanFr: 'le', start: 0, kind: 'accord' }]);
  assert.equal('notes' in today, false, 'no notes key without notes');
  const withWhy = parse({ ...RAW_OPINION, marks: [{ span_fr: 'le', start: 0, kind: 'accord', why: ` ${HINT} ` }] });
  assert.deepEqual(withWhy.marks, [{ spanFr: 'le', start: 0, kind: 'accord', why: HINT }]);
  const settled = parse({
    ...RAW_OPINION,
    proof: 'fixed',
    marks: [],
    notes: [
      { span_fr: 'le', kind: 'accord', why: 'full', example_fr: 'Les gens aiment le marché.', rule_id: 'plural_s' },
      { span_fr: 'x', kind: 'style', why: null, example_fr: null, rule_id: null },
    ],
  });
  assert.deepEqual(settled.notes, [{ spanFr: 'le', kind: 'accord', why: 'full', exampleFr: 'Les gens aiment le marché.', ruleId: 'plural_s' }]);
});

// ---------------------------------------------------------------------------
// 3. The marks
// ---------------------------------------------------------------------------

const marks = (props) => render(h(RvProofMarks, { draftFr: DRAFT, kindLabels: KINDS, copy: comptoirCopy('en').pourquoi, whyLanguage: 'en', ...props }));

test('without a why the marks are today\'s markup', () => {
  const plain = MARKS.map(({ why: _why, ...mark }) => mark);
  const html = marks({ marks: plain });
  assert.equal(
    html,
    '<p class="ct-paper__fr" lang="fr"><mark class="ct-mark" data-kind="accord">le</mark> gens sont <mark class="ct-mark" data-kind="accord">content</mark> au marché</p>'
      + '<ul class="ct-marks"><li class="ct-why"><b lang="fr">le</b> · agreement</li><li class="ct-why"><b lang="fr">content</b> · agreement</li></ul>',
  );
  assert.doesNotMatch(html, /button/);
});

test('with a why each underlined word is a button and the open why sits under the sentence', () => {
  const closed = marks({ marks: MARKS });
  assert.equal((closed.match(/<button[^>]*class="ct-mark ct-mark--why"/g) || []).length, 2, 'both words tappable');
  assert.equal((closed.match(/class="ct-why__b"/g) || []).length, 2, 'and their 44 px rows');
  assert.doesNotMatch(closed, /ct-why-open/, 'nothing open at first');
  assert.match(closed, /aria-label="Why “le”\?"/);

  const open = marks({ marks: MARKS, initialOpen: 1 });
  const panel = open.match(/<p id="ct-why" class="ct-why-open"[\s\S]*?<\/p>/)[0];
  assert.match(panel, /The adjective after «être» agrees with the subject\./);
  assert.match(panel, /lang="en"/, 'the why in the mother tongue');
  assert.doesNotMatch(open, new RegExp(HINT.replace('.', '\\.')), 'one why open at a time');
  assert.ok(open.indexOf('ct-why-open') > open.indexOf('</p>'), 'under the sentence');
  assert.equal((open.match(/aria-expanded="true"/g) || []).length, 2, 'the word and its row');
});

// Seen in a browser at 375 px (2026-11-20, A2 de): the open why is a column, and its head
// («le», « · agreement») came apart into two lines, the second starting with its dot.
test('the open why keeps its head on one line: the word and its kind together, the rule under it', () => {
  const panel = marks({ marks: MARKS, initialOpen: 0 }).match(/<p id="ct-why" class="ct-why-open"[\s\S]*?<\/p>/)[0];
  assert.match(panel, /^<p[^>]*><span class="ct-why-open__k"><b lang="fr">le<\/b> · agreement<\/span><span class="ct-why-open__t"/);
});

test('a mark without a why stays a plain underline beside ones that have one', () => {
  const html = marks({ marks: [MARKS[0], { spanFr: 'content', start: 13, kind: 'accord' }] });
  assert.match(html, /<mark class="ct-mark" data-kind="accord">content<\/mark>/);
  assert.equal((html.match(/ct-mark--why/g) || []).length, 1);
});

// ---------------------------------------------------------------------------
// 4. The settled notes
// ---------------------------------------------------------------------------

test('once settled: the full why, «Dans l\'article : …» and the quiet line', () => {
  const notes = [{ spanFr: 'le', kind: 'accord', why: 'The article agrees with its noun: «les gens».', exampleFr: 'Les gens aiment le marché.', ruleId: 'plural_s' }];
  const fr = render(h(RvProofNotes, { notes, kindLabels: comptoirCopy('fr').mark_kinds, copy: comptoirCopy('fr').pourquoi, whyLanguage: 'en' }));
  assert.match(fr, /<span class="ct-note__why" lang="en">The article agrees with its noun: «les gens»\.<\/span>/);
  assert.match(fr, /Dans l’article : <q lang="fr">Les gens aiment le marché\.<\/q>/);
  assert.match(fr, /<p class="ct-note__forge">Cette règle revient dans La Forge\.<\/p>/);
  assert.doesNotMatch(fr, /<a |<button/, 'nothing navigates away mid-session');
  const de = render(h(RvProofNotes, { notes, kindLabels: comptoirCopy('de').mark_kinds, copy: comptoirCopy('de').pourquoi, whyLanguage: 'de' }));
  assert.match(de, /Im Artikel:/);
  assert.equal(render(h(RvProofNotes, { notes: undefined, kindLabels: KINDS, copy: comptoirCopy('en').pourquoi, whyLanguage: 'en' })), '');
  assert.doesNotMatch(
    render(h(RvProofNotes, { notes: [{ ...notes[0], ruleId: null }], kindLabels: KINDS, copy: comptoirCopy('en').pourquoi, whyLanguage: 'en' })),
    /ct-note__forge/,
  );
});

// ---------------------------------------------------------------------------
// 5. The copy
// ---------------------------------------------------------------------------

test('fr, en and de say every line', () => {
  const keys = Object.keys(model.POURQUOI_COPY.fr).sort();
  for (const language of ['fr', 'en', 'de']) {
    const table = comptoirCopy(language).pourquoi;
    assert.deepEqual(Object.keys(table).sort(), keys, language);
    assert.ok(Object.values(table).every((line) => typeof line === 'string' && line.trim()), language);
  }
  assert.equal(model.pourquoiCopy('xx'), model.POURQUOI_COPY.fr);
});

// ---------------------------------------------------------------------------
// Integration 2026-11-22 (d5-03, d6-02): the opened why above the foot, one copy of the
// learner's sentence while Romy's corrections are shown, the fix field in whole lines.
// ---------------------------------------------------------------------------

test('an opened why is brought into the band above the fixed foot', () => {
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, 'RvProofMarks.tsx'), 'utf8');
  assert.match(src, /bringIntoView\(note,/);
  assert.match(src, /leaderRise\(/);
});

test('while Romy’s corrections card is shown, the learner’s own bubble is not repeated', () => {
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, 'RvComptoirOpinion.tsx'), 'utf8');
  assert.match(src, /\{opinion && !marked && !printsAsWritten && <MineLine textFr=\{opinion\.learnerFr\}/);
});

test('the fix field shows whole lines: its cap is a whole number of lines plus its padding and border', () => {
  const css = require('node:fs').readFileSync(require('node:path').join(__dirname, '../../../styles/revue.css'), 'utf8');
  const start = css.indexOf('.av2 .rv-composer .av2-field__control {');
  assert.ok(start >= 0, 'the composer control rule');
  const rule = css.slice(start, css.indexOf('}', start));
  assert.match(rule, /max-height: calc\(6lh \+ 1rem \+ 4px\)/, 'six whole lines');
  assert.match(rule, /padding-block: 0;/, 'no padding for scrolled text to show through');
  assert.match(rule, /border-block: calc\(0\.5rem \+ 2px\) solid var\(--av2-card\)/, 'the air is a border in the field’s colour');
});
