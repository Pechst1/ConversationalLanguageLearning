// node --test components/radio/radio.test.js
//
// WP-122 A · La Radio, rendered and decided.
//
//   1. listen first: nothing of the text until the bulletin ends or «Lire»; the
//      play control is the one red press while the text is hidden;
//   2. after the end: the transcript with tap words, the dictée's line masked, the
//      journey's own Dictation mounted, «Vérifier» the one press; graded → the
//      mask lifts, «C'est entendu»;
//   3. a bulletin that cannot sound shows the text at once, no play, no dictée;
//   4. the player's machine, the hairline's weighting, who stands on the stage;
//   5. the client: a 404 is «off», a half-voiced bulletin is silence;
//   6. La Une: the chip «La Radio · 50 s», its place after the Revue chip, and
//      HomeScreen's budget with letter + Revue + Radio (+ words due).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const { h, render, visibleText, WEB_ROOT } = require('../revue/revue-test-setup');

const types = require('../../lib/radio-types.ts');
const { createRadioClient } = require('../../lib/radio-api.ts');
const { radioHomeChip, withRadioChip, radioChipSeconds } = require('../../lib/radio-une.ts');
const { radioCopy } = require('./radio-copy.ts');
const model = require('./radio-model.ts');
const { RadioSurface } = require('./RadioSurface.tsx');
const { mockBulletin, silentWavDataUri, createMockRadioClient } = require('./radio-mock.ts');
const { journeyCopy } = require('../atelier-v2/journey/journey-copy.ts');

const EN = radioCopy('en');
const FR = radioCopy('fr');

function surface(props = {}) {
  const bulletin = props.bulletin || mockBulletin();
  return render(
    h(RadioSurface, {
      bulletin,
      copy: EN,
      journeyCopy: journeyCopy('en'),
      language: 'en',
      phase: 'idle',
      index: 0,
      progress: 0,
      readRequested: false,
      onToggle: () => {},
      onRead: () => {},
      dicteeValue: '',
      onDicteeChange: () => {},
      onCheck: () => {},
      dicteeResult: null,
      onDone: () => {},
      onExit: () => {},
      onWord: () => {},
      ...props,
    }),
  );
}
const primaries = (html) => (html.match(/av2-btn--primary/g) || []).length;

// ---------------------------------------------------------------------------
// 1–3. The surface
// ---------------------------------------------------------------------------

test('listen first: the text is hidden until the end, and the play control is the one press', () => {
  const bulletin = mockBulletin();
  for (const phase of ['idle', 'loading', 'playing', 'paused']) {
    const html = surface({ phase, index: 2, progress: 0.4 });
    const text = visibleText(html);
    for (const line of bulletin.lines) assert.ok(!text.includes(line.textFr.slice(0, 30)), `${phase}: «${line.textFr.slice(0, 30)}» is hidden`);
    assert.match(html, /data-text="hidden"/);
    assert.doesNotMatch(html, /av2-dictation/, `${phase}: no dictée yet`);
    assert.equal(primaries(html), 1, `${phase}: one press`);
    assert.match(html, /class="av2-btn av2-btn--primary[^"]*"[^>]*data-radio-play=""/);
    assert.match(html, /class="radio__read"[^>]*>Lire</, 'the «Lire» door is there');
    assert.match(text, /Listen first\. The text comes after\./);
  }
  assert.match(visibleText(surface({ phase: 'idle' })), /Listen/);
  assert.match(visibleText(surface({ phase: 'playing' })), /Pause/);
  assert.match(visibleText(surface({ phase: 'paused' })), /Resume/);
  // The hairline says how far, for a screen reader too.
  assert.match(surface({ phase: 'playing', progress: 0.42 }), /role="progressbar"[^>]*aria-valuenow="42"/);
  // The title (French) is always there; the stage is the Revue's band.
  assert.match(surface(), /Un jour de grève dans les transports/);
  assert.match(surface(), /class="rv-stage" data-size="band"/);
});

test('after the end: the transcript with tap words, the dictée masked and mounted, «Vérifier» the press', () => {
  const bulletin = mockBulletin();
  const html = surface({ phase: 'ended', progress: 1 });
  const text = visibleText(html);
  assert.match(html, /data-text="shown"/);
  for (const line of bulletin.lines) {
    if (line.index === bulletin.dictee.lineIndex) continue;
    const third = line.textFr.split(' ')[2].replace(/[,.:;]/g, '');
    assert.ok(text.includes(third), `line ${line.index} shown («${third}»)`);
  }
  // The dictée's sentence is masked until graded: written from the ear, not copied.
  const dictee = bulletin.lines[bulletin.dictee.lineIndex].textFr;
  assert.ok(!text.includes(dictee.slice(0, 40)), 'the dictée line is masked');
  assert.match(html, /data-dictee-mask=""/);
  // Tap-glosses: every word is a control (RvGlossText, mode tap).
  assert.match(html, /<button type="button" class="rv-word">grèves<\/button>/);
  // The journey's Dictation, with its own heard line and field.
  assert.match(html, /class="av2-dictation"/);
  assert.match(html, /<textarea[^>]*autoCorrect="off"/i);
  assert.match(text, /21 words/);
  assert.equal(primaries(html), 1, 'one press: Check');
  assert.match(text, /Check/);
  assert.doesNotMatch(text, /C’est entendu/);
  // The play control steps back to a secondary «Listen again».
  assert.match(html, /av2-btn--secondary[^"]*"[^>]*data-radio-play=""/);
  // «Lire» reveals the same, before the end.
  assert.match(surface({ phase: 'paused', readRequested: true }), /data-text="shown"/);
});

test('graded: the mask lifts, the verdict shows, «C\'est entendu» is the press', () => {
  const bulletin = mockBulletin();
  const dictee = bulletin.lines[bulletin.dictee.lineIndex].textFr;
  const html = surface({
    phase: 'ended',
    dicteeValue: 'dans les transports',
    dicteeResult: { outcome: 'not_yet', expectedFr: dictee, note: null },
  });
  const text = visibleText(html);
  assert.doesNotMatch(html, /data-dictee-mask/);
  assert.match(text, /Listen again: this is what was said\./);
  assert.match(text, /Romy said/);
  assert.equal(primaries(html), 1);
  assert.match(html, /data-radio-done=""/);
  const met = surface({ phase: 'ended', dicteeResult: { outcome: 'met', expectedFr: dictee, note: null }, copy: FR, journeyCopy: journeyCopy('fr') });
  assert.match(visibleText(met), /Exactement ce que Romy a dit\./);
  assert.doesNotMatch(visibleText(met), /Romy a dit «/);
});

test('a bulletin that cannot sound shows the text at once: no play, no dictée, «C\'est entendu»', () => {
  const silent = { ...mockBulletin(), audio: 'unavailable', lines: mockBulletin().lines.map((line) => ({ ...line, clipUrl: null })) };
  const html = surface({ bulletin: silent });
  assert.match(html, /data-text="shown"/);
  assert.doesNotMatch(html, /data-radio-play/);
  assert.doesNotMatch(html, /av2-dictation/);
  assert.doesNotMatch(html, /data-dictee-mask/, 'nothing to mask without a dictée');
  assert.match(visibleText(html), /The sound can’t be played right now\. Here is the text\./);
  assert.equal(primaries(html), 1);
  assert.match(html, /data-radio-done=""/);
});

// ---------------------------------------------------------------------------
// 4. The model
// ---------------------------------------------------------------------------

test('the player: idle → loading → playing → (line) → loading → playing → ended; pause and fail', () => {
  let phase = 'idle';
  for (const [event, expected] of [
    ['play', 'loading'],
    ['loaded', 'playing'],
    ['line_ended', 'loading'],
    ['loaded', 'playing'],
    ['pause', 'paused'],
    ['play', 'loading'],
    ['loaded', 'playing'],
    ['last_ended', 'ended'],
    ['play', 'loading'],
    ['failed', 'failed'],
  ]) {
    phase = model.playerNext(phase, event);
    assert.equal(phase, expected, event);
  }
  assert.equal(model.textVisible('playing', false, 'ready'), false);
  assert.equal(model.textVisible('ended', false, 'ready'), true);
  assert.equal(model.textVisible('failed', false, 'ready'), true, 'a failed clip shows the text');
  assert.equal(model.textVisible('idle', true, 'ready'), true, '«Lire»');
  assert.equal(model.textVisible('idle', false, 'unavailable'), true);
});

test('the hairline weighs lines by length; the guest stands up from their line on', () => {
  const lines = [{ textFr: 'x'.repeat(300) }, { textFr: 'x'.repeat(100) }];
  assert.equal(model.bulletinProgress(lines, 0, 0), 0);
  assert.equal(model.bulletinProgress(lines, 0, 0.5), 150 / 400);
  assert.equal(model.bulletinProgress(lines, 1, 0), 300 / 400);
  assert.equal(model.bulletinProgress(lines, 2, 0), 1);
  const bulletin = mockBulletin();
  const guest = bulletin.lines.findIndex((line) => line.role === 'guest');
  assert.deepEqual(model.stageMembers(bulletin, 0, 'playing').map((m) => m.id), ['romy_tremblay']);
  const on = model.stageMembers(bulletin, guest, 'playing');
  assert.deepEqual(on.map((m) => [m.id, m.speaking]), [['romy_tremblay', false], ['marin_leveque', true]]);
  assert.deepEqual(model.stageMembers(bulletin, 0, 'ended').map((m) => m.id), ['romy_tremblay', 'marin_leveque']);
});

// ---------------------------------------------------------------------------
// 5. The client and the mock
// ---------------------------------------------------------------------------

test('the client: a 404 is «off»; a half-voiced bulletin is silence; snake_case in, camelCase out', async () => {
  const notFound = createRadioClient({ get: () => Promise.reject({ response: { status: 404 } }), post: () => Promise.reject() });
  assert.deepEqual(await notFound.week(), { enabled: false });
  const raw = {
    dossier_id: 'd', title_fr: 'T', topic: 'work', band: 'A2', week: '2026-W40', seconds: 52.3, audio: 'ready', guest_id: 'marin_leveque',
    lines: [
      { index: 0, speaker: 'romy_tremblay', speaker_name: 'Romy Tremblay', role: 'lede', text_fr: 'Bonjour.', clip_url: '/api/v1/daily-journeys/line-audio/nova-' + 'a'.repeat(32) },
      { index: 1, speaker: 'marin_leveque', speaker_name: 'Marin', role: 'guest', text_fr: 'Salut.', clip_url: null },
    ],
    dictee: { line_index: 0, words: 1 },
    stage: { plate_url: null, place_fr: 'Ici' },
  };
  const calls = [];
  const client = createRadioClient({ get: (url) => (calls.push(url), Promise.resolve(raw)), post: () => Promise.resolve({}) });
  const bulletin = await client.bulletin('d', 'A2');
  assert.equal(calls[0], '/revue/radio/d?band=A2');
  assert.equal(bulletin.audio, 'unavailable', 'one line without a clip silences the bulletin');
  assert.equal(bulletin.lines[1].speakerName, 'Marin');
  assert.equal(bulletin.dictee.lineIndex, 0);
  assert.equal(types.parseDicteeResult({ outcome: 'weird' }).outcome, 'not_yet');
});

test('the mock: a silent WAV, the grève at A2 with the dictée on the shortest fact, a mock client', async () => {
  const uri = silentWavDataUri(0.5);
  assert.match(uri, /^data:audio\/wav;base64,UklGR/);
  const bytes = Buffer.from(uri.split(',')[1], 'base64');
  assert.equal(bytes.toString('ascii', 8, 12), 'WAVE');
  assert.equal(bytes.length, 44 + 4000);
  const bulletin = mockBulletin();
  const facts = bulletin.lines.filter((line) => line.role === 'claim' && !/D’après/.test(line.textFr));
  const shortest = facts.reduce((a, b) => (b.textFr.length < a.textFr.length ? b : a));
  assert.equal(bulletin.dictee.lineIndex, shortest.index);
  assert.ok(bulletin.lines.some((line) => /D’après/.test(line.textFr)), 'the view carries «d’après»');
  const client = createMockRadioClient();
  const graded = await client.dictee('x', shortest.textFr.toUpperCase());
  assert.equal(graded.outcome, 'met');
  const week = await client.heard('x');
  assert.equal(week.chip, false);
});

// ---------------------------------------------------------------------------
// 6. La Une
// ---------------------------------------------------------------------------

const WEEK = { enabled: true, week: types.parseRadioWeek({ week: '2026-W40', current: { dossier_id: 'evergreen-greve-transports', title_fr: 'Grève', topic: 'work', evergreen: true }, queue: [], heard: [], heard_today: false, chip: true, seconds: 53 }) };

test('the chip: «La Radio» (55 s in its name) to the next bulletin; none when off, heard today, or all heard', () => {
  const chip = radioHomeChip(WEEK, 'fr');
  assert.equal(chip.label, 'La Radio');
  assert.equal(chip.ariaLabel, 'La Radio de Romy, 55 secondes');
  assert.equal(chip.href, '/radio?dossier=evergreen-greve-transports');
  assert.equal(radioChipSeconds(null), 50);
  assert.equal(radioHomeChip({ enabled: false }, 'en'), null);
  assert.equal(radioHomeChip({ enabled: true, week: { ...WEEK.week, chip: false } }, 'en'), null);
  assert.equal(radioHomeChip({ enabled: true, week: { ...WEEK.week, current: null } }, 'en'), null);
  // Its place: after the Revue chip, else after the letter, else first; never on the Papier day.
  const letter = { id: 'courrier' };
  const revue = { id: 'revue' };
  const words = { id: 'lexique' };
  const radio = { id: 'radio' };
  const ids = (chips) => chips.map((c) => c.id);
  assert.deepEqual(ids(withRadioChip([letter, revue, words], radio)), ['courrier', 'revue', 'radio', 'lexique']);
  assert.deepEqual(ids(withRadioChip([letter, words], radio)), ['courrier', 'radio', 'lexique']);
  assert.deepEqual(ids(withRadioChip([revue, words], radio)), ['revue', 'radio', 'lexique']);
  assert.deepEqual(ids(withRadioChip([words], radio)), ['radio', 'lexique']);
  assert.deepEqual(ids(withRadioChip([], radio, true)), [], 'the Papier day keeps La Une whole');
  assert.deepEqual(ids(withRadioChip([letter], null)), ['courrier']);
});

// HomeScreen with letter + Revue + Radio chips, as home.test.js draws Home.
const Module = require('node:module');
void Module;
const { HomeScreen } = require('../atelier-v2/home/HomeScreen.tsx');
const { JourneyTodayCard } = require('../atelier-v2/journey/JourneyTodayCard.tsx');
const journeyState = require('../atelier-v2/journey/journey-state.ts');
const { dayMarkState } = require('../atelier-v2/journey/day-mark.ts');
const { atelierCopy } = require('../../lib/atelier-v2-copy.ts');
const revueTypes = require('../../lib/revue-types.ts');
const { revueHomeChip } = require('../revue/revue-home.ts');

const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const DAY = JSON.parse(fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/first_day.json'), 'utf8')).response;
const REVUE = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, 'components/revue/fixtures/mock-wire.json'), 'utf8'));
const wordCount = (text) => text.split(' ').filter((token) => /[\p{L}\p{N}]/u.test(token)).length;
const prose = (html) => visibleText(html.replace(/<span aria-hidden="true" data-level-figure="">[\s\S]*?<\/span>/g, ' '));

function home(language, chips, extra = {}) {
  const envelope = { ...DAY, control_language: language };
  const controller = {
    phase: journeyState.phaseFromEnvelope(envelope),
    feedback: { kind: 'idle' },
    envelope,
    journey: envelope.journey ?? null,
    step: null,
    respondPrompt: null,
    controlLanguage: language,
    legacyResume: envelope.legacy_resume ?? null,
    progress: journeyState.journeyProgress(envelope.journey ?? null),
    busy: false,
    help: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
  return render(
    h(HomeScreen, {
      dateLabel: 'mardi 23 septembre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      level: { band: 'A1.1', percent: 60 },
      language,
      day: dayMarkState(null, language),
      hero: h(JourneyTodayCard, { controller, onOpen: () => {} }),
      chips,
      ...extra,
    }),
  );
}

test('La Une: letter + Papier + Radio → the letter and the Papier (the Radio waits); ≤ 25 words, one press', () => {
  const revueWeek = { enabled: true, offer: revueTypes.parseOffer(REVUE.offer) };
  for (const language of ['en', 'de', 'fr']) {
    const copy = atelierCopy(language);
    const letter = { id: 'courrier', label: copy.home_letter, ariaLabel: copy.home_letter_aria, href: '/missions?mission=1', shape: 'story' };
    const words = { id: 'lexique', label: copy.home_words_many.replace('{n}', '3'), ariaLabel: copy.home_review_many.replace('{n}', '3'), href: '/vocabulary/review' };
    const revue = revueHomeChip(revueWeek, language);
    const radio = radioHomeChip(WEEK, language);
    const cases = [
      [[letter, revue, words], ['courrier', 'revue']],
      [[revue, words], ['revue', 'radio']],
      [[letter, words], ['courrier', 'radio']],
      [[words], ['radio', 'lexique']],
    ];
    for (const [base, shown] of cases) {
      const chips = withRadioChip(base, radio);
      const html = home(language, chips);
      const drawn = [...html.matchAll(/data-chip="([^"]+)"/g)].map((m) => m[1]);
      assert.deepEqual(drawn, shown, `${language}: ${base.map((c) => c.id).join('+')}`);
      const count = wordCount(prose(html));
      assert.ok(count <= 25, `${language}: ${count} words — ${prose(html)}`);
      assert.equal(primaries(html), 1, 'a chip is never a press');
    }
    // After the day: one chip, the first in precedence.
    const done = home(language, withRadioChip([words], radio), { dayDone: true });
    assert.ok((done.match(/data-chip=/g) || []).length <= 1);
  }
});
