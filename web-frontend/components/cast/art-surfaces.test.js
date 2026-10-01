/* WP-116 phase 2 · every face goes through the art-set switch.
 *   node --test components/cast/art-surfaces.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

require('../../node_modules/sucrase/register/ts');
require('../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../..');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const flags = require('../../launch-flags.json');

function withArtSet(value, fn) {
  const before = flags.artSet;
  flags.artSet = value;
  try {
    return fn();
  } finally {
    flags.artSet = before;
  }
}

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    if (name === 'node_modules' || name.startsWith('.') || name === '__fixtures__') continue;
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx$/.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

/** Files allowed to build painted face URLs without the switch: the builders themselves. */
const ALLOWED = new Set([
  // `leadPortraitUrl` is computed but rendered nowhere.
  'pages/atelier.tsx',
]);

test('no screen shows a painted face without going through the art-set switch', () => {
  const offenders = [];
  for (const file of [...walk(path.join(ROOT, 'components')), ...walk(path.join(ROOT, 'pages'))]) {
    const rel = path.relative(ROOT, file);
    if (ALLOWED.has(rel)) continue;
    const source = fs.readFileSync(file, 'utf8');
    const paintsFaces = /faceSrcFor\(|portraitSrc\(|model_sheet_url|portrait_url/.test(source);
    if (paintsFaces && !/useArtSet\(/.test(source)) offenders.push(rel);
  }
  assert.deepEqual(offenders, [], 'route these faces through useArtSet() and CastFace');
});

test('CastPortrait and the av2 Portrait draw the rig in the drawn set, the photo in the painted one', () => {
  const { CastPortrait } = require('../atelier-v2/ui/CastPortrait.tsx');
  const { Portrait } = require('../atelier-v2/ui/Feedback.tsx');
  const painted = withArtSet('painted', () => renderToStaticMarkup(React.createElement(CastPortrait, { characterId: 'romy_tremblay', name: 'Romy', mood: 'happy' })));
  assert.match(painted, /portrait-happy\.webp/);
  assert.doesNotMatch(painted, /cast-rig/);
  const drawn = withArtSet('drawn', () => renderToStaticMarkup(React.createElement(CastPortrait, { characterId: 'romy_tremblay', name: 'Romy', mood: 'happy' })));
  assert.match(drawn, /data-cast="romy_tremblay"/);
  assert.match(drawn, /data-mood="ravie"/);
  assert.doesNotMatch(drawn, /\.webp/);
  const disc = withArtSet('drawn', () => renderToStaticMarkup(React.createElement(Portrait, { name: 'Marin', mood: 'moved' })));
  assert.match(disc, /data-cast="marin_leveque"/);
  assert.match(disc, /data-mood="emue"/);
});

test('Odile gets a drawn face; Camille only once the learner has chosen; a minor character keeps the initial', () => {
  const { CastPortrait } = require('../atelier-v2/ui/CastPortrait.tsx');
  const { rememberCastVariants } = require('../../lib/cast-variants.ts');
  const render = (props) => withArtSet('drawn', () => renderToStaticMarkup(React.createElement(CastPortrait, props)));
  assert.match(render({ characterId: 'odile', name: 'Odile' }), /data-cast="odile_ferrand"/);
  const before = render({ characterId: 'camille', name: 'Camille Marchand' });
  assert.doesNotMatch(before, /cast-rig/, 'no face before T1 Day B');
  assert.doesNotMatch(before, /landlord_marchand/, 'never the grandfather');
  rememberCastVariants({ camille_marchand: 'm' });
  assert.match(render({ characterId: 'camille', name: 'Camille Marchand' }), /data-cast="camille_marchand"/);
  assert.doesNotMatch(render({ characterId: 'bastien_roux', name: 'Bastien Roux' }), /cast-rig/);
});

test('the trombinoscope card shows the rig in the mood they feel about you', () => {
  const { CastCard } = require('../feuilleton/archive/Trombinoscope.tsx');
  const member = { id: 'lila_bonnet', name: 'Lila Bonnet', role: 'Institutrice', relationship: { mood: 2 } };
  const drawn = withArtSet('drawn', () => renderToStaticMarkup(React.createElement(CastCard, { member })));
  assert.match(drawn, /data-cast="lila_bonnet"/);
  assert.match(drawn, /data-mood="ravie"/);
  const painted = withArtSet('painted', () => renderToStaticMarkup(React.createElement(CastCard, { member })));
  assert.match(painted, /lila_bonnet\/portrait-happy\.webp/);
});
