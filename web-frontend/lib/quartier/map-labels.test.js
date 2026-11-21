// node --test lib/quartier/map-labels.test.js
//
// P12 stage 6 · La Carte's names. Observed 17 Nov (`quartier-q-roam-map-all.png`): in «Tout Paris»
// «L'hippodrome de ParisLongchamp» ran over «L'hémicycle de l'Assemblée nationale» and the mairie
// over the gare; in «Ton quartier» (the default) names ran off the right edge. On a phone 375 px
// wide the frame is square (`.qz-map-frame`: aspect-ratio 1, max-height 54vh = 438 px > its
// width), so the map's own units are the screen's, up to scale: the test holds the layout there.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function alias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) return resolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolve.call(this, request, ...rest);
};

const { projectPoint } = require('@/components/carte/carte-projection');
const { mapPlaces } = require('./world.ts');
const { LABEL, placeLabels, shortName, textWidth } = require('./map-labels.ts');
const { WHOLE_BOX, labelsFor, quarterBox } = require('@/components/quartier/QuartierMap.tsx');

const pins = () =>
  mapPlaces()
    .map((p) => ({ p, xy: projectPoint('paris', p.lat, p.lon) }))
    .filter((x) => x.xy);

const overlap = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

/** What the map drew before: every name to the right of its pin, at full length. */
function naive(list, box) {
  const u = box[2] / 100;
  const size = LABEL.size * u;
  return list.map(({ p, xy }) => {
    const x0 = xy[0] + LABEL.gap * u;
    return { id: p.id, text: p.name.fr, rect: [x0, xy[1] - size * 0.6, x0 + textWidth(p.name.fr, size), xy[1] + size * 0.6] };
  });
}

function problems(labels, box) {
  const out = [];
  labels.forEach((a, i) =>
    labels.slice(i + 1).forEach((b) => {
      if (overlap(a.rect, b.rect)) out.push(`«${a.text}» runs over «${b.text}»`);
    }),
  );
  for (const l of labels) {
    if (l.rect[0] < box[0] || l.rect[1] < box[1] || l.rect[2] > box[0] + box[2] || l.rect[3] > box[1] + box[3]) out.push(`«${l.text}» runs past the edge`);
  }
  return out;
}

for (const [zoom, boxOf] of [
  ['Ton quartier (the default)', (list) => quarterBox(list.map((x) => x.xy))],
  ['Tout Paris', () => WHOLE_BOX],
]) {
  test(`${zoom}: no name runs over another or past the frame`, () => {
    const list = pins();
    const box = boxOf(list);
    // the fault, as drawn before: names overlap or leave the frame
    assert.ok(problems(naive(list, box), box).length, 'the old layout is clean here: the test would hold nothing');
    const labels = labelsFor(list, box, 'quai_de_valmy');
    assert.deepEqual(problems(labels, box), []);
    // where you are always has its name, and so does every open place on the default map
    const named = new Set(labels.map((l) => l.id));
    assert.ok(named.has('quai_de_valmy'));
    if (zoom.startsWith('Ton')) for (const { p } of list.filter((x) => x.p.status === 'open')) assert.ok(named.has(p.id), `${p.id} has no name`);
  });
}

test('a long name gives up its complement before it is cut, and a cut name says so', () => {
  assert.equal(shortName("L'hippodrome de ParisLongchamp"), "L'hippodrome");
  assert.equal(shortName('La mairie du 10e'), 'La mairie');
  assert.equal(shortName("L'hémicycle de l'Assemblée nationale"), "L'hémicycle");
  assert.equal(shortName('Le quai de Valmy'), 'Le quai');
  assert.equal(shortName('Montmartre'), null);
  // a pin at the frame's right edge: the name goes to its left
  const box = [0, 0, 100, 100];
  const [l] = placeLabels([{ id: 'a', name: 'Le marché d’Aligre', xy: [95, 50], rank: 0 }], box, 1);
  assert.equal(l.anchor, 'end');
  // two pins on top of each other: the second name goes elsewhere, never over the first
  const two = placeLabels(
    [
      { id: 'a', name: 'La gare de l’Est', xy: [50, 50], rank: 0 },
      { id: 'b', name: 'La mairie du 10e', xy: [50, 53], rank: 1 },
    ],
    box,
    1,
  );
  assert.equal(two.length, 2);
  assert.ok(!overlap(two[0].rect, two[1].rect));
});
