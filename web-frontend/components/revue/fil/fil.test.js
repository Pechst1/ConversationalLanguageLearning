// node --test components/revue/fil/fil.test.js
//
// «Le fil» (WIRE §10, owner 2026-11-20), the client:
//
//   1. the model: the shown step never ahead of the server's, the strips moved without
//      drag, the order's reason built from the strips' own names (never the solution),
//      a miss said with the word's gloss, the A1 sentence as the server builds it, the
//      sequence words a free telling uses;
//   2. the wire: real views (fixtures/fil-sessions.json, dumped from the backend's
//      loop) parsed; the order's solution absent until resolved; act bodies in snake_case;
//   3. the player rendered from those views at A1 (en), A2 (de) and B1 (en): one chrome
//      language, at most two buttons in a foot, no solution before the retry, Romy's marks
//      on the learner's own words, «La page» with the wire in order.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render, fixture } = setup;
const visibleText = (html) => setup.visibleText(html.replace(/<style[\s\S]*?<\/style>/g, ' '));

const types = require('../../../lib/revue-types.ts');
const filTypes = require('../../../lib/revue-fil-types.ts');
const { parseFilResult } = require('../../../lib/revue-api.ts');
const model = require('./fil-model.ts');
const { filCopy } = require('./fil-copy.ts');
const { RvFil } = require('../index.ts');

const SESSIONS = fixture('fil-sessions');
const session = (name) => types.parseSessionView(SESSIONS[name]);
const screen = (name) => render(h(RvFil, { client: {}, session: session(name), onExit: () => {}, onReleve: () => {} }));

function footButtons(html) {
  const foot = html.slice(html.lastIndexOf('class="rv-foot'));
  return (foot.match(/<button/g) || []).length;
}

// ---------------------------------------------------------------------------
// 1. The model
// ---------------------------------------------------------------------------

test('the shown step is never ahead of the server, and «Raconter» holds «Voir la page»', () => {
  assert.equal(model.openingStep({ step: 'words' }, false), 'words');
  assert.equal(model.openingStep({ step: 'page' }, false), 'tell');
  assert.equal(model.openingStep({ step: 'order' }, true), 'page');
  assert.equal(model.clampStep({ step: 'order' }, 'tell', false), 'order');
  assert.equal(model.clampStep({ step: 'tell' }, 'order', false), 'order');
  assert.equal(model.nextStep('order'), 'words');
});

test('the strips move without drag: swap two, or one place up or down', () => {
  assert.deepEqual(model.swap(['a', 'b', 'c', 'd'], 0, 3), ['d', 'b', 'c', 'a']);
  assert.deepEqual(model.move(['a', 'b', 'c', 'd'], 1, -1), ['b', 'a', 'c', 'd']);
  assert.deepEqual(model.move(['a', 'b', 'c', 'd'], 3, 1), ['a', 'b', 'c', 'd'], 'the last one stays');
});

test("the order's reason names two strips by their own names, in the chrome language", () => {
  const strips = [
    { key: 'a', text: { fr: 'Le vote a lieu le 12 mars.', tr: 'The vote takes place on 12 March.' }, label: { fr: 'le vote', tr: 'the vote' } },
    { key: 'b', text: { fr: 'La mairie annonce le projet le 3 mars.', tr: null }, label: null },
  ];
  const hint = { key: 'a', afterKey: 'b' };
  assert.equal(model.orderHintText(filCopy('en'), strips, hint, 'en'), 'The vote comes after « La mairie annonce le projet… ».');
  assert.equal(model.orderHintText(filCopy('fr'), strips, hint, 'fr'), 'Le vote vient après « La mairie annonce le projet… ».');
  strips[1].label = { fr: "l'annonce", tr: 'die Ankündigung' };
  strips[0].label = { fr: 'le vote', tr: 'die Abstimmung' };
  assert.equal(model.orderHintText(filCopy('de'), strips, hint, 'de'), 'Die Abstimmung kommt nach die Ankündigung.');
});

test('a miss says what the word means and what the strip needs', () => {
  const miss = { position: 0, id: 'enfin', fr: 'enfin', tr: 'finally', role: 'last', needs: 'first' };
  assert.equal(model.missText(filCopy('en'), miss), '«enfin» means “finally”: it closes the story. This dispatch needs a word that opens the story.');
  assert.equal(
    model.missText(filCopy('de'), { ...miss, tr: 'schließlich' }),
    '«enfin» heißt „schließlich“: Es schließt die Geschichte ab. Diese Meldung braucht ein Wort, das die Geschichte eröffnet.',
  );
});

test("A1's sentence builds as the server builds it; a free telling counts its sequence words", () => {
  assert.equal(
    model.a1Telling({ fr: "d'abord" }, 'le baccalauréat naît en 1808', { fr: 'enfin' }, 'le Grand oral compte moins en 2027'),
    "D'abord, le baccalauréat naît en 1808. Enfin, le Grand oral compte moins en 2027.",
  );
  assert.equal(model.a1Telling({ fr: "d'abord" }, 'la mairie annonce', null, null), "D'abord, la mairie annonce.");
  const words = [{ fr: "tout d'abord" }, { fr: "d'abord" }, { fr: 'par la suite' }, { fr: 'puis' }];
  assert.deepEqual(model.connectorsUsed("Tout d'abord, le bac naît. Par la suite, il change.", words), ["tout d'abord", 'par la suite']);
  assert.deepEqual(model.connectorsUsed('Depuis 1808, le bac existe.', words), [], '«puis» inside «depuis» is not one');
});

// ---------------------------------------------------------------------------
// 2. The wire
// ---------------------------------------------------------------------------

test('a fil session parses with its view, and the order has no solution before it is resolved', () => {
  const s = session('a1_order');
  assert.equal(s.mode, 'fil');
  assert.equal(s.comptoir, null);
  assert.deepEqual(s.fil.steps, ['read', 'order', 'words', 'tell', 'page']);
  assert.equal(s.fil.step, 'order');
  assert.deepEqual(s.fil.order.strips.map((strip) => strip.key), ['a', 'b', 'c', 'd']);
  assert.deepEqual(s.fil.order.solution, []);
  assert.equal(s.fil.words, null);
  const hinted = session('a1_order_hint').fil.order;
  assert.equal(hinted.tries, 1);
  assert.ok(hinted.hint && hinted.hint.key && hinted.hint.afterKey);
  assert.deepEqual(hinted.solution, []);
  const page = session('a1_page');
  assert.equal(page.closing.filPage.strips.length, 4);
  assert.equal(page.closing.comptoirPage, null);
  assert.equal(page.artifact.kind, 'fil');
});

test('acts go out in snake_case and a refusal comes back with its code', () => {
  assert.deepEqual(filTypes.filBodyWire({ act: 'order', order: ['b', 'a', 'c', 'd'] }), { act: 'order', order: ['b', 'a', 'c', 'd'] });
  assert.deepEqual(filTypes.filBodyWire({ act: 'tell', texts: ['x', 'y'], mode: 'voice' }), { act: 'tell', texts: ['x', 'y'], mode: 'voice' });
  assert.deepEqual(filTypes.filBodyWire({ act: 'tell_fix', value: 'romy' }), { act: 'tell_fix', value: 'romy' });
  const result = parseFilResult({ session: SESSIONS.a1_tell, error: { code: 'tell_order', key: 'a', after_key: 'b' } });
  assert.deepEqual(result.error, { code: 'tell_order', key: 'a', afterKey: 'b', count: null });
  assert.equal(parseFilResult({ session: SESSIONS.a1_tell, error: null }).error, null);
  assert.ok(types.RV_MADE_KINDS.includes('fil'));
});

// ---------------------------------------------------------------------------
// 3. The player
// ---------------------------------------------------------------------------

const GERMAN_CHROME = /\b(Weiter|Wörter prüfen|Reihenfolge prüfen|Übersetzen|Meine Geschichte senden)\b/;
const ENGLISH_CHROME = /\b(Continue|Check the words|Check the order|Translate|Send my story)\b/;

test('A1 (en): read, order with arrows, a reason after a wrong order, never the solution', () => {
  let html = screen('a1_read');
  let text = visibleText(html);
  assert.match(text, /Au fil/);
  assert.match(text, /What happened|Ce qui s'est passé|Ce qui s’est passé/);
  assert.ok(footButtons(html) <= 2);

  html = screen('a1_order');
  text = visibleText(html);
  assert.match(text, /Les dépêches sont tombées dans le désordre/);
  assert.match(html, /aria-label="Move up"/);
  assert.match(text, /Check the order/);
  assert.match(text, /Try 1 of 2/);
  assert.doesNotMatch(text, /Here is the right order|right order\./);
  assert.ok(footButtons(html) <= 2);
  assert.doesNotMatch(text, GERMAN_CHROME);

  html = screen('a1_order_hint');
  text = visibleText(html);
  assert.match(text, /The first exam comes after the creation\./);
  assert.match(html, /data-misplaced/);
  assert.match(text, /Try 2 of 2/);
  assert.doesNotMatch(text, /Here is the right order/);
});

test('A1 (en): the words placed, a miss explained with its gloss, then the tiles', () => {
  let html = screen('a1_words');
  let text = visibleText(html);
  assert.match(text, /Put a word on each dispatch/);
  assert.match(html, /class="fl-slot"/);
  assert.doesNotMatch(text, /finally/, 'no gloss before a try');

  html = screen('a1_words_miss');
  text = visibleText(html);
  assert.match(text, /«enfin» means “finally”: it closes the story\. This dispatch needs a word that opens the story\./);
  assert.doesNotMatch(text, /Here are the right words/);

  html = screen('a1_tell');
  text = visibleText(html);
  assert.match(text, /Sentence 1/);
  assert.match(text, /le baccalauréat naît en 1808/);
  assert.match(text, /Send my story/);
  assert.ok(footButtons(html) <= 2);

  html = screen('a1_told');
  text = visibleText(html);
  assert.match(text, /D'abord, le baccalauréat naît en 1808\. Enfin, le Grand oral compte moins en 2027\./);
  assert.match(text, /See the page/);
});

test('A1 (en): «La page» prints the wire in order and the telling under «Toi»', () => {
  const html = screen('a1_page');
  const text = visibleText(html);
  assert.match(text, /Le fil de Romy/);
  assert.match(html, /class="fl-wire__word">D&#x27;abord|class="fl-wire__word">D'abord/);
  assert.ok(text.indexOf('1808') < text.indexOf('2027'), 'in true order');
  assert.match(text, /Toi · Dans le journal/, 'tiles: Romy did not read them');
  assert.ok(footButtons(html) <= 2);
});

test('A2 (de): three words per strip, the frames, and Romy marks without the answer', () => {
  let html = screen('a2_words');
  let text = visibleText(html);
  assert.match(text, /Wörter prüfen/);
  assert.equal((html.match(/class="fl-option"/g) || []).length, 12);
  assert.doesNotMatch(text, ENGLISH_CHROME);

  html = screen('a2_tell');
  text = visibleText(html);
  assert.match(text, /D'abord, le baccalauréat…/);
  assert.match(text, /Enfin, le Grand oral…/);
  assert.match(text, /Meine Geschichte senden/);

  html = screen('a2_marked');
  text = visibleText(html);
  assert.match(text, /Presque/);
  assert.match(html, /<mark class="ct-mark" data-kind="accord">il<\/mark>/);
  assert.match(text, /il · Angleichung/);
  assert.doesNotMatch(text, /ils sont/, 'no solution before the retry');
  assert.ok(footButtons(html) <= 2);
});

test('B1 (en): the chrome is French from B1; free telling with the sequence words shown and counted', () => {
  const html = screen('b1_tell');
  const text = visibleText(html);
  assert.match(text, /avec au moins 2 de ces mots/);
  assert.equal((text.match(/avec au moins 2 de ces mots/g) || []).length, 1, 'said once');
  assert.match(text, /tout d'abord/);
  assert.match(text, /0 mot\(s\) du fil sur 2/);
  assert.doesNotMatch(text, ENGLISH_CHROME);
  assert.ok(footButtons(html) <= 2);
});
