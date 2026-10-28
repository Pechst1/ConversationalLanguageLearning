// node --test lib/quartier/site.test.js
//
// Le Quartier · the places the forge built. A site file is written by `scripts/forge`, which the
// app's CI does not run, so these tests hold every file in `world/sites` to the forge's own checks
// (`draft.py check`): you start, the stalls stand and the crowd goes on ground you can walk; the
// shops carry a trade's name and never a real business's; the people the brief names stand at a
// stall of what they sell, dressed from the avatar kit. And the world registry agrees with the
// files: a place is open on the map only with a site behind it, and every site loads.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const REPO = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { SLOT_OPTIONS } = require('../avatar.ts');
const { TRADES } = require('./market-talk.ts');
const { WORLD } = require('./world.ts');

const SITES = path.join(__dirname, 'world', 'sites');
const files = fs.readdirSync(SITES).filter((f) => f.endsWith('.json'));
const sites = files.map((f) => ({ file: f, site: JSON.parse(fs.readFileSync(path.join(SITES, f), 'utf8')) }));

// the forge's generic fascias: the first name of each trade in draft.py's TRADES
const DRAFT = fs.readFileSync(path.join(REPO, 'scripts', 'forge', 'draft.py'), 'utf8');
const FASCIAS = new Set(Array.from(DRAFT.matchAll(/^\s+"[a-z_]+": \("([^"]+)",/gm), (m) => m[1]));

function inRing(x, z, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, zi] = ring[i];
    const [xj, zj] = ring[j];
    if (zi > z !== zj > z && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}

const onWalk = (site, [x, z]) => site.walk.some((p) => inRing(x, z, p.outer) && !p.holes.some((h) => inRing(x, z, h)));

function edgeDistance(site, [x, z]) {
  let best = Infinity;
  site.walk.forEach((p) =>
    [p.outer, ...p.holes].forEach((ring) => {
      for (let i = 0; i < ring.length; i++) {
        const [ax, az] = ring[i];
        const [bx, bz] = ring[(i + 1) % ring.length];
        const dx = bx - ax;
        const dz = bz - az;
        const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1)));
        best = Math.min(best, Math.hypot(x - (ax + dx * t), z - (az + dz * t)));
      }
    }),
  );
  return best;
}

const words = (w) => Boolean(w && w.fr && w.en && w.de);

test('there is at least one forged place, and every site names itself after its file', () => {
  assert.ok(sites.length >= 1);
  sites.forEach(({ file, site }) => {
    assert.equal(`${site.id}.json`, file);
    assert.equal(site.version, 1, file);
    assert.ok(words(site.title) && words(site.can_do), `${file}: title and can_do in three languages`);
    assert.ok(site.radius.walk < site.radius.build, `${file}: built beyond where you can walk`);
  });
});

test('you start, the stalls stand and the crowd goes on ground you can walk', () => {
  sites.forEach(({ file, site }) => {
    assert.ok(site.walk.length, `${file}: no walkable ground`);
    assert.ok(onWalk(site, site.start.pos), `${file}: the start is off the walkable ground`);
    site.stalls.forEach((s) => assert.ok(onWalk(site, s.c), `${file}: stall at ${s.c} off the walkable ground`));
    site.spots.forEach((s) => assert.ok(onWalk(site, s.at), `${file}: crowd spot ${s.at} off the walkable ground`));
    site.people.forEach((p) => assert.ok(onWalk(site, p.pos) || edgeDistance(site, p.pos) < 0.5, `${file}: ${p.key} stands off the walkable ground`));
  });
});

test('the buildings are of the kit’s styles, and every shop carries a trade’s name, never a business’s', () => {
  sites.forEach(({ file, site }) => {
    assert.ok(FASCIAS.size > 10, 'read the trades from draft.py');
    site.buildings.forEach((b, i) => {
      assert.ok(['haussmann', 'faubourg', 'moderne'].indexOf(b.style) >= 0, `${file}: building ${i} is ${b.style}`);
      assert.equal(b.street.length, b.fp.length, `${file}: building ${i} flags each edge`);
      (b.runs || []).forEach((r) =>
        r.shops.forEach((s) => {
          if (s.name) assert.ok(FASCIAS.has(s.name), `${file}: fascia «${s.name}» is not a generic trade`);
        }),
      );
    });
    site.plaques.forEach((p) => assert.ok(site.buildings[p.b] && p.e < site.buildings[p.b].fp.length, `${file}: plaque «${p.text}» on a wall that is not there`));
  });
});

test('the people the brief names stand at a stall of what they sell, dressed from the avatar kit', () => {
  sites.forEach(({ file, site }) => {
    const keys = site.people.map((p) => p.key);
    assert.equal(new Set(keys).size, keys.length, `${file}: two people with one key`);
    site.people.forEach((p) => {
      assert.ok(words(p.name), `${file}: ${p.key} has a name in three languages`);
      if (p.goal) assert.ok(words(p.goal), `${file}: ${p.key}'s errand in three languages`);
      if (p.goods) {
        assert.ok(Object.keys(TRADES).some((t) => TRADES[t].goods.indexOf(p.goods) >= 0), `${file}: nobody's trade sells ${p.goods}`);
        if (p.in) {
          const hall = site.landmarks.find((l) => l.name === p.in);
          assert.ok(hall && hall.kind === 'halle', `${file}: ${p.key} works in «${p.in}», which is not a hall here`);
        } else {
          const near = site.stalls.filter((s) => s.goods === p.goods && Math.hypot(s.c[0] - p.pos[0], s.c[1] - p.pos[1]) < 3);
          assert.ok(near.length, `${file}: ${p.key} stands at no stall of ${p.goods}`);
        }
      }
      Object.keys(p.look || {}).forEach((slot) => {
        const v = p.look[slot];
        if (typeof v === 'boolean') return;
        assert.ok(SLOT_OPTIONS[slot], `${file}: ${p.key} wears «${slot}», which is not a slot of the avatar kit`);
        assert.ok(SLOT_OPTIONS[slot].indexOf(v) >= 0, `${file}: ${p.key}'s ${slot} «${v}» is not in the kit`);
      });
    });
  });
});

test('every site says where its data came from, and the Papier article it was forged for exists', () => {
  sites.forEach(({ file, site }) => {
    assert.match(site.provenance.data || '', /Overture/, `${file}: attribution`);
    assert.ok(site.provenance.release, `${file}: data release`);
    if (site.provenance.papier) {
      // an evergreen article, or a week's
      const revue = path.join(REPO, 'app', 'services', 'revue');
      const weeks = fs.readdirSync(path.join(revue, 'weekly')).map((wk) => path.join(revue, 'weekly', wk));
      const found = [path.join(revue, 'evergreen')].concat(weeks).some((dir) => fs.existsSync(path.join(dir, `${site.provenance.papier}.json`)));
      assert.ok(found, `${file}: no Papier article ${site.provenance.papier}`);
    }
  });
});

test('the map and the files agree: a place is open with a site behind it, and every site loads', () => {
  const index = fs.readFileSync(path.join(SITES, 'index.ts'), 'utf8');
  WORLD.places.forEach((p) => {
    if (p.site) {
      assert.equal(p.status, 'open', `${p.id} has a site but is ${p.status}`);
      assert.ok(files.indexOf(`${p.site}.json`) >= 0, `${p.id}: no file for site ${p.site}`);
    }
    if (p.status === 'open') assert.ok(p.site || p.kind === 'home', `${p.id} is open with nothing built`);
    if (p.site && p.kind !== 'home') assert.ok(words(p.ride), `${p.id}: how you get there from the quai`);
  });
  sites.forEach(({ site }) => {
    assert.ok(index.indexOf(`  ${site.id}: () => import('./${site.id}.json')`) >= 0, `sites/index.ts does not load ${site.id}`);
    assert.ok(
      WORLD.places.some((p) => p.id === site.id),
      `${site.id} is not in the world registry`,
    );
  });
});

test('a venue stands its set beside its walkable ground: the stand behind, the track before, the people on it', () => {
  sites
    .filter(({ site }) => site.venue)
    .forEach(({ file, site }) => {
      const v = site.venue;
      assert.equal(v.kind, 'hippodrome', `${file}: a venue the kit draws`);
      assert.ok(Math.abs(Math.hypot(v.u[0], v.u[1]) - 1) < 1e-3 && Math.abs(Math.hypot(v.n[0], v.n[1]) - 1) < 1e-3, `${file}: unit axes`);
      assert.ok(Math.abs(v.u[0] * v.n[0] + v.u[1] * v.n[1]) < 1e-3, `${file}: the straight runs square to the way across`);
      // the walkable ground lies between the stand's front and the rail
      const across = ([x, z]) => (x - v.post[0]) * v.n[0] + (z - v.post[1]) * v.n[1];
      site.walk.forEach((p) => p.outer.forEach((pt) => assert.ok(across(pt) <= 0 && across(pt) >= -(v.lawn + v.esplanade) - 0.01, `${file}: walkable ground at ${pt} is on the track or in the stand`)));
      assert.ok(v.race.runners >= 2 && v.race.runners <= 16 && v.race.metres > 0, `${file}: a race to run`);
      assert.deepEqual(site.people.map((p) => p.key).sort(), ['guichetiere', 'habitue'], `${file}: the clerk at the window and the regular at the rail`);
    });
});
