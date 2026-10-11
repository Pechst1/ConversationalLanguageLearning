// node --test lib/rule-card.test.js
//
// WP-L10 — the rule card v2:
//   1. the markup: [x] carries the rule (red), {x} is silent (grey);
//   2. the learner's language is picked, English is the floor;
//   3. the intro card has exactly one Garamond headline, and it is French;
//   4. the inline card has none (the exercise prompt is the headline);
//   5. the stylesheet draws the card with --av2 tokens only.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { parseMarked, plainText, pick, usableCard } = require('./rule-card');
const { RuleCard } = require('@/components/atelier-v2/rule/RuleCard');

const cards = JSON.parse(
  fs.readFileSync(path.join(WEB_ROOT, '..', 'app', 'data', 'grammar_rule_cards.json'), 'utf8'),
).cards;

test('the markup splits rule, silent and plain parts', () => {
  assert.deepEqual(parseMarked('habit{e}'), [
    { text: 'habit', tone: 'plain' },
    { text: 'e', tone: 'silent' },
  ]);
  assert.deepEqual(parseMarked('[le] café'), [
    { text: 'le', tone: 'mark' },
    { text: ' café', tone: 'plain' },
  ]);
  assert.equal(plainText('Une petit[e] table blanch[e].'), 'Une petite table blanche.');
});

test("the learner's language is picked, English is the floor", () => {
  assert.equal(pick({ en: 'A', de: 'B' }, 'de'), 'B');
  assert.equal(pick({ en: 'A' }, 'fr'), 'A');
  assert.equal(usableCard(cards.FR_A1_NOUN_001), true);
  assert.equal(usableCard({ example: { fr: '' }, rule: {} }), false);
});

const render = (props) => renderToStaticMarkup(React.createElement(RuleCard, props));

test('the intro card has one Garamond headline, and it is the French example', () => {
  const html = render({ card: cards.FR_A1_NOUN_001, language: 'en', variant: 'intro', conceptId: 1, onDone: () => {} });
  assert.equal((html.match(/av2-headline/g) || []).length, 1);
  assert.match(html, /<h2 class="av2-headline rc-example" lang="fr">Une petit<span class="rc-mark">e<\/span>/);
  assert.match(html, /The noun decides\./);
  assert.match(html, /Essayer/);
  assert.doesNotMatch(html, /Le schéma|Le contrôle|Avoid:/);
});

test('a German learner reads the rule in German, with a silent-ending table', () => {
  const html = render({ card: cards.FR_A1_VERB_001, language: 'de', variant: 'intro', conceptId: 2, onDone: () => {} });
  assert.match(html, /Streiche -er/);
  assert.match(html, /habit<span class="rc-silent">ent<\/span>/);
  assert.match(html, /habit<span class="rc-mark">ez<\/span>/);
  assert.match(html, /Übersetzen/);
});

test('the inline card sets no headline (the exercise prompt is the one headline)', () => {
  const html = render({ card: cards.FR_A1_NOUN_001, language: 'en', variant: 'inline', conceptId: 1 });
  assert.doesNotMatch(html, /av2-headline/);
  assert.doesNotMatch(html, /Essayer/);
});

test('the card is drawn with av2 tokens only', () => {
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles', 'atelier-v2.css'), 'utf8');
  const block = css.slice(css.indexOf('WP-L10 — the rule card v2'), css.indexOf('.av2 .rc-done'));
  assert.ok(block.length > 200);
  assert.doesNotMatch(block, /#[0-9a-f]{3,6}\b/i, 'no raw hex colours');
  assert.doesNotMatch(block, /stroke:/, 'shapes are never outlined');
});

// ---------------------------------------------------------------------------
// F-1 (content program 2026-10-03): the v2+ card, the colour key, the x-ray.
// ---------------------------------------------------------------------------

const {
  howSteps,
  cardPartners,
  cardHasDepth,
  markupTones,
  xrayPieces,
  xrayRoleLabel,
  locateXray,
  xraySegments,
  usableXray,
  pickXrayMark,
} = require('./rule-card');
const { XraySentence } = require('@/components/atelier-v2/rule/XraySentence');

const V2_DIR = path.join(WEB_ROOT, '..', 'app', 'data', 'rule_cards');
const v2Cards = Object.assign(
  {},
  ...fs
    .readdirSync(V2_DIR)
    .filter((name) => /^fr2_.*\.json$/.test(name))
    .map((name) => JSON.parse(fs.readFileSync(path.join(V2_DIR, name), 'utf8')).cards),
);

test('unbalanced or nested markup renders as plain text and never crashes', () => {
  assert.deepEqual(parseMarked('Elle [est parti'), [{ text: 'Elle est parti', tone: 'plain' }]);
  assert.deepEqual(parseMarked('il} parle]'), [{ text: 'il parle', tone: 'plain' }]);
  assert.deepEqual(parseMarked('[a{b}c]'), [
    { text: 'a', tone: 'plain' },
    { text: 'b', tone: 'silent' },
    { text: 'c', tone: 'plain' },
  ]);
  assert.deepEqual(parseMarked('parl[ai]{s}'), [
    { text: 'parl', tone: 'plain' },
    { text: 'ai', tone: 'mark' },
    { text: 's', tone: 'silent' },
  ]);
  assert.deepEqual(parseMarked('[]{}'), []);
  assert.deepEqual(parseMarked(undefined), []);
  assert.deepEqual(parseMarked({ fr: '[x]' }), [], 'a non-string is no text, not «[object Object]»');
  assert.equal(plainText('Je [suis] allé{e} [au'), 'Je suis allée au');
  assert.deepEqual(markupTones(['habit{e}', 'rien']), { mark: false, silent: true });
});

test('every authored v2 card is usable and its markup is balanced', () => {
  const ids = Object.keys(v2Cards);
  assert.ok(ids.length >= 100, `the A1–B1 shards are there (${ids.length})`);
  const french = (card) => [
    card.example?.fr,
    card.contrast?.wrong,
    card.contrast?.right,
    ...(card.pattern?.rows || []).map((row) => row.fr),
    ...(card.examples || []).map((item) => item.fr),
    ...(card.traps || []).flatMap((trap) => [trap.wrong, trap.right]),
  ].filter((value) => typeof value === 'string');
  const unbalanced = [];
  for (const id of ids) {
    assert.equal(usableCard(v2Cards[id]), true, id);
    for (const value of french(v2Cards[id])) {
      const rest = value.replace(/\[[^[\]{}]*\]|\{[^[\]{}]*\}/g, '');
      if (/[[\]{}]/.test(rest)) unbalanced.push(`${id}: ${value}`);
    }
  }
  assert.deepEqual(unbalanced, []);
});

test('how-to steps lose their typed numbers; partners need a title, French first', () => {
  const card = v2Cards.FR2_A21_PC_ETRE;
  const steps = howSteps(card, 'de');
  assert.equal(steps.length, 3);
  assert.match(steps[0], /^Prüfe das Verb/);
  assert.doesNotMatch(steps.join(' '), /^\d\./m);
  assert.deepEqual(cardPartners(card, 'en'), [], 'no titles from the server: no links');
  const titled = {
    ...card,
    contrast_with: [
      { ...card.contrast_with[0], title: { en: 'Passé composé with avoir', fr: 'Le passé composé avec avoir' } },
      card.contrast_with[1],
    ],
  };
  const partners = cardPartners(titled, 'de');
  assert.equal(partners.length, 1);
  assert.equal(partners[0].title, 'Le passé composé avec avoir');
  assert.match(partners[0].note, /Die meisten Verben nehmen avoir/);
  assert.equal(partners[0].href, '/grammar?unit=FR2_A21_PC_AVOIR');
  assert.equal(cardHasDepth(card, 'en'), true);
  assert.equal(cardHasDepth(cards.FR_A1_NOUN_001, 'en'), false, 'a v1 card has no depth');
});

test('a v2+ card keeps a short first view; its depth opens behind «More»', () => {
  const card = {
    ...v2Cards.FR2_A21_PC_ETRE,
    contrast_with: [
      { ...v2Cards.FR2_A21_PC_ETRE.contrast_with[0], title: { fr: 'Le passé composé avec avoir' } },
      v2Cards.FR2_A21_PC_ETRE.contrast_with[1],
    ],
  };
  const closed = render({ card, language: 'en', variant: 'intro', conceptId: 7, onDone: () => {} });
  assert.equal((closed.match(/av2-headline/g) || []).length, 1, 'still one Garamond line');
  assert.match(closed, /Elle <span class="rc-mark">est<\/span> parti<span class="rc-mark">e<\/span>/);
  assert.match(closed, /class="rc-key"/, 'the colour key, the first time');
  assert.match(closed, /<span class="rc-mark">red<\/span> = carries the rule/);
  assert.match(closed, /aria-expanded="false">More</);
  assert.doesNotMatch(closed, /How to build it|Watch out|Compare with|J’ai allé|J'ai allé/);

  const open = render({ card, language: 'en', variant: 'inline', defaultOpen: true });
  assert.match(open, /aria-expanded="true">More</);
  assert.equal((open.match(/class="rc-step"/g) || []).length, 3, 'three numbered steps');
  assert.match(open, /How to build it/);
  assert.match(open, /More examples/);
  assert.match(open, /Nous <span class="rc-mark">sommes<\/span> arrivé<span class="rc-mark">s<\/span>/);
  assert.match(open, /Show translations/);
  assert.doesNotMatch(open, /We arrived in Lyon/, 'translations on demand');
  assert.match(open, /Watch out/);
  assert.match(open, /<s>J&#x27;ai allé au cinéma\.<\/s>/);
  assert.match(open, /Aller is an être verb/);
  assert.match(open, /Compare with/);
  assert.match(open, /href="\/grammar\?unit=FR2_A21_PC_AVOIR"/);
  assert.match(open, /Le passé composé avec avoir/);
  assert.doesNotMatch(open, /FR2_A21_PC_PRONOMINAL/, 'an untitled partner is left out');
  assert.doesNotMatch(open, /av2-headline/);

  const german = render({ card, language: 'de', variant: 'inline', defaultOpen: true });
  assert.match(german, /Mehr/);
  assert.match(german, /So baust du es/);
  assert.match(german, /<span class="rc-mark">rot<\/span> = trägt die Regel/);
});

test('a v1 card still opens «Why?» with the note and the cahier link', () => {
  const html = render({ card: cards.FR_A1_NOUN_001, language: 'en', variant: 'inline', conceptId: 3, defaultOpen: true });
  assert.match(html, />Why\?</);
  assert.match(html, /<p class="rc-more">/);
  assert.match(html, /href="\/grammar\?concept=3"/);
  assert.doesNotMatch(html, /rc-deep|rc-sec/);
});

test('the x-ray finds discontinuous, overlapping and apostrophe-folded marks', () => {
  assert.deepEqual(xrayPieces('ne...que'), ['ne', 'que']);
  assert.deepEqual(xrayPieces('ne … que'), ['ne', 'que']);
  assert.equal(xrayRoleLabel('agreement_marks'), 'Agreement marks');

  const sentence = 'Je ne bois que du thé le matin.';
  const marks = [
    { token: 'ne...que', role: 'restriction', explanation: 'ne…que = only' },
    { token: 'du thé', role: 'article_kept', explanation: 'article stays' },
    { token: 'jamais', role: 'missing', explanation: 'not in the sentence' },
  ];
  assert.deepEqual(locateXray(sentence, marks), [[[3, 5], [11, 14]], [[15, 21]], []]);
  assert.deepEqual(
    xraySegments(sentence, marks).map((segment) => [segment.text, segment.marks]),
    [['Je ', []], ['ne', [0]], [' bois ', []], ['que', [0]], [' ', []], ['du thé', [1]], [' le matin.', []]],
  );

  // «ne» is found as a word, not inside «personne».
  assert.deepEqual(locateXray('Personne ne vient.', [{ token: 'ne' }]), [[[9, 11]]]);
  // iOS apostrophes in the sentence, ASCII in the token.
  assert.deepEqual(locateXray('S’il fait beau, nous irons.', [{ token: "S'il fait" }]), [[[0, 9]]]);

  const overlap = 'Marie est arrivée hier.';
  const both = [{ token: 'est arrivée' }, { token: 'arrivée' }];
  assert.deepEqual(
    xraySegments(overlap, both).map((segment) => [segment.text, segment.marks]),
    [['Marie ', []], ['est ', [0]], ['arrivée', [0, 1]], [' hier.', []]],
  );
  assert.equal(pickXrayMark([0, 1], null, overlap, both), 1, 'the narrowest mark first');
  assert.equal(pickXrayMark([0, 1], 1, overlap, both), 0, 'a second tap cycles');

  assert.equal(usableXray({ sentence, marks }), true);
  assert.equal(usableXray({ sentence, marks: [marks[2]] }), false);
  assert.equal(usableXray(null), false);
});

test('the x-ray sentence underlines each mark and reads out the first one', () => {
  const html = renderToStaticMarkup(
    React.createElement(XraySentence, {
      language: 'fr',
      xray: {
        sentence: 'Je ne bois que du thé le matin.',
        marks: [
          { token: 'ne...que', role: 'restriction', explanation: 'ne…que = only' },
          { token: 'du thé', role: 'article_kept', explanation: 'article stays' },
        ],
      },
    }),
  );
  assert.match(html, /La phrase aux rayons X/);
  assert.match(html, /<p class="xr-sentence" lang="fr">Je <span class="xr-seg" data-on="true" style="box-shadow:0 4px 0 var\(--xr-red\)/);
  assert.equal((html.match(/class="xr-seg"/g) || []).length, 3, 'ne, que, du thé');
  assert.match(html, /var\(--xr-blue\)/);
  assert.match(html, /<span class="xr-key__token" lang="fr">ne … que<\/span>/);
  assert.match(html, /aria-pressed="true"/);
  assert.match(html, /<p class="xr-note__role">Restriction<\/p>/);
  assert.match(html, /ne…que = only/);
  assert.equal(renderToStaticMarkup(React.createElement(XraySentence, { language: 'en', xray: null })), '');
});

test('the x-ray and the card depth are drawn with av2 tokens only', () => {
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles', 'atelier-v2.css'), 'utf8');
  const block = css.slice(css.indexOf('F-1 (content program 2026-10-03)'), css.indexOf('.av2 .rc-done'));
  assert.ok(block.length > 500);
  assert.doesNotMatch(block, /#[0-9a-f]{3,6}\b/i);
  assert.doesNotMatch(block, /font-family|text-transform:\s*uppercase/);
});
