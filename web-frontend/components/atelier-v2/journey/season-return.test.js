// node --test components/atelier-v2/journey/season-return.test.js
//
// WP-98 «La saison suivante» + WP-99 «Le facteur et les dépêches», the web half:
//
//   1. «Entre-temps»: read defensively, at most five dated lines, lapsed letters
//      linked to the Courrier, the greeting's face; shown before the first step
//      only, once per journey (device memory), never on day 1;
//   2. «Nouvelle saison»: the premiere is chosen journey → envelope, the poster
//      is the day's first panel (existing art), one primary on the front page
//      and on Home's card;
//   3. the interlude: only with a readable return date; Home says «l’histoire
//      reprend le …», offers the practice that exists and presses nothing;
//   4. dates in words in three languages; «La suite demain» prefers the
//      engine's `next_teaser_fr`; the archive prints a new season as a volume;
//   5. the copy tables carry the same keys in en/de/fr.

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

const model = require('./season-return-model.ts');
const { SEASON_RETURN_TABLES, seasonReturnCopy } = require('./season-return-copy.ts');
const { EntreTemps, SeasonPremiere, InterludeCard } = require('./SeasonPages.tsx');
const { JourneyTodayCard } = require('./JourneyTodayCard.tsx');
const state = require('./journey-state.ts');
const { rewardView } = require('./journey-recap-model.ts');
const archive = require('../../feuilleton/archive/archive-model.ts');
const { ArchiveVolume } = require('../../feuilleton/archive/FeuilletonArchive.tsx');

const h = React.createElement;
const quiet = (fn) => {
  const original = console.error;
  console.error = () => {};
  try {
    return fn();
  } finally {
    console.error = original;
  }
};
const render = (element) => quiet(() => renderToStaticMarkup(element));
const primaries = (html) => (html.match(/av2-btn--primary/g) || []).length;

function memoryStorage(initial = {}) {
  const values = { ...initial };
  return {
    getItem: (key) => (key in values ? values[key] : null),
    setItem: (key, value) => {
      values[key] = String(value);
    },
    values,
  };
}

const ABSENCE = {
  days: 6,
  greeting_fr: 'Te voilà enfin !',
  entre_temps: [
    { text_fr: 'Six.', date: '2026-09-27', character_id: 'romy_tremblay' },
    { text_fr: 'Un.', date: '2026-09-21', character_id: null },
    { text_fr: 'Trois.', date: '2026-09-23', character_id: null },
    { text_fr: '   ', date: '2026-09-24', character_id: null },
    { text_fr: 'Deux.', date: '2026-09-22', character_id: null },
    { text_fr: 'Quatre.', date: 'not a date', character_id: null },
    { text_fr: 'Cinq.', date: '2026-09-26', character_id: null },
  ],
  lapsed_letters: [
    { mission_id: 'm7', correspondent_name: 'Lila' },
    { mission_id: 'm7', correspondent_name: 'Lila' },
    { mission_id: '', correspondent_name: 'Nobody' },
    { mission_id: 'm9', correspondent_name: null },
  ],
};

const STEPS = [
  { id: 's1', kind: 'scene', status: 'active', prompt: { image_url: '/scene.webp', panels: [{ image_url: null }, { image_url: '/panel-2.webp' }] } },
  { id: 's2', kind: 'respond', status: 'pending', prompt: {} },
];

function journey(extra = {}) {
  return {
    id: 'j-1',
    status: 'active',
    current_step_id: 's1',
    steps: STEPS,
    cast_intro: null,
    scenario: { character_id: 'romy_tremblay', character_name: 'Romy', image_url: '/scenario.webp' },
    ...extra,
  };
}

// ---------------------------------------------------------------- Entre-temps

test('absenceOf: nothing, malformed or empty is no page', () => {
  assert.equal(model.absenceOf(null), null);
  assert.equal(model.absenceOf({}), null);
  assert.equal(model.absenceOf({ absence: null }), null);
  assert.equal(model.absenceOf({ absence: 'yes' }), null);
  assert.equal(model.absenceOf({ absence: { days: 4, greeting_fr: ' ', entre_temps: [], lapsed_letters: [] } }), null);
});

test('absenceOf: at most five lines, the latest five, oldest first; letters deduplicated', () => {
  const view = model.absenceOf({ absence: ABSENCE, scenario: { character_id: 'marin_leveque', character_name: 'Marin' } });
  assert.equal(view.days, 6);
  assert.equal(view.lines.length, model.ENTRE_TEMPS_MAX_LINES);
  assert.equal(model.ENTRE_TEMPS_MAX_LINES, 5);
  // Dated lines sort forward; the blank one is dropped; the undated one keeps its place.
  const all = model.absenceOf({ absence: { ...ABSENCE, entre_temps: ABSENCE.entre_temps.slice(0, 3) } });
  assert.deepEqual(all.lines.map((line) => line.textFr), ['Un.', 'Trois.', 'Six.']);
  assert.equal(view.lines.at(-1).textFr, 'Six.', 'the most recent line is last');
  assert.ok(view.lines.every((line) => line.date === null || /^\d{4}-\d{2}-\d{2}$/.test(line.date)));
  assert.deepEqual(view.letters, [
    { missionId: 'm7', correspondentName: 'Lila', href: '/missions?mission=m7' },
    { missionId: 'm9', correspondentName: '', href: '/missions?mission=m9' },
  ]);
  // No speaker on the absence: the day's counterpart greets.
  assert.equal(view.characterId, 'marin_leveque');
  assert.equal(view.characterName, 'Marin');
});

test('absenceOf: the absence names its own speaker; no greeting means no borrowed face', () => {
  const own = model.absenceOf({ absence: { ...ABSENCE, character_id: 'lila_bonnet', character_name: 'Lila' }, scenario: { character_id: 'x' } });
  assert.equal(own.characterId, 'lila_bonnet');
  const silent = model.absenceOf({ absence: { ...ABSENCE, greeting_fr: null }, scenario: { character_id: 'x', character_name: 'X' } });
  assert.equal(silent.characterId, null);
  assert.equal(silent.greetingFr, null);
});

test('dayPreludes: before the first step only, never on day 1, each once per journey', () => {
  const none = () => false;
  assert.deepEqual(model.dayPreludes(journey({ absence: ABSENCE }), none), ['entre_temps']);
  assert.deepEqual(
    model.dayPreludes(journey({ absence: ABSENCE, season_premiere: { number: 2, title_fr: 'Les voisins' } }), none),
    ['entre_temps', 'premiere'],
    'welcomed back first, then the front page',
  );
  // Day 1: the cast is being introduced — no «meanwhile».
  assert.deepEqual(model.dayPreludes(journey({ absence: ABSENCE, cast_intro: [{ character_id: 'marin' }] }), none), []);
  // The day has moved: a resume goes straight on.
  const moved = journey({
    absence: ABSENCE,
    current_step_id: 's2',
    steps: [{ ...STEPS[0], status: 'completed' }, { ...STEPS[1], status: 'active' }],
  });
  assert.equal(model.journeyAtFirstStep(moved), false);
  assert.deepEqual(model.dayPreludes(moved, none), []);
  assert.deepEqual(model.dayPreludes(journey({ absence: ABSENCE, status: 'paused' }), none), []);
  assert.deepEqual(model.dayPreludes(null, none), []);
  // Seen on this device for this journey.
  assert.deepEqual(model.dayPreludes(journey({ absence: ABSENCE }), (kind) => kind === 'entre_temps'), []);
  // An older server: nothing to show.
  assert.deepEqual(model.dayPreludes(journey(), none), []);
});

test('prelude memory: per kind and journey; unreadable storage reads as unseen and never throws', () => {
  const storage = memoryStorage();
  assert.equal(model.preludeSeen(storage, 'entre_temps', 'j-1'), false);
  model.rememberPreludeSeen(storage, 'entre_temps', 'j-1');
  assert.equal(model.preludeSeen(storage, 'entre_temps', 'j-1'), true);
  assert.equal(model.preludeSeen(storage, 'premiere', 'j-1'), false);
  assert.equal(model.preludeSeen(storage, 'entre_temps', 'j-2'), false);
  const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
  assert.equal(model.preludeSeen(broken, 'premiere', 'j-1'), false);
  assert.doesNotThrow(() => model.rememberPreludeSeen(broken, 'premiere', 'j-1'));
  assert.equal(model.preludeSeen(null, 'premiere', 'j-1'), false);
  assert.equal(model.preludeSeen(storage, 'premiere', ''), false);
});

test('EntreTemps renders the greeting, ≤ 5 tappable dated lines, the lapsed letter and one primary', () => {
  for (const language of ['en', 'de', 'fr']) {
    const view = model.absenceOf({ absence: { ...ABSENCE, character_id: 'romy_tremblay', character_name: 'Romy' } });
    const html = render(h(EntreTemps, { absence: view, language, onContinue: () => {} }));
    const t = seasonReturnCopy(language);
    assert.equal(primaries(html), 1, `${language}: one primary`);
    assert.ok(html.includes(t.absence_title));
    assert.ok(html.includes(t.absence_resume));
    assert.ok(html.includes(t.absence_skip), 'skippable');
    assert.equal((html.match(/class="sr-line"/g) || []).length, 5);
    assert.ok(html.includes('data-word'), 'the words are tappable');
    assert.ok(html.includes('href="/missions?mission=m7"'), 'the lapsed letter opens in the Courrier');
    assert.ok(html.includes(t.lapsed_line_anon), 'an unnamed correspondent still has a line');
    assert.ok(html.includes('data-greeting'));
    assert.ok(html.includes('Entre-temps'));
  }
});

// ------------------------------------------------------------ Nouvelle saison

test('season premiere: journey first, then the envelope; a premiere without number or title is none', () => {
  assert.equal(model.seasonPremiereOf({ season_premiere: { number: 0, title_fr: 'X' } }), null);
  assert.equal(model.seasonPremiereOf({ season_premiere: { number: 2, title_fr: '  ' } }), null);
  assert.deepEqual(model.seasonPremiereOf({ season_premiere: { number: '3', title_fr: 'T', logline_fr: '' } }), {
    number: 3,
    titleFr: 'T',
    loglineFr: null,
  });
  const envelope = { season_premiere: { number: 2, title_fr: 'Envelope' }, journey: null };
  assert.equal(model.todayPremiere(envelope, null).titleFr, 'Envelope');
  assert.equal(model.todayPremiere(envelope, { season_premiere: { number: 2, title_fr: 'Journey' } }).titleFr, 'Journey');
  assert.equal(model.todayPremiere(null, null), null);
});

test('the poster is the day’s first drawn panel: episode → scene panel → scene image → scenario', () => {
  const j = journey();
  assert.equal(model.premierePoster(j, [{ image_url: null }, { image_url: '/episode.webp' }]), '/episode.webp');
  assert.equal(model.premierePoster(j, null), '/panel-2.webp');
  assert.equal(model.premierePoster({ ...j, steps: [{ kind: 'scene', prompt: { image_url: '/scene.webp' } }] }), '/scene.webp');
  assert.equal(model.premierePoster({ ...j, steps: [] }), '/scenario.webp');
  assert.equal(model.premierePoster({ steps: [], scenario: { image_url: null } }), null);
});

test('SeasonPremiere: «Saison N» in Garamond, title, logline, poster, one primary', () => {
  const premiere = model.seasonPremiereOf({ season_premiere: { number: 2, title_fr: 'Les voisins', logline_fr: 'Une lettre arrive.' } });
  for (const language of ['en', 'de', 'fr']) {
    const html = render(h(SeasonPremiere, { premiere, posterUrl: '/poster.webp', language, onContinue: () => {} }));
    assert.equal(primaries(html), 1);
    assert.match(html, /av2-headline--display[^>]*>Saison 2</);
    assert.ok(html.includes('Les voisins'));
    assert.ok(html.includes('Une lettre arrive.'));
    assert.ok(html.includes('src="/poster.webp"'));
    assert.ok(html.includes(seasonReturnCopy(language).premiere_open));
  }
});

// ------------------------------------------------------------------ Interlude

test('interludeOf: the date only when readable; without one, a pause and no invented date', () => {
  assert.equal(model.interludeOf(null), null);
  assert.equal(model.interludeOf({ interlude: null }), null);
  assert.deepEqual(model.interludeOf({ interlude: { returns_on: 'soon', reason_fr: 'x' } }), { returnsOn: null, reasonFr: 'x' });
  assert.equal(model.interludeOf({ interlude: { returns_on: '2026-13-01' } }).returnsOn, null);
  const fr = seasonReturnCopy('fr');
  assert.equal(model.interludeHeadline({ returnsOn: null, reasonFr: null }, fr, 'fr'), 'Le feuilleton fait une pause.');
  assert.equal(model.interludeHeadline({ returnsOn: '2026-10-01', reasonFr: null }, fr, 'fr'), 'L’histoire reprend le 1er octobre.');
  assert.deepEqual(model.interludeOf({ interlude: { returns_on: '2026-10-05T00:00:00Z', reason_fr: ' Pause. ' } }), {
    returnsOn: '2026-10-05',
    reasonFr: 'Pause.',
  });
  assert.equal(model.todayInterlude({ interlude: null }, { interlude: { returns_on: '2026-10-05' } }).returnsOn, '2026-10-05');
});

test('interlude practice: only what exists — Forge when offered, the Courrier, the archive', () => {
  assert.deepEqual(model.interludePractice(null).map((p) => p.id), ['courrier', 'relecture']);
  assert.deepEqual(model.interludePractice('/atelier?mode=forge').map((p) => p.href), ['/atelier?mode=forge', '/missions', '/graphic-novel']);
  assert.deepEqual(model.interludePractice('https://evil.example').map((p) => p.id), ['courrier', 'relecture']);
});

test('longDate: three languages, «1er» on the first, never through a timezone', () => {
  assert.equal(model.longDate('2026-10-05', 'fr'), '5 octobre');
  assert.equal(model.longDate('2026-10-01', 'fr'), '1er octobre');
  assert.equal(model.longDate('2026-10-05', 'en'), 'October 5');
  assert.equal(model.longDate('2026-10-05', 'de'), '5. Oktober');
  assert.equal(model.longDate('2026-03-01', 'de-AT'), '1. März');
  assert.equal(model.longDate('2026-12-31', undefined), '31 décembre');
  assert.equal(model.longDate('nope', 'en'), '');
  assert.equal(model.longDate(null, 'en'), '');
});

function controllerFor(envelope, language = 'en') {
  return {
    phase: state.phaseFromEnvelope(envelope),
    feedback: { kind: 'idle' },
    envelope,
    journey: envelope.journey ?? null,
    step: null,
    respondPrompt: null,
    controlLanguage: language,
    legacyResume: null,
    progress: state.journeyProgress(envelope.journey ?? null),
    busy: false,
    help: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
}

const ENVELOPE = {
  contract_version: 1,
  enabled: true,
  control_language: 'en',
  local_date: '2026-09-29',
  timezone: 'Europe/Paris',
  journey: null,
  available: null,
  legacy_resume: null,
  practice_href: '/atelier?mode=practice',
  because: null,
  is_warm: false,
  missed_days: 6,
};

const SCENARIO = {
  scenario_key: 'k',
  content_version: '1',
  title_fr: 'Une lettre sans timbre',
  objective_key: 'o',
  objective_native: 'Ask Romy.',
  level_band: 'A1',
  character_id: 'romy_tremblay',
  character_name: 'Romy',
  location_id: 'le_mistral',
  location_name: 'Le Mistral',
  image_url: '/scenario.webp',
  serial_thread_id: null,
  serial_episode_id: null,
  estimated_seconds: 300,
};

test('Home between two seasons: the return date and the reason, the practice rows, no press, no «Reprise»', () => {
  for (const language of ['en', 'de', 'fr']) {
    const envelope = {
      ...ENVELOPE,
      control_language: language,
      forge: { href: '/atelier?mode=forge', concept_id: 1, budget_seconds: 300, folded: false },
      interlude: { returns_on: '2026-10-05', reason_fr: 'Le Mistral ferme une semaine.' },
    };
    const html = render(h(JourneyTodayCard, { controller: controllerFor(envelope, language), onOpen: () => {} }));
    const t = seasonReturnCopy(language);
    assert.equal(primaries(html), 0, `${language}: no fake scene to press`);
    assert.ok(html.includes(t.interlude_kicker));
    assert.ok(html.includes(model.longDate('2026-10-05', language)));
    assert.ok(html.includes('Le Mistral ferme une semaine.'));
    for (const href of ['/atelier?mode=forge', '/missions', '/graphic-novel']) {
      assert.ok(html.includes(`href="${href}"`), `${language}: ${href}`);
    }
  }
  // A quiet authored interlude scene: the card, labelled, and no «Reprise en douceur».
  const withScene = { ...ENVELOPE, available: SCENARIO, interlude: { returns_on: '2026-10-05', reason_fr: null } };
  const html = render(h(JourneyTodayCard, { controller: controllerFor(withScene), onOpen: () => {} }));
  assert.equal(primaries(html), 1);
  assert.ok(html.includes('Between two seasons'));
  assert.ok(!html.includes('Easing back in'), 'days between seasons are not an absence');
  assert.ok(html.includes('The story comes back on October 5.'));
});

test('Home on a premiere day: the front page is the card, one primary that opens the season', () => {
  const envelope = {
    ...ENVELOPE,
    available: SCENARIO,
    season_premiere: { number: 2, title_fr: 'Les voisins', logline_fr: 'Une lettre arrive.' },
  };
  const html = render(h(JourneyTodayCard, { controller: controllerFor(envelope, 'fr'), onOpen: () => {} }));
  assert.equal(primaries(html), 1);
  assert.match(html, /Saison 2/);
  assert.ok(html.includes('Les voisins'));
  assert.ok(html.includes('src="/scenario.webp"'), 'the poster is existing art');
  assert.ok(html.includes('Ouvrir la saison'));
  assert.ok(html.includes('data-premiere="2"'));
});

// ----------------------------------------------------------- the teaser

test('«La suite demain»: the engine’s next_teaser_fr first, signed by the structured teaser', () => {
  const structured = { text_fr: 'Authored.', character_id: 'romy_tremblay', character_name: 'Romy', source: 'authored' };
  assert.equal(model.recapTeaserOf(null), null);
  assert.deepEqual(model.recapTeaserOf({ teaser: structured }), structured);
  assert.deepEqual(model.recapTeaserOf({ teaser: structured, next_teaser_fr: ' Qui a écrit la lettre ? ' }), {
    text_fr: 'Qui a écrit la lettre ?',
    character_id: 'romy_tremblay',
    character_name: 'Romy',
    source: 'engine',
  });
  assert.equal(model.recapTeaserOf({ teaser: null, next_teaser_fr: 'Demain.' }).character_name, null);
  assert.equal(model.recapTeaserOf({ teaser: { ...structured, text_fr: ' ' } }), null);
});

test('the recap and Home’s finished card print the engine’s teaser', () => {
  const recap = {
    completion_kind: 'complete',
    objective_outcome: 'met',
    practiced_targets: [],
    capability_evidence: [],
    next_focus: null,
    collectible_ids: [],
    story_outcome: null,
    active_seconds: 300,
    teaser: { text_fr: 'Authored.', character_id: null, character_name: 'Romy', source: 'authored' },
    next_teaser_fr: 'Qui a écrit la lettre ?',
  };
  const done = {
    id: 'j-9',
    contract_version: 1,
    revision: 3,
    status: 'completed',
    local_date: '2026-09-29',
    timezone: 'Europe/Paris',
    budget_seconds: 600,
    estimated_active_seconds: 300,
    current_step_id: null,
    scenario: SCENARIO,
    steps: [],
    recap,
    retry: null,
  };
  const view = rewardView(done, recap, 'en');
  assert.equal(view.teaser.text_fr, 'Qui a écrit la lettre ?');
  assert.equal(view.teaser.source, 'engine');
  const html = render(h(JourneyTodayCard, { controller: controllerFor({ ...ENVELOPE, journey: done }, 'en'), onOpen: () => {} }));
  assert.ok(html.includes('data-teaser="engine"'));
  assert.ok(html.includes('Qui a écrit la lettre'));
});

// ----------------------------------------------------------- the archive

const RAW_ARCHIVE = {
  seasons: [
    {
      number: 1,
      title_fr: 'S’installer',
      finished: true,
      loaded: true,
      chapters: [{ index: 1, title_fr: 'Arrivée', closed: true, days: [{ date: '2026-06-01', journey_id: 'j1', title_fr: 'Un' }] }],
    },
    { number: 2, title_fr: 'Les voisins', logline_fr: 'Une lettre arrive sans timbre.', finished: false, loaded: true, chapters: [] },
  ],
  current: { season: 2, chapter: 1 },
};

test('the archive keeps a new season as a volume before its first page is filed', () => {
  const payload = archive.normalizeArchive(RAW_ARCHIVE);
  assert.deepEqual(payload.seasons.map((s) => s.number), [2, 1]);
  assert.equal(payload.seasons[0].logline_fr, 'Une lettre arrive sans timbre.');
  assert.equal(archive.isNewVolume(payload, payload.seasons[0]), true);
  assert.equal(archive.isNewVolume(payload, payload.seasons[1]), false, 'a tome is not new');
  // A first season is «the» volume, never «new».
  const first = archive.normalizeArchive({
    seasons: [{ number: 1, title_fr: 'S', finished: false, chapters: [{ index: 1, days: [{ date: '2026-06-01', journey_id: 'j' }] }] }],
    current: { season: 1, chapter: 1 },
  });
  assert.equal(archive.isNewVolume(first, first.seasons[0]), false);
  // A non-current empty season is still dropped.
  const stale = archive.normalizeArchive({ ...RAW_ARCHIVE, current: null });
  assert.deepEqual(stale.seasons.map((s) => s.number), [1]);
});

test('ArchiveVolume prints the new volume: «Nouveau volume», «Saison 2» in Garamond, title, logline', () => {
  const payload = archive.normalizeArchive(RAW_ARCHIVE);
  const html = render(h(ArchiveVolume, { archive: payload, language: 'en', openKeys: [], onToggleChapter: () => {} }));
  assert.ok(html.includes('data-new-volume="2"'));
  assert.ok(html.includes('New volume'));
  assert.match(html, /av2-headline--screen[^>]*>Saison 2</);
  assert.ok(html.includes('Une lettre arrive sans timbre.'));
  assert.ok(html.includes('The first pages are on their way.'));
  assert.ok(html.includes('data-tome="1"'), 'the finished season stays a tome');
});

// ----------------------------------------------------------- copy

test('the copy tables carry the same keys, no blanks, and the marks stay French', () => {
  const keys = Object.keys(SEASON_RETURN_TABLES.fr).sort();
  for (const language of ['en', 'de']) {
    assert.deepEqual(Object.keys(SEASON_RETURN_TABLES[language]).sort(), keys, language);
  }
  for (const language of ['en', 'de', 'fr']) {
    for (const [key, value] of Object.entries(SEASON_RETURN_TABLES[language])) {
      assert.ok(String(value).trim(), `${language}.${key}`);
    }
    assert.equal(SEASON_RETURN_TABLES[language].season_n, 'Saison {n}');
    assert.equal(SEASON_RETURN_TABLES[language].entre_temps_mark, 'Entre-temps');
  }
  assert.equal(seasonReturnCopy('fr').absence_title, 'Pendant votre absence');
  assert.equal(seasonReturnCopy('fr').absence_resume, 'Reprendre l’histoire');
  assert.equal(seasonReturnCopy('fr').lapsed_title, 'Courrier en souffrance');
  assert.notEqual(seasonReturnCopy('de').absence_title, seasonReturnCopy('fr').absence_title);
  assert.equal(seasonReturnCopy(null).lang, 'fr');
});

test('InterludeCard alone never presses and names the places in French', () => {
  const html = render(h(InterludeCard, { interlude: { returnsOn: '2026-10-05', reasonFr: null }, language: 'de' }));
  assert.equal(primaries(html), 0);
  assert.ok(html.includes('Die Geschichte geht am 5. Oktober weiter.'));
  assert.ok(html.includes('Le Courrier'));
  assert.ok(!html.includes('La Forge'), 'no Forge row without a Forge block');
});
