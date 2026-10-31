// node --test components/courrier/courrier-busy.test.js
//
// #337 — «New letter» after a finished letter took ~20 s (a paid generation)
// during which the finished letter stayed on screen with a button that only
// dimmed. The press must say, in words, that a letter is being written, and a
// second press must be ignored until the letter exists.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
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

const { CrGhost } = require('./Courrier.tsx');
const { courrierCopy } = require('./courrier-copy.ts');
const { AtelierV2Root } = require('@/components/atelier-v2/ui/AtelierV2Root.tsx');

const h = React.createElement;
const decode = (s) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"');
const render = (language, element) => decode(renderToStaticMarkup(h(AtelierV2Root, { language }, element)));

test('a pending CrGhost says what is happening, is busy and is really disabled', () => {
  for (const language of ['fr', 'en', 'de']) {
    const t = courrierCopy(language);
    const opening = t.new_courrier_opening;
    // On the unfixed code there is no such sentence: the press can only dim.
    assert.ok(opening && opening !== t.new_courrier, `${language}: a «writing your letter» sentence exists`);
    const html = render(
      language,
      h(CrGhost, { primary: true, pending: true, pendingLabel: opening, disabled: true }, t.new_courrier),
    );
    assert.match(html, /aria-busy="true"/, `${language}: aria-busy`);
    assert.match(html, /disabled=""/, `${language}: really disabled`);
    assert.ok(html.includes(opening), `${language}: shows ${opening}`);
    assert.ok(!html.includes(`<span>${t.new_courrier}</span>`), `${language}: no longer says «${t.new_courrier}»`);
  }
});

test('an idle CrGhost keeps its label and is not busy', () => {
  const t = courrierCopy('en');
  const html = render('en', h(CrGhost, { primary: true, pendingLabel: t.new_courrier_opening }, t.new_courrier));
  assert.ok(!/aria-busy/.test(html));
  assert.ok(html.includes(t.new_courrier));
});

test('every «New letter» press on the Courrier page shows the creating state and ignores a second tap', () => {
  const source = fs
    .readFileSync(path.join(WEB_ROOT, 'pages/missions.tsx'), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');
  const presses = source.match(/<CrGhost[^>]*onClick=\{startFreshMission\}[^>]*>/g) || [];
  assert.ok(presses.length >= 3, 'the finished, serial and lapsed screens each offer a new letter');
  for (const press of presses) {
    assert.match(press, /pending=\{creating\}/, `${press} shows the busy state`);
    assert.match(press, /pendingLabel=\{t\.new_courrier_opening\}/, `${press} says a letter is being written`);
  }
  const start = source.slice(source.indexOf('const startFreshMission'));
  const body = start.slice(0, start.indexOf('\n  };'));
  assert.match(body, /creatingRef\.current/, 'a second tap before the re-render is ignored');
});
