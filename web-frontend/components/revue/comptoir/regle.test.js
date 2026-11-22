// node --test components/revue/comptoir/regle.test.js
//
// «Papier · La règle» (2026-11-22), the client:
//
//   1. the wire: a mark's and a note's concept (`concept_id`, `concept_name`, `is_day_rule`,
//      `is_recent_rule`) parsed when sent, the shape unchanged when not;
//   2. the stamp: «règle du jour» before «règle de la semaine», nothing under no rule;
//   3. rendered: the stamp on the mark's row and on the settled note, the concept's name in
//      the open why and the note; without a concept exactly the markup before;
//   4. the mock (`&regle=1`): the counter's marks name their concept, the day's rule stamped;
//   5. the copy in fr, en and de.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render } = setup;

const types = require('../../../lib/revue-types.ts');
const rubriques = require('../../../lib/revue-rubriques-types.ts');
const mock = require('../../../lib/revue-mock-comptoir.ts');
const model = require('./pourquoi.ts');
const { comptoirCopy } = require('./comptoir-copy.ts');
const { RvProofMarks } = require('./RvProofMarks.tsx');
const { RvProofNotes } = require('./RvProofNotes.tsx');

const DRAFT = 'le gens sont content au marché';
const DAY = { conceptId: 'FR2_A11_ADJ_AGREEMENT', conceptName: 'Adjektive: Angleichung und Stellung', isDayRule: true };
const RULE_LINE = 'Adjektive passen sich an (+e weiblich, +s Plural), auch nach être, und stehen meist nach dem Nomen.';
const MARKS = [
  { spanFr: 'le', start: 0, kind: 'accord', why: 'Der Artikel richtet sich nach dem Nomen.', conceptId: 'FR2_A11_NOUN_PLURALS', conceptName: 'Plural der Nomen' },
  { spanFr: 'content', start: 13, kind: 'accord', why: RULE_LINE, ...DAY },
];

test('the wire: the concept when sent, the shape unchanged when not', () => {
  const parse = (marks) => types.parseComptoirView({ step: 'opinion', steps: [], band: 'a2', cast: [], opinion: {
    stance: 'contre', learner_fr: DRAFT, draft_fr: DRAFT, proof: 'marked', marks, tries: 0, max_tries: 2,
  } }).opinion.marks;
  assert.deepEqual(parse([{ span_fr: 'le', start: 0, kind: 'accord' }]), [{ spanFr: 'le', start: 0, kind: 'accord' }]);
  assert.deepEqual(
    parse([{ span_fr: 'content', start: 13, kind: 'accord', concept_id: 'FR2_A11_ADJ_AGREEMENT', concept_name: 'Adjektive: Angleichung und Stellung', is_day_rule: true, is_recent_rule: false }]),
    [{ spanFr: 'content', start: 13, kind: 'accord', ...DAY }],
  );
  const notes = types.parseComptoirNotes([{ span_fr: 'content', kind: 'accord', why: null, example_fr: null, rule_id: null, concept_id: 'FR2_A11_ADJ_AGREEMENT', concept_name: 'Adjektive', is_recent_rule: true }]);
  assert.deepEqual(notes, [{ spanFr: 'content', kind: 'accord', why: null, exampleFr: null, ruleId: null, conceptId: 'FR2_A11_ADJ_AGREEMENT', conceptName: 'Adjektive', isRecentRule: true }]);
  assert.equal(typeof rubriques.parseTitreView, 'function', 'the rubriques parse the same fields (marks())');
});

test('the stamp: the day\'s rule, then a recent one, else none', () => {
  const copy = comptoirCopy('de').pourquoi;
  assert.deepEqual(model.ruleStamp(DAY, copy), { kind: 'day', label: 'Regel des Tages' });
  assert.deepEqual(model.ruleStamp({ conceptId: 'x', isRecentRule: true }, copy), { kind: 'recent', label: 'Regel der Woche' });
  assert.deepEqual(model.ruleStamp({ conceptId: 'x', isDayRule: true, isRecentRule: true }, copy).kind, 'day');
  assert.equal(model.ruleStamp({ conceptId: 'x' }, copy), null);
  assert.equal(model.ruleStamp({ isDayRule: true }, copy), null, 'no concept, no stamp');
});

const marks = (props) => render(h(RvProofMarks, { draftFr: DRAFT, kindLabels: comptoirCopy('de').mark_kinds, copy: comptoirCopy('de').pourquoi, whyLanguage: 'de', ...props }));

test('rendered: the stamp on the mark under the day\'s rule, the concept named in the open why', () => {
  const closed = marks({ marks: MARKS });
  const stamps = closed.match(/<span class="pp-stamp ct-rule-stamp" data-ink="regle" data-rule="day"[^>]*><span class="pp-stamp__ink">Regel des Tages<\/span><\/span>/g) || [];
  assert.equal(stamps.length, 1, 'only the mark under the day\'s rule is stamped');
  assert.ok(closed.indexOf('Regel des Tages') > closed.indexOf('<b lang="fr">content</b>'), 'on its own row');
  const open = marks({ marks: MARKS, initialOpen: 1 });
  const panel = open.match(/<p id="ct-why" class="ct-why-open"[\s\S]*?<\/p>/)[0];
  assert.match(panel, /<span class="ct-rule-name" lang="de">Adjektive: Angleichung und Stellung<\/span>/);
  assert.match(panel, new RegExp(RULE_LINE.replace(/[()+]/g, '\\$&')));
  const plain = marks({ marks: MARKS.map(({ spanFr, start, kind }) => ({ spanFr, start, kind })) });
  assert.doesNotMatch(plain, /pp-stamp|ct-rule-name/, 'without a concept, the markup before');
});

test('the settled note carries the stamp and the concept\'s name', () => {
  const html = render(h(RvProofNotes, {
    notes: [{ spanFr: 'content', kind: 'accord', why: RULE_LINE, exampleFr: null, ruleId: null, ...DAY }],
    kindLabels: comptoirCopy('fr').mark_kinds, copy: comptoirCopy('fr').pourquoi, whyLanguage: 'de',
  }));
  assert.match(html, /règle du jour/);
  assert.match(html, /<span class="ct-rule-name" lang="de">Adjektive: Angleichung und Stellung<\/span>/);
});

test('the mock (&regle=1): the day\'s rule stamped, its card\'s line as the why', () => {
  const raw = [{ span_fr: 'le', start: 0, kind: 'accord', fix_fr: 'les' }, { span_fr: 'content', start: 13, kind: 'accord', fix_fr: 'contents' }];
  const off = mock.marksWire(raw, 'de', true);
  assert.ok(off.every((mark) => !('concept_id' in mark)), 'off: today\'s wire');
  const on = mock.marksWire(raw, 'de', true, true);
  assert.equal(on[1].concept_id, 'FR2_A11_ADJ_AGREEMENT');
  assert.equal(on[1].is_day_rule, true);
  assert.equal(on[1].why, RULE_LINE);
  assert.equal(on[0].is_day_rule, false);
  const notes = mock.notesWire([raw], 'fixed', 'de', '', true, true);
  assert.equal(notes[1].is_day_rule, true);
});

test('fr, en and de name the stamps', () => {
  assert.equal(comptoirCopy('fr').pourquoi.day_rule, 'règle du jour');
  assert.equal(comptoirCopy('de').pourquoi.day_rule, 'Regel des Tages');
  assert.equal(comptoirCopy('en').pourquoi.day_rule, 'today’s rule');
  for (const language of ['fr', 'en', 'de']) assert.ok(comptoirCopy(language).pourquoi.recent_rule.trim(), language);
});
