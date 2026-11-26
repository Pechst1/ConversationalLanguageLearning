// node --test components/cahiers/journal-scene-reveal.test.js
//
// #1081 — live walk 26 Nov. «The scene as it was» printed «Dix heures», «Dix heures»,
// «« Dix heures »»: the page title as heading, setup and line. «What you remember» quoted
// four people's lines glued as one. The card prints the title once, as its heading, and
// each line once under the person who said it.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { cahierCopy } = require('./cahier-copy.ts');
const journal = require('./JournalTab.tsx');

const count = (html, text) => html.split(text).length - 1;

test('#1081 · the title is a heading only, printed once', () => {
  const t = cahierCopy('en').journal;
  // A reveal stored before the fix: the title in every field.
  const html = renderToStaticMarkup(
    React.createElement(journal.SceneReveal, {
      reveal: { title_fr: 'Dix heures', setup_fr: 'Dix heures', character_line_fr: 'Dix heures' },
      t,
    }),
  );
  assert.equal(count(html, 'Dix heures'), 1, html);
  assert.match(html, /<h2[^>]*>Dix heures<\/h2>/);
});

test('#1081 · each line once, under its own speaker', () => {
  const t = cahierCopy('en').journal;
  const html = renderToStaticMarkup(
    React.createElement(journal.SceneReveal, {
      reveal: {
        title_fr: 'Dix heures',
        lines: [
          { speaker_name: 'Margaux', text_fr: 'Tu as peur de Marchand.' },
          { speaker_name: 'Romy', text_fr: 'Merci.' },
          { speaker_name: 'Romy', text_fr: 'Merci.' },
          { speaker_name: 'Camille', text_fr: 'Et Marchand signe à dix heures.' },
        ],
      },
      t,
    }),
  );
  assert.equal(count(html, 'Merci.'), 1, html);
  assert.ok(html.includes('Camille : « Et Marchand signe à dix heures. »'), html);
  assert.ok(html.includes('Margaux : « Tu as peur de Marchand. »'), html);
  assert.ok(!html.includes('Merci. Merci.'), html);
});

test('#1081 · a missed detail is quoted with who said it', () => {
  assert.equal(journal.saidBy('Margaux', 'Pas ce soir.'), 'Margaux : « Pas ce soir. »');
  assert.equal(journal.saidBy(null, 'Le livre est sur la table.'), 'Le livre est sur la table.');
});
