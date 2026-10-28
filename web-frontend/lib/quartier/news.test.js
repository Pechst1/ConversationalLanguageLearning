// node --test lib/quartier/news.test.js
//
// Le Quartier · the news on the map. `world/news.json` is written by `scripts/forge/forge.py news`
// from the Papier's articles (`app/services/revue/**/*.json`): every place an article names with
// an exact position in Paris, once, from the newest article that names it. These tests read the
// articles again and hold the file to them, so an article that names a new place puts its pin
// on the map in the same change; and the map shows each such place, under scaffolding until the
// forge has built it.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { NEWS, WORLD, mapPlaces } = require('./world.ts');

// the forge's PARIS_BOX: Paris inside the périphérique, give or take
const PARIS = { lon: [2.224, 2.47], lat: [48.815, 48.902] };

function articles(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((e) => (e.isDirectory() ? articles(path.join(dir, e.name)) : e.name.endsWith('.json') ? [path.join(dir, e.name)] : []))
    .sort();
}

function expected() {
  const best = new Map();
  articles(path.join(REPO, 'app', 'services', 'revue')).forEach((file) => {
    let d;
    try {
      d = JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch {
      return;
    }
    if (!d || typeof d !== 'object' || Array.isArray(d)) return;
    (d.places || []).forEach((p) => {
      const g = p.geo || {};
      if (!p.id || g.lat == null || g.lon == null || g.precision !== 'exact') return;
      if (g.lon < PARIS.lon[0] || g.lon > PARIS.lon[1] || g.lat < PARIS.lat[0] || g.lat > PARIS.lat[1]) return;
      const week = d.week || '';
      const had = best.get(p.id);
      if (had && !(week > (had.article.week || ''))) return;
      best.set(p.id, {
        id: p.id,
        name_fr: p.name_fr,
        lat: g.lat,
        lon: g.lon,
        article: { id: d.id, title_fr: d.title_fr, week: d.week ?? null, topic: d.topic ?? null },
      });
    });
  });
  const key = (n) => `${n.article.week || ''}\u0000${n.id}`;
  return Array.from(best.values()).sort((a, b) => (key(a) < key(b) ? 1 : key(a) > key(b) ? -1 : 0));
}

test('the news layer names every place the Papier puts in Paris (run `forge.py news` after an article changes)', () => {
  assert.deepEqual(NEWS, expected());
});

test('every news place is on the map, open once the forge has built it and under scaffolding until then', () => {
  const pins = mapPlaces();
  assert.equal(new Set(pins.map((p) => p.id)).size, pins.length, 'a place is pinned once');
  NEWS.forEach((n) => {
    const pin = pins.find((p) => p.id === n.id);
    assert.ok(pin, `${n.id} is not on the map`);
    const known = WORLD.places.find((p) => p.id === n.id);
    if (known) assert.equal(pin, known, `${n.id}: the registry's entry wins`);
    else {
      assert.equal(pin.status, 'en_chantier', `${n.id} is not built yet`);
      assert.equal(pin.kind, 'news');
      assert.equal(pin.site, null);
      assert.match(pin.why.fr, new RegExp(n.article.title_fr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    }
  });
});
