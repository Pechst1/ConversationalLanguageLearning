// node --test components/lexique/recall-ladder.test.js — WP-115b, the drill's side.
const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.resolve(__dirname, '../../node_modules/sucrase/register/ts'));
const ladder = require('./recall-ladder.ts');

test('the server’s rung is the card’s mode', () => {
  assert.equal(ladder.ladderRung({ ladder: 'production' }, false), 'production');
  assert.equal(ladder.ladderRung({ ladder: 'audio' }, false), 'audio');
  assert.equal(ladder.ladderRung(null, false), null, 'an older server: the page decides');
});

test('a cloze or a scene that cannot be blanked is asked as production', () => {
  assert.equal(ladder.ladderRung({ ladder: 'cloze' }, false), 'production');
  assert.equal(ladder.ladderRung({ ladder: 'cloze' }, true), 'cloze');
  assert.equal(ladder.ladderRung({ ladder: 'scene', scene_cue: { sentence_fr: 'Tu as vu la _____ ?' } }, false), 'scene');
  assert.equal(ladder.ladderRung({ ladder: 'scene', scene_cue: null }, false), 'production');
});

test('a stubborn word is rescued with its cue', () => {
  const item = { ladder: 'rescue', rescue_cue: { sentence_fr: null, first_letter: 's', length: 7 } };
  assert.equal(ladder.ladderRung(item, false), 'rescue');
  assert.deepEqual(ladder.ladderCue(item), { sentence_fr: null, first_letter: 's', length: 7 });
});

test('an answered card reports how it was answered', () => {
  assert.equal(ladder.gradedFormat('production', false), 'typed');
  assert.equal(ladder.gradedFormat('scene', false), 'cloze');
  assert.equal(ladder.gradedFormat('rescue', true), 'spoken');
});

test('successive relearning: wrong goes to the end, right leaves the loop', () => {
  assert.deepEqual(ladder.nextAgainQueue([], 4, true), [4]);
  assert.deepEqual(ladder.nextAgainQueue([4, 7], 4, true), [7, 4]);
  assert.deepEqual(ladder.nextAgainQueue([7, 4], 4, false), [7]);
});

test('a line card blanks the form in the line and hints the lemma (owner 2026-10-08)', () => {
  const cue = { sentence_fr: "Vous _____ d'où ?", expected_fr: 'venez', hint_fr: 'venir' };
  assert.equal(ladder.linePrompt(cue), "Vous _____ d'où ? (venir)");
  assert.equal(ladder.linePrompt({ sentence_fr: 'Tu as vu la _____ ?', hint_fr: null }), 'Tu as vu la _____ ?');
  assert.equal(ladder.linePrompt(null), '');
  assert.equal(ladder.lineAnswer('scene', cue, 'venir'), 'venez');
  assert.equal(ladder.lineAnswer('production', cue, 'venir'), 'venir', 'context-free rungs keep the lemma');
  assert.equal(ladder.lineAnswer('scene', { sentence_fr: 'x _____' }, 'venir'), 'venir', 'an older server');
});

test('the device folds a line answer with or without its elided clitic', () => {
  assert.equal(ladder.matchesLineForm('venez', 'venez'), true);
  assert.equal(ladder.matchesLineForm('venir', 'venez'), false);
  assert.equal(ladder.matchesLineForm('j etais', 'etais'), true);
  assert.equal(ladder.matchesLineForm('nous etais', 'etais'), false);
  assert.equal(ladder.matchesLineForm('', 'etais'), false);
});
