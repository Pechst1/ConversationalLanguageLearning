// node --test lib/can-dos.test.js
//
// WP-94 «Numéro spécial» + WP-95 «Le Carnet» — the pure model:
//   1. the copy tables share keys and placeholders in en/de/fr;
//   2. a special edition is read from the snapshot, the envelope or the offer,
//      and its can-dos are listed in the chrome language;
//   3. the recap's épreuve moment: passed → the band just closed, failed → the
//      kind line and the date seven days on;
//   4. Home's level line is the next can-do, never a percentage (W12);
//   5. the Carnet: bands ordered, future ones locked, stamps with scene, face,
//      date and quote, and «Essayez-le pour de vrai» → Répétition.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const { CAN_DO_COPY_TABLES } = require('./can-do-copy.ts');
const m = require('./can-dos.ts');

const placeholders = (text) => (text.match(/\{\w+\}/g) || []).sort().join(',');

test('the copy tables share keys and placeholders', () => {
  const fr = CAN_DO_COPY_TABLES.fr;
  for (const language of ['en', 'de']) {
    const table = CAN_DO_COPY_TABLES[language];
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const key of Object.keys(fr)) {
      assert.equal(placeholders(table[key]), placeholders(fr[key]), `${language}.${key}`);
      assert.ok(table[key].trim(), `${language}.${key} is written`);
    }
  }
  // Place names are French in every column.
  for (const language of ['en', 'de', 'fr']) {
    assert.equal(CAN_DO_COPY_TABLES[language].special_kicker, 'Numéro spécial');
    assert.equal(CAN_DO_COPY_TABLES[language].carnet_name, 'Le Carnet');
  }
});

const CAN_DOS = [
  { id: 'cafe', title_fr: 'commander au café', title_native: 'order at a café' },
  { id: 'prix', title_fr: 'demander un prix et payer', title_native: 'ask a price and pay' },
  { id: 'soi', title_fr: 'se présenter', title_native: 'introduce yourself' },
  { id: 'heure', title_fr: 'dire l’heure', title_native: 'tell the time' },
];

test('a special edition is read wherever the server put it, and only when it is one', () => {
  const snapshot = { special: 'epreuve', epreuve: { band: 'A1.2', can_dos: CAN_DOS } };
  assert.deepEqual(m.epreuveOf(snapshot).band, 'A1.2');
  assert.equal(m.epreuveOf({ journey: snapshot }).canDos.length, 4);
  assert.equal(m.epreuveOf({ journey: null, available: { special: 'epreuve', epreuve: { band: 'A1.1', can_dos: [] } } }).band, 'A1.1');
  assert.equal(m.epreuveOf({ special: null }), null);
  assert.equal(m.epreuveOf({ journey: { id: 'x' } }), null, 'an older server: no special');
  assert.equal(m.epreuveOf(null), null);
  // Garbage can-dos are dropped, not guessed.
  assert.equal(m.epreuveOf({ special: 'epreuve', epreuve: { band: 'A1.1', can_dos: [{}, { id: 'a' }, CAN_DOS[0]] } }).canDos.length, 1);
});

test('the special list line is in the chrome language, at most three, then «…»', () => {
  assert.equal(
    m.specialListLine(CAN_DOS.slice(0, 2), 'fr'),
    'Aujourd’hui, montrez que vous savez : commander au café · demander un prix et payer',
  );
  assert.equal(m.specialListLine(CAN_DOS, 'en'), 'Today, show that you can: order at a café · ask a price and pay · introduce yourself · …');
  assert.match(m.specialListLine(CAN_DOS.slice(0, 1), 'de'), /^Heute zeigen Sie, was Sie können: order at a café$/);
  assert.equal(m.specialListLine([], 'fr'), null);
});

test('the recap: passed presses the band just closed; failed is kind and dated', () => {
  const journey = { local_date: '2026-09-28', special: 'epreuve', epreuve: { band: 'A1.2', can_dos: CAN_DOS } };
  const passed = m.epreuveRecapView(journey, { epreuve_result: 'passed', epreuve_line_fr: 'Bravo, toute la troupe !' }, 'fr');
  assert.equal(passed.result, 'passed');
  assert.equal(passed.band, 'A1.2');
  assert.equal(passed.title, 'A1.2, bouclé');
  assert.equal(passed.sealCaption, 'A1.2 · 28 sept.');
  assert.equal(passed.lineFr, 'Bravo, toute la troupe !');
  // Without the snapshot's band, the level-up's «from» is the band closed.
  const fromLevelUp = m.epreuveRecapView({ local_date: '2026-09-28' }, { epreuve_result: 'passed', level_up: { from_level: 'A1.1', to_level: 'A1.2' } }, 'en');
  assert.equal(fromLevelUp.band, 'A1.1');
  assert.equal(fromLevelUp.title, 'A1.1, closed');

  const failed = m.epreuveRecapView(journey, { epreuve_result: 'failed', epreuve_line_fr: null }, 'fr');
  assert.equal(failed.result, 'failed');
  assert.equal(failed.next, 'La prochaine édition spéciale : dans 7 jours (5 octobre)');
  assert.doesNotMatch(`${failed.title} ${failed.body}`, /échou|raté|dommage/i, 'no shame');
  assert.equal(m.epreuveRecapView(journey, { epreuve_result: 'failed' }, 'en').next, 'The next special edition: in 7 days (5 October)');
  assert.equal(m.epreuveRecapView({}, { epreuve_result: 'failed' }, 'fr').next, 'La prochaine édition spéciale : dans 7 jours');
  assert.equal(m.epreuveRecapView(journey, { epreuve_result: null }, 'fr'), null);
  assert.equal(m.epreuveRecapView(journey, {}, 'fr'), null, 'an older recap');
});

test('dates: «28 sept.», and seven days on across a month', () => {
  assert.equal(m.carnetDate('2026-09-28', 'fr'), '28 sept.');
  assert.equal(m.carnetDate('2026-09-28T09:14:00+00:00', 'fr'), '28 sept.');
  assert.match(m.carnetDate('2026-09-28', 'en'), /^28 Sept?$/);
  assert.match(m.carnetDate('2026-09-28', 'de'), /^28\. Sept\.?$/);
  assert.equal(m.carnetDate('not a date', 'fr'), null);
  assert.equal(m.carnetDate(null, 'fr'), null);
  assert.equal(m.dayAfter('2026-09-28', 7, 'fr'), '5 octobre');
  assert.equal(m.dayAfter('2026-12-29', 7, 'de'), '5. Januar');
});

test('Home: the next can-do replaces the percentage (W12)', () => {
  const payload = { coverage: { band: 'A1.1', percent: 0 }, next_can_do: { ...CAN_DOS[1], band: 'A1.1' }, can_dos_stamped: 0, can_dos_total: 12 };
  const read = m.nextCanDoOf(payload);
  assert.equal(read.next.id, 'prix');
  assert.equal(read.total, 12);
  const fr = m.nextStepView({ band: 'A1.1', ...read }, 'fr');
  assert.equal(fr.line, 'Prochaine étape : demander un prix et payer');
  assert.equal(fr.href, '/notebook?mode=carnet');
  assert.doesNotMatch(fr.line, /%/);
  assert.equal(m.nextStepView({ band: 'A1.1', ...read }, 'en').line, 'Next step: ask a price and pay');
  assert.equal(m.nextStepView({ band: 'A1.1', ...read }, 'de').ariaLabel, 'Niveau A1.1. Nächster Schritt: ask a price and pay. Carnet öffnen');
  // On the coverage instead of the top level.
  assert.equal(m.nextCanDoOf({ coverage: { band: 'A1.1', next_can_do: CAN_DOS[0] } }).next.id, 'cafe');
  // Several sources: the first that carries the field wins.
  assert.equal(m.nextCanDoOf(null, { cefr: { next_can_do: CAN_DOS[2] } }).next.id, 'soi');
  // All stamped: it says so.
  assert.equal(m.nextStepView({ band: 'A1.1', next: null, stamped: 12, total: 12 }, 'fr').line, 'Tout A1.1 est tamponné');
  // An older server: nothing.
  assert.deepEqual(m.nextCanDoOf({ coverage: { band: 'A1.1', percent: 60 } }), { next: null, stamped: null, total: null });
  assert.equal(m.nextStepView({ band: 'A1.1', next: null }, 'fr'), null);
});

const PAYLOAD = {
  current_band: 'A1.2',
  bands: [
    { band: 'A2.1', title_native: 'A2.1', can_dos: [{ id: 'z', title_fr: 'raconter sa journée', title_native: 'tell your day', stamped_at: null }] },
    {
      band: 'A1.2',
      title_native: 'A1.2',
      can_dos: [
        {
          ...CAN_DOS[0],
          stamped_at: '2026-09-28T09:14:00+00:00',
          source: 'scene',
          scene_id: 's1',
          scene_title_fr: 'Vous avez commandé au comptoir',
          character_id: 'margaux_barman',
          quote_fr: 'Un café, s’il vous plaît.',
        },
        { ...CAN_DOS[1], stamped_at: null, source: null },
        { ...CAN_DOS[2], stamped_at: '2026-09-20', source: 'authored', character_id: 'a_stranger' },
      ],
    },
    { band: 'A1.1', title_native: 'A1.1', can_dos: [{ ...CAN_DOS[3], stamped_at: '2026-09-10', source: 'epreuve' }] },
    'junk',
  ],
};

test('the Carnet: bands in order, the current one open, the future locked calmly', () => {
  const payload = m.readCanDos(PAYLOAD);
  assert.equal(payload.bands.length, 3, 'junk dropped');
  const model = m.carnetModel(payload, null, 'fr');
  assert.deepEqual(model.bands.map((b) => `${b.band}:${b.state}:${b.locked}`), ['A1.1:past:false', 'A1.2:current:false', 'A2.1:future:true']);
  assert.equal(model.selected.band, 'A1.2');
  assert.equal(model.selected.count, '2 sur 3 tamponnés');
  const [cafe, prix, soi] = model.selected.items;
  assert.equal(cafe.stamped, true);
  assert.equal(cafe.line, 'Vous avez commandé au comptoir — Margaux, 28 sept.');
  assert.equal(cafe.characterId, 'margaux_barman');
  assert.equal(cafe.quoteFr, 'Un café, s’il vous plaît.');
  assert.equal(cafe.ariaState, 'Tamponné le 28 sept.');
  assert.equal(cafe.rehearsalHref, '/repetition?situation=commander%20au%20caf%C3%A9');
  assert.equal(prix.stamped, false);
  assert.equal(prix.line, null);
  assert.equal(prix.ariaState, 'Pas encore tamponné');
  assert.ok(prix.rehearsalHref, 'an unstamped can-do can still be tried for real');
  // An unknown speaker gets no face and no invented name.
  assert.equal(soi.characterId, null);
  assert.equal(soi.line, 'premier jour — 20 sept.');

  const en = m.carnetModel(payload, 'A1.2', 'en');
  assert.equal(en.selected.items[0].title, 'order at a café');
  assert.equal(en.selected.items[0].rehearsalHref, '/repetition?situation=order%20at%20a%20caf%C3%A9');
  assert.equal(en.selected.count, '2 of 3 stamped');

  const future = m.carnetModel(payload, 'A2.1', 'fr');
  assert.equal(future.selected.locked, true);
  assert.equal(future.selected.lockedNote, 'A2.1 s’ouvre quand A1.2 est bouclé. Voici ce qui vous y attend.');
  assert.equal(future.selected.items[0].rehearsalHref, null);
  assert.equal(future.selected.count, 'Rien de tamponné pour l’instant');

  const past = m.carnetModel(payload, 'A1.1', 'fr');
  assert.equal(past.selected.items[0].line, 'numéro spécial — 10 sept.');

  // An unknown band falls back to the current one; nothing at all → no selection.
  assert.equal(m.carnetModel(payload, 'C2.9', 'fr').selected.band, 'A1.2');
  assert.equal(m.carnetModel(null, null, 'fr').selected, null);
  assert.equal(m.readCanDos({ nope: true }), null);
});

test('band ranks sort sub-bands', () => {
  assert.ok(m.bandRank('A1.1') < m.bandRank('A1.2'));
  assert.ok(m.bandRank('A1.2') < m.bandRank('A2.1'));
  assert.ok(m.bandRank('A2.2') < m.bandRank('B1.1'));
  assert.equal(m.bandRank('??'), Number.POSITIVE_INFINITY);
});
