// node --test components/atelier-v2/home/quartier-door.test.js
//
// Le Quartier's door on Home: a build made with NEXT_PUBLIC_QUARTIER_VISIBLE=true (the owner's
// phone) draws one quiet chip to /quartier, with the day plan or without it. The public build
// draws none (home.test.js).

process.env.NEXT_PUBLIC_QUARTIER_VISIBLE = 'true';

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { HomeScreen } = require('./HomeScreen.tsx');
const { dayMarkState } = require('../journey/day-mark.ts');

const h = React.createElement;

const home = (language, props = {}) =>
  renderToStaticMarkup(
    h(HomeScreen, {
      dateLabel: 'mardi 23 septembre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      language,
      tiles: [],
      ...props,
    }),
  );

test('the owner’s build has one door to Le Quartier, with the day plan or without it', () => {
  for (const language of ['en', 'de', 'fr']) {
    for (const html of [home(language, { day: dayMarkState(null, language) }), home(language)]) {
      assert.equal((html.match(/href="\/quartier"/g) || []).length, 1, `${language}: one door`);
      assert.match(html, /data-chip="quartier"/);
      assert.match(html, /aria-label="(Entrer dans|Enter|Le Quartier betreten)/);
    }
  }
});
