// node --test lib/rule-montage.test.js
//
// Le Montage's script: the sentence each tap makes, the people in it, and the language of its lines.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const { montageFor, montageSentence, montageSeen, MONTAGE_COPY } = require('./rule-montage.ts');

const script = montageFor('FR2_A21_PC_ETRE');
const UNITS = [
  'FR2_A21_PC_ETRE', 'FR2_A21_PC_PRONOMINAL', 'FR2_A21_PC_NEGATION', 'FR2_A21_COD',
  // Step 3: ten A1/A2 rules.
  'FR2_A11_ADJ_AGREEMENT', 'FR2_A11_NEGATION', 'FR2_A11_CONTRACTIONS', 'FR2_A11_POSSESSIVES', 'FR2_A12_FUTUR_PROCHE',
  'FR2_A11_PARTITIVE', 'FR2_A21_PC_AVOIR', 'FR2_A21_COI', 'FR2_A21_Y_PLACE', 'FR2_A21_EN_QUANTITY',
];
const scripts = UNITS.map((unit) => montageFor(unit));

test('the pilot rule, step 2 and step 3 have a Montage, nothing else', () => {
  scripts.forEach((each, index) => assert.equal(each?.unit, UNITS[index]));
  assert.equal(montageFor('FR2_A11_ETRE'), null);
  assert.equal(montageFor('FR2_A22_IMPARFAIT'), null);
  assert.equal(montageFor(null), null);
});

test('step 2: each Montage builds its rule card, one tap at a time', () => {
  const sentences = (unit) => {
    const each = montageFor(unit);
    return [each.start, ...each.beats.map((beat) => beat.then)].map(montageSentence);
  };
  assert.deepEqual(sentences('FR2_A21_PC_PRONOMINAL'), [
    'Ce matin, Marin a réveillé Lila.',
    'Ce matin, Marin s’a réveillé.',
    'Ce matin, Marin s’est réveillé.',
    'Ce matin, Lila s’est réveillé.',
    'Ce matin, Romy et Margaux se sont réveillé.',
  ]);
  const pronominal = montageFor('FR2_A21_PC_PRONOMINAL');
  assert.equal(pronominal.beats[2].thread.prints.text, 'réveillé[e]');
  assert.equal(pronominal.beats[3].thread.prints.text, 'réveillé[es]');
  // The one wrong sentence on the way («s’a») is struck, and the next tap is on it.
  assert.equal(pronominal.beats[0].then.find((token) => token.k === 'h-a').off, true);
  assert.equal(pronominal.beats[1].tap.k, 'h-a');

  assert.deepEqual(sentences('FR2_A21_PC_NEGATION'), [
    'Hier, Gus a vu le film.',
    'Hier, Gus n’a vu le film.',
    'Hier, Gus n’a pas vu le film.',
    'Hier, Gus n’est pas parti.',
    'Gus n’est jamais parti.',
  ]);
  assert.deepEqual(sentences('FR2_A21_COD'), [
    'Romy regarde le film.',
    'Romy le regarde.',
    'Romy la regarde.',
    'Romy les regarde.',
    'Romy l’adore.',
  ]);
  // The object pronoun stays in the present, as its card does: no participle to agree.
  assert.ok(montageFor('FR2_A21_COD').beats.every((beat) => !beat.thread));
});

const sentencesOf = (unit) => {
  const each = montageFor(unit);
  return [each.start, ...each.beats.map((beat) => beat.then)].map(montageSentence);
};

test('step 3: each Montage builds its rule card, one tap at a time', () => {
  assert.deepEqual(sentencesOf('FR2_A11_ADJ_AGREEMENT'), [
    'Gus prend un café noir.',
    'Lila prend un café noir.',
    'Lila prend une tasse noir.',
    'Lila prend deux tasses noire.',
    'Lila prend deux petites tasses noires.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A11_NEGATION'), [
    'Margaux boit du café.',
    'Margaux ne boit du café.',
    'Margaux ne boit pas du café.',
    'Margaux ne boit pas de café.',
    'Margaux n’aime pas le café.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A11_CONTRACTIONS'), [
    'Marin va à la gare.',
    'Marin va à le marché.',
    'Marin va au marché.',
    'Marin rentre du marché.',
    'Marin rentre de la poste.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A11_POSSESSIVES'), [
    'Gus cherche son téléphone.',
    'Romy cherche son téléphone.',
    'Romy cherche sa clé.',
    'Romy cherche ses clés.',
    'Romy cherche sa adresse.',
    'Romy cherche son adresse.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A12_FUTUR_PROCHE'), [
    'Ce soir, Romy dîne chez Margaux.',
    'Ce soir, Romy va dîne chez Margaux.',
    'Ce soir, Romy va dîner chez Margaux.',
    'Ce soir, Gus et Romy vont dîner chez Margaux.',
    'Ce soir, Gus et Romy ne vont pas dîner chez Margaux.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A11_PARTITIVE'), [
    'Margaux aime le pain.',
    'Margaux prend de le pain.',
    'Margaux prend du pain.',
    'Margaux prend de la soupe.',
    'Margaux prend de l’eau.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A21_PC_AVOIR'), [
    'Gus mange une pizza.',
    'Hier, Gus a manger une pizza.',
    'Hier, Gus a mangé une pizza.',
    'Hier, Gus a fini le projet.',
    'Hier, Gus a attendu Romy.',
    'Hier, Gus a pris le train.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A21_COI'), [
    'Lila téléphone à Marin.',
    'Lila lui téléphone.',
    'Lila lui téléphone.',
    'Lila leur téléphone.',
    'Lila leur écrit.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A21_Y_PLACE'), [
    'Margaux va au marché.',
    'Margaux y va.',
    'Margaux y va.',
    'Margaux n’y va pas.',
    'Margaux ne va pas y aller.',
  ]);
  assert.deepEqual(sentencesOf('FR2_A21_EN_QUANTITY'), [
    'Lila prend des pommes.',
    'Lila en prend.',
    'Lila en prend un kilo.',
    'Lila en prend deux.',
    'Lila en a acheté deux.',
  ]);
  const adj = montageFor('FR2_A11_ADJ_AGREEMENT');
  assert.deepEqual(adj.beats.map((beat) => beat.thread?.prints?.text ?? null), [null, 'noir[e]', 'noire[s]', null]);
  assert.equal(adj.beats[0].thread.blocked, true, 'the person does not decide');
});

test('step 3: every wrong sentence on the way is struck, and the next tap takes it away', () => {
  const struck = { FR2_A11_NEGATION: 'a-du', FR2_A11_CONTRACTIONS: 'p-ale', FR2_A11_POSSESSIVES: 'p-sa2', FR2_A12_FUTUR_PROCHE: 'v-dine', FR2_A11_PARTITIVE: 'a-dele', FR2_A21_PC_AVOIR: 'v-mange' };
  Object.keys(struck).forEach((unit) => {
    const beats = montageFor(unit).beats;
    const at = beats.findIndex((beat) => beat.then.some((token) => token.off));
    assert.ok(at >= 0, unit);
    assert.equal(beats[at].then.find((token) => token.off).k, struck[unit], unit);
    assert.equal(beats[at].wobble, struck[unit], unit);
    assert.deepEqual(beats[at + 1].tap, { kind: 'token', k: struck[unit] }, unit);
    assert.ok(!beats[at + 1].then.some((token) => token.off), unit);
  });
});

test('no ask gives its answer away in French', () => {
  scripts.forEach((each) => each.beats.forEach((beat, index) => {
    const next = beat.then.filter((token) => /\[/.test(token.text)).flatMap((token) => token.text.replace(/[[\]]/g, '').split(' '));
    // What the learner already sees, word by word, and the tile in their hand are not a giveaway.
    const seen = (index ? each.beats[index - 1].then : each.start).flatMap((token) => token.text.replace(/[[\]]/g, '').split(' '));
    next.filter((word) => !seen.includes(word) && !(beat.tap.label || '').split(/[\s…]+/).includes(word)).forEach((word) => {
      assert.ok(!new RegExp(`(^|[^\\p{L}])${word}([^\\p{L}]|$)`, 'u').test(beat.ask.fr), `${each.unit} beat ${index + 1}: «${word}» in «${beat.ask.fr}»`);
    });
  }));
});

test('five taps build the rule on Gus and Romy', () => {
  assert.equal(montageSentence(script.start), 'Hier, Gus ___ mangé.');
  assert.deepEqual(script.beats.map((beat) => montageSentence(beat.then)), [
    'Hier, Gus a mangé.',
    'Hier, Gus a parti.',
    'Hier, Gus est parti.',
    'Hier, Romy est parti.',
    'Hier, Romy a mangé.',
  ]);
  const prints = script.beats[3].thread.prints;
  assert.equal(prints.text, 'parti[e]');
  assert.equal(script.beats[4].thread.blocked, true);
});

test('the one wrong sentence on the way is the one that says it is wrong', () => {
  const beat = script.beats[1];
  assert.equal(beat.then.find((token) => token.k === 'h-a').off, true);
  assert.equal(script.beats[2].tap.k, 'h-a');
});

test('every word a beat refers to is in its sentence', () => scripts.forEach((script) => {
  let current = script.start;
  script.beats.forEach((beat) => {
    if (beat.tap.kind === 'token') assert.ok(current.some((token) => token.k === beat.tap.k));
    const keys = beat.then.map((token) => token.k);
    if (beat.flyInto) assert.ok(keys.includes(beat.flyInto));
    if (beat.wobble) assert.ok(keys.includes(beat.wobble));
    (beat.thread?.through ?? []).forEach((key) => assert.ok(keys.includes(key), key));
    if (beat.thread?.prints) assert.ok(keys.includes(beat.thread.prints.k));
    current = beat.then;
  });
}));

test('every line exists in all three languages', () => {
  assert.equal(script.beats.flatMap((beat) => [beat.ask, beat.say].filter(Boolean)).length, 9);
  scripts.flatMap((each) => each.beats.flatMap((beat) => [beat.ask, beat.say].filter(Boolean))).forEach((line) => {
    for (const language of ['en', 'de', 'fr']) assert.ok(line[language]?.trim(), JSON.stringify(line));
  });
  for (const language of ['en', 'de', 'fr']) assert.ok(MONTAGE_COPY[language].skip && MONTAGE_COPY[language].replay);
});

test('the examples are about people in the cast, and the agreement is right', () => {
  assert.deepEqual(script.examples.map((example) => example.fr), [
    'Gus [est] parti à huit heures.',
    'Romy [est] parti[e] à huit heures.',
    'Romy [a] mangé au Mistral.',
  ]);
  const coaches = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, '..', 'app/data/forge_coaches.json'), 'utf8')).cast;
  scripts.forEach((each) => {
    const people = [each.subject, ...each.examples.map((example) => example.cast), ...each.beats.flatMap((beat) => [beat.subject, beat.tap.cast].filter(Boolean))];
    people.forEach((cast) => assert.equal(coaches[cast.id]?.name, cast.name, `${each.unit}: ${cast.id}`));
    assert.equal(each.examples.length, 3);
    each.examples.forEach((example) => assert.match(example.fr, /\[[^\]]+\]/, 'an example marks its rule'));
  });
});

test('with no storage it has not been seen', () => {
  assert.equal(montageSeen('FR2_A21_PC_ETRE'), false);
});
