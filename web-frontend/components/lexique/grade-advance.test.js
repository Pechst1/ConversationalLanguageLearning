// node --test components/lexique/grade-advance.test.js
//
// Owner, 1 Nov: «wenn ich auf „Weiß ich“ gehe, bleibt die Karte trotzdem da und ich komme
// nicht weiter». The deck filed a card only after the server had answered its review, so a
// slow or failed request kept the card on screen with the grade buttons disabled. Every
// grade now goes through one path that files the card at once; the server's answer can
// only move it into or out of «ask again».
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

require(path.resolve(__dirname, '../../node_modules/sucrase/register/ts'));
const deck = require('./deck-session.ts');

const ORDER = [{ word_id: 11 }, { word_id: 12 }, { word_id: 13 }];
const head = (progress) => deck.remainingCards(ORDER, progress)[0]?.word_id ?? null;
const remaining = (progress) => deck.remainingCards(ORDER, progress).map((item) => item.word_id);

// Every grade the page offers: Encore 0, Dur 1, «Weiß ich» 2, Facile 3 on a self-rated
// card, and the graded card's one «Weiter» (right or wrong by the typed answer).
const GRADES = [
  { label: 'Encore', rating: 0, graded: false, typedMatches: false },
  { label: 'Dur', rating: 1, graded: false, typedMatches: false },
  { label: 'Weiß ich', rating: 2, graded: false, typedMatches: false },
  { label: 'Facile', rating: 3, graded: false, typedMatches: false },
  { label: 'Weiter (right)', rating: 2, graded: true, typedMatches: true },
  { label: 'Weiter (wrong)', rating: 0, graded: true, typedMatches: false },
];

test('a grade on an unturned card turns it; on a turned card it files', () => {
  for (const grade of GRADES) {
    assert.deepEqual(deck.gradeAction({ ...grade, revealed: false }), { kind: 'reveal' }, grade.label);
    const action = deck.gradeAction({ ...grade, revealed: true });
    assert.equal(action.kind, 'file', grade.label);
    assert.equal(action.rating, grade.rating);
  }
});

test('every grade moves the deck on at once, before the server answers', () => {
  for (const grade of GRADES) {
    const action = deck.gradeAction({ ...grade, revealed: true });
    const after = deck.fileCard(deck.EMPTY_PROGRESS, 11, action.wrong);
    assert.equal(head(after), 12, `${grade.label}: the next card is on screen`);
    const right = !(grade.graded ? !grade.typedMatches : grade.rating === 0);
    assert.equal(remaining(after).includes(11), !right, `${grade.label}: ${right ? 'gone' : 'asked again at the end'}`);
  }
  const know = deck.fileCard(deck.EMPTY_PROGRESS, 11, deck.gradeAction({ ...GRADES[2], revealed: true }).wrong);
  assert.deepEqual(remaining(know), [12, 13], '«Weiß ich» takes the card off the deck');
});

test('the server’s verdict only settles «ask again»; a failed save never holds the deck', () => {
  const filed = deck.fileCard(deck.EMPTY_PROGRESS, 11, false);
  assert.deepEqual(remaining(deck.settleVerdict(filed, 11, true)), [12, 13, 11], 'judged wrong: again at the end');
  assert.equal(deck.settleVerdict(filed, 11, false), filed, 'judged right: nothing changes');
  const wrongFirst = deck.fileCard(deck.EMPTY_PROGRESS, 11, true);
  assert.deepEqual(remaining(deck.settleVerdict(wrongFirst, 11, false)), [12, 13], 'the device said wrong, the server right');
  assert.equal(deck.settleVerdict(deck.EMPTY_PROGRESS, 11, true), deck.EMPTY_PROGRESS, 'an unfiled card is untouched');
  const lost = deck.reviewNotSaved(filed, 11);
  assert.equal(head(lost), 12, 'not saved: the deck still moves on');
  assert.deepEqual(remaining(lost), [12, 13, 11], 'and the card comes back at the end');
});

test('the review page files through the one path, never after awaiting the server', () => {
  const page = fs.readFileSync(path.join(__dirname, '..', '..', 'pages', 'vocabulary', 'review.tsx'), 'utf8');
  assert.doesNotMatch(page, /await apiService\.submitAnkiReview/, 'the deck never waits for the review to land');
  assert.doesNotMatch(page, /disabled=\{reviewing\}/, 'no grade button is held while a review is in flight');
  const body = page.slice(page.indexOf('const fileGrade = '), page.indexOf('const returnToAtelier'));
  assert.ok(body.indexOf('fileCard(') >= 0 && body.indexOf('fileCard(') < body.indexOf('submitAnkiReview('), 'filed before it is sent');
  const grades = page.match(/onClick=\{\(\) => [^}]*\}/g).filter((handler) => /Rating|submit|fileGrade/.test(handler));
  assert.ok(grades.length >= 4, grades.join('\n'));
  for (const handler of grades) assert.match(handler, /handleRatingClick\(/, handler);
  assert.match(page, /gradeAction\(\{ revealed, rating, graded, typedMatches \}\)/);
});
