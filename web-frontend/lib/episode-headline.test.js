// node --test lib/episode-headline.test.js — WP-109: today's episode, headlined.
const assert = require('node:assert/strict');
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

const model = require('./episode-headline.ts');

const tentpole = {
  edition_no: 2, title_fr: 'La lettre', teaser_fr: 'Demain, Camille.', season_title_fr: 'La clé d’Odile',
  cast: [{ id: 'lila_bonnet', name: 'Lila Bonnet' }],
};

test('the kicker is the number and the season', () => {
  assert.equal(model.headlineKicker(tentpole), 'Nº 2 · La clé d’Odile');
  assert.equal(model.headlineKicker(null), '');
});

test('#314: a re-read day says so in the kicker, between the number and the season', () => {
  assert.equal(model.headlineKicker({ ...tentpole, reread: true }), 'Nº 2 · Relecture · La clé d’Odile');
  assert.equal(model.headlineKicker({ ...tentpole, reread: false }), 'Nº 2 · La clé d’Odile');
});

test('a known title leads; the teaser follows it', () => {
  assert.equal(model.headlineTitle(tentpole, 'Votre prochain chapitre'), 'La lettre');
  assert.equal(model.headlineTeaser(tentpole, 'La lettre'), 'Demain, Camille.');
});

test('a generated day not yet written: yesterday’s «À suivre…» leads, never twice', () => {
  const gap = { ...tentpole, title_fr: null };
  assert.equal(model.headlineTitle(gap, 'Votre prochain chapitre'), 'Demain, Camille.');
  assert.equal(model.headlineTeaser(gap, 'Demain, Camille.'), null);
  assert.equal(model.headlineTitle(gap, 'Un café au Mistral'), 'Un café au Mistral', 'a real scene title is kept');
});

test('one entry into today’s episode: start or resume the day', () => {
  assert.equal(model.TODAY_EPISODE_HREF, '/atelier?start=today');
});

test('the teaser does not say «À suivre…» twice', () => {
  const hooked = { ...tentpole, teaser_fr: 'Deux clés pour la même porte. À suivre…' };
  assert.equal(model.headlineTeaser(hooked, 'La lettre'), 'Deux clés pour la même porte.');
});

test('inside a gap with a destination, the kicker says where the week is going', () => {
  const day = {
    edition_no: 23,
    season_title_fr: 'La clé d’Odile',
    arc: { gap_title_fr: 'Avant la fête', title_fr: 'Les 25 ans du Mistral', when_fr: 'samedi', days_left: 3 },
  };
  assert.equal(model.headlineKicker(day, 'de'), 'Nº 23 · Avant la fête · noch 3 Tage bis Samstag');
  assert.equal(model.headlineKicker(day, 'en'), 'Nº 23 · Avant la fête · 3 days to Saturday');
  assert.equal(model.headlineKicker(day, 'fr'), 'Nº 23 · Avant la fête · samedi, dans 3 jours');
  const eve = { ...day, arc: { ...day.arc, days_left: 1 } };
  assert.equal(model.headlineKicker(eve, 'de'), 'Nº 23 · Avant la fête · morgen ist Samstag');
  assert.equal(model.headlineArc(eve, 'fr'), "Avant la fête · demain, c'est samedi");
});

test('without an arc the kicker is the season’s, as before', () => {
  const day = { edition_no: 7, season_title_fr: 'La clé d’Odile', arc: null };
  assert.equal(model.headlineKicker(day, 'de'), 'Nº 7 · La clé d’Odile');
  assert.equal(model.headlineArc(day, 'de'), '');
});
