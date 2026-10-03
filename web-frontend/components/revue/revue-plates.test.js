// node --test components/revue/revue-plates.test.js
//
// WP-119 phase 4 «Les planches» · the second plate (§12.7).
//
//   1. the wire's `plate_url_second` / `plate_switched` parse, and an older stage
//      without them parses to exactly what it did (nothing invented);
//   2. `stagePlateUrl`: the site until the switch; the second view once the server
//      says so, once a guest has entered in the thread, or while making; never
//      without a second view;
//   3. RvStage shows the second plate after a switch and keeps the cast in place.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render } = require('./revue-test-setup');

const types = require('../../lib/revue-types.ts');
const { RvStage, stageCast, stagePlateUrl } = require('./RvStage.tsx');

const SITE = '/assets/serial/locations/marche_canal.webp';
const SECOND = '/media/graphic-novel/revue-plates/cafe_rue_aligre-0123456789abcdef.webp';
const RAW = {
  place_id: 'marche_aligre',
  place_fr: "Le marché d'Aligre, un matin",
  plate_url: SITE,
  plate_place_id: 'marche_canal',
  place_is_real: false,
  dress: 'coat',
  cast: [
    { id: 'romy_tremblay', hold: 'notebook' },
    { id: 'user', hold: null },
  ],
};
const at = '2026-10-01T09:00:00+02:00';
const GUEST_ENTERS = { id: '5.g', seq: 5, at, kind: 'guest', castId: 'margaux_barman', textFr: 'Ça me regarde.', move: 'enter', position: null, reasonFr: null };

test('the second plate parses, and an older stage gains no field', () => {
  const stage = types.parseStage({ ...RAW, plate_url_second: SECOND, plate_switched: true });
  assert.equal(stage.plateUrlSecond, SECOND);
  assert.equal(stage.plateSwitched, true);
  const old = types.parseStage(RAW);
  assert.equal('plateUrlSecond' in old, false);
  assert.equal('plateSwitched' in old, false);
});

test('stagePlateUrl switches at the guest, at make or on the server word, and only with a second view', () => {
  const stage = types.parseStage({ ...RAW, plate_url_second: SECOND, plate_switched: false });
  assert.equal(stagePlateUrl(stage, []), SITE);
  assert.equal(stagePlateUrl(stage, [GUEST_ENTERS]), SECOND);
  assert.equal(stagePlateUrl(stage, [{ ...GUEST_ENTERS, move: 'follow_up' }]), SITE);
  assert.equal(stagePlateUrl(stage, [], true), SECOND);
  assert.equal(stagePlateUrl({ ...stage, plateSwitched: true }, []), SECOND);
  assert.equal(stagePlateUrl(types.parseStage(RAW), [GUEST_ENTERS], true), SITE);
});

test('RvStage shows the second plate after a switch and keeps the cast', () => {
  const stage = types.parseStage({ ...RAW, plate_url_second: SECOND, plate_switched: true });
  const cast = stageCast([
    { id: 'romy_tremblay', hold: 'notebook' },
    { id: 'margaux_barman', hold: null },
  ]);
  const before = render(h(RvStage, { plateUrl: stage.plateUrl, size: 'band', cast, you: { outfit: 'coat' } }));
  const after = render(h(RvStage, { plateUrl: stagePlateUrl(stage, [GUEST_ENTERS]), size: 'band', cast, you: { outfit: 'coat' } }));
  assert.match(before, new RegExp(`src="${SITE}"`));
  assert.match(after, new RegExp(`src="${SECOND.replace(/[.]/g, '\\.')}"`));
  assert.doesNotMatch(after, new RegExp(SITE));
  // Everything but the plate is the same markup: the cast does not move.
  const strip = (html) => html.replace(/<img[^>]*class="rv-stage__plate[^"]*"[^>]*>/g, '');
  assert.equal(strip(after), strip(before));
  assert.match(after, /margaux_barman|margaux/);
});
