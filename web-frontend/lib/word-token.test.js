// node --test lib/word-token.test.js
//
// WP-D6 — the gender is the shape.
//
//   1. the three shapes are pinned: feminine noun = circle, masculine noun =
//      square, anything else = triangle — with the article inside and the
//      accessible name «féminin» / «masculin» / «verbe»;
//   2. «l'addition» reads «féminin» with the elided article;
//   3. colour is the learner state, never the gender;
//   4. nothing is guessed: no stored gender → a plain ink token, no article;
//   5. the stylesheet draws the shapes with --av2 tokens only, never outlined;
//   6. the three surfaces use the token.

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
const { WordToken } = require('@/components/atelier-v2/ui/WordToken');
const { wordTokenModel, articleFor, normalizeGender, wordTokenTone } = require('./word-token');

const render = (props) => renderToStaticMarkup(React.createElement(WordToken, props));

test('the three shapes are pinned', () => {
  assert.equal(
    render({ word: 'table', gender: 'f', partOfSpeech: 'noun', state: 'learning' }),
    '<span class="av2-word-token" data-shape="feminine" data-tone="learning" role="img" aria-label="féminin">'
      + '<span class="av2-word-token__article" aria-hidden="true">la</span></span>',
  );
  assert.equal(
    render({ word: 'pain', gender: 'm', partOfSpeech: 'noun', state: 'new' }),
    '<span class="av2-word-token" data-shape="masculine" data-tone="new" role="img" aria-label="masculin">'
      + '<span class="av2-word-token__article" aria-hidden="true">le</span></span>',
  );
  assert.equal(
    render({ word: 'manger', partOfSpeech: 'verb', state: 'mastered' }),
    '<span class="av2-word-token" data-shape="other" data-tone="known" role="img" aria-label="verbe"></span>',
  );
});

test("«l'addition» reads «féminin»", () => {
  for (const word of ["l'addition", 'l’addition', 'addition']) {
    const model = wordTokenModel({ word, gender: 'f', partOfSpeech: 'noun' });
    assert.equal(model.shape, 'feminine', word);
    assert.equal(model.label, 'féminin', word);
    assert.equal(model.article, 'l’', word);
  }
  const html = render({ word: "l'addition", gender: 'f' });
  assert.match(html, /aria-label="féminin"/);
  assert.match(html, />l’<\/span>/);
});

test('articles: elision, h muet, h aspiré, a written article wins', () => {
  assert.equal(articleFor('homme', 'm'), 'l’');
  assert.equal(articleFor('heure', 'f'), 'l’');
  assert.equal(articleFor('été', 'm'), 'l’');
  assert.equal(articleFor('haricot', 'm'), 'le');
  assert.equal(articleFor('honte', 'f'), 'la');
  assert.equal(articleFor('la gare', 'f'), 'la');
  assert.equal(articleFor('gare', 'f'), 'la');
  assert.equal(articleFor('frère', 'm'), 'le');
});

test('gender is stored values only; colour is state only', () => {
  assert.equal(normalizeGender('f'), 'f');
  assert.equal(normalizeGender('feminine'), 'f');
  assert.equal(normalizeGender('M'), 'm');
  assert.equal(normalizeGender('m/f'), null);
  assert.equal(normalizeGender(''), null);
  assert.equal(normalizeGender(null), null);

  // Same state, two genders → same tone. Same gender, three states → three tones.
  const fem = wordTokenModel({ word: 'gare', gender: 'f', state: 'due' });
  const masc = wordTokenModel({ word: 'train', gender: 'm', state: 'due' });
  assert.equal(fem.tone, masc.tone);
  assert.deepEqual(
    ['new', 'building', 'mastered'].map((state) => wordTokenModel({ word: 'gare', gender: 'f', state }).tone),
    ['new', 'learning', 'known'],
  );
  assert.equal(wordTokenTone('holding'), 'known');
  assert.equal(wordTokenTone('fraying'), 'learning');
});

test('nothing is guessed: no stored gender is a plain ink token', () => {
  // «hiver» is a noun, but without a stored gender it gets no shape and no article.
  const noun = wordTokenModel({ word: 'hiver', gender: null, partOfSpeech: 'noun', state: 'new' });
  assert.equal(noun.shape, 'plain');
  assert.equal(noun.article, '');
  assert.doesNotMatch(noun.label, /féminin|masculin/);

  const unknown = render({ word: 'gare', gender: null, partOfSpeech: 'x' });
  assert.match(unknown, /data-shape="plain"/);
  assert.match(unknown, /aria-hidden="true"/);
  assert.doesNotMatch(unknown, /role="img"/);
  assert.match(unknown, />G<\/span>/);
});

test('the stylesheet: shapes by radius and clip-path, --av2 tokens only, never outlined', () => {
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');
  const block = css.slice(css.indexOf('/* WP-D6 (begin)'), css.indexOf('/* WP-D6 (end) */'));
  assert.ok(block.length > 100, 'the WP-D6 block exists');
  assert.match(block, /\[data-shape='feminine'\] \{ border-radius: var\(--av2-r-pill\); \}/);
  assert.match(block, /\[data-shape='masculine'\] \{ border-radius: 8px; \}/);
  assert.match(block, /\[data-shape='other'\] \{[^}]*clip-path: polygon\(50% 0, 100% 100%, 0 100%\)/);
  assert.doesNotMatch(block, /#[0-9a-fA-F]{3,8}\b/, 'no raw colours');
  assert.doesNotMatch(block, /\b(border|outline|stroke|box-shadow)\s*:/, 'shapes are never outlined');
  for (const match of block.matchAll(/var\((--[a-z0-9-]+)\)/g)) {
    assert.ok(match[1].startsWith('--av2-'), `${match[1]} is an --av2 token`);
  }
  for (const line of block.split('\n').filter((l) => l.trim().startsWith('.'))) {
    assert.ok(line.trim().startsWith('.av2 '), `scoped: ${line}`);
  }
});

test('the Lexique list, Mots du jour and the word sheet use the token', () => {
  const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
  const lexique = read('pages/vocabulary.tsx');
  assert.match(lexique, /<WordToken word=\{word\} gender=\{gender\}/);
  assert.match(lexique, /gender=\{item\.gender\}/);
  assert.match(read('components/lexique/MotsDuJour.tsx'), /gender=\{entry\.gender\}/);
  assert.match(read('components/mobile/WordBiographySheet.tsx'), /gender=\{biography\.word\.gender\}/);
});
