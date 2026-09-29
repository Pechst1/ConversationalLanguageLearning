// node --test components/feuilleton/archive/archive.test.js
//
// WP-96 «Les Cahiers du feuilleton» + WP-97 «Les suites».
//
//   1. the archive payload is read defensively and ordered as the volume
//      prints it (seasons and chapters newest first, days oldest first);
//      header-only seasons stay on the shelf; the authored day is a planche;
//   2. which chapter is open on arrival; the digest line's two halves;
//   3. routes: a planche's, a margin note's, and the day each one finds;
//   4. margin notes sit on their panel (engine panel_id → the character's
//      first line → the page's end);
//   5. the trust meter is five marks that can fall; «tu depuis le …»;
//      «Ce que … sait de vous» holds five, newest first;
//   6. «Précédemment»: ≤3 lines, never on day 1, never twice;
//   7. the renders: folds, colophon, tome, planche rows, the reply in
//      Garamond italic, the trombinoscope without closeness pips, the recap's
//      colophon and tome, and the chrome in the learner's language.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  if (request === 'next/link') {
    return originalResolve.call(this, path.join(WEB_ROOT, 'components/feuilleton/reader/__fixtures__/next-link-stub.js'), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const realConsoleError = console.error;
console.error = (...args) => {
  const first = String(args[0] || '');
  if (first.includes('non-boolean attribute') || first.includes('useLayoutEffect')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
global.React = React;
const h = React.createElement;

const model = require('./archive-model.ts');
const trombi = require('./trombinoscope-model.ts');
const prev = require('./precedemment-model.ts');
const { archiveCopy, archiveDate, faPlural } = require('./archive-copy.ts');
const marks = require('./ArchiveMarks.tsx');
const surface = require('./FeuilletonArchive.tsx');
const { CastCard, Trombinoscope } = require('./Trombinoscope.tsx');
const { AtelierV2Root } = require('@/components/atelier-v2/ui/index.ts');
const { JourneyRecap } = require('@/components/atelier-v2/journey/JourneyRecap.tsx');

const decode = (s) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"');
const text = (html) => decode(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<span class="fa-sr">[\s\S]*?<\/span>/g, ' ').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();

/* ------------------------------------------------------------ fixture */

const day = (date, n, extra = {}) => ({
  date,
  journey_id: `j-${date}`,
  scene_id: `s-${date}`,
  title_fr: `Planche du ${date}`,
  edition_no: n,
  image_url: null,
  learner_lines: [],
  ending_fr: null,
  margin_notes: [],
  can_do_id: null,
  special: null,
  ...extra,
});

const RAW = {
  // deliberately out of order: the model owns the order
  seasons: [
    {
      number: 1,
      title_fr: 'S’installer',
      finished: true,
      loaded: false,
      day_count: 21,
      chapters: [],
    },
    {
      number: 2,
      title_fr: 'Les voisins',
      finished: false,
      loaded: true,
      chapters: [
        {
          index: 1,
          title_fr: 'La clé perdue',
          digest_fr: 'Qui a pris la clé ? → Marin, pour la rendre à Lila.',
          closed: true,
          days: [
            day('2026-09-13', 2, { learner_lines: ['Vas-y, Marin !'], ending_fr: 'Marin part en courant.' }),
            // the authored first day: no scene id, its own page
            day('2026-09-12', 1, {
              scene_id: null,
              authored: true,
              panels: [
                { id: 'a1', index: 0, narration_fr: 'Le Mistral, huit heures.', dialogue: [{ character_id: 'margaux_barman', text_fr: 'Bonjour !' }] },
                { id: 'a2', index: 1, narration_fr: '', dialogue: [] },
              ],
            }),
          ],
        },
        {
          index: 2,
          title_fr: 'Le plombier',
          digest_fr: null,
          closed: false,
          days: [
            day('2026-09-15', 4, {
              learner_lines: ['Je peux vous aider ?'],
              margin_notes: [
                { text_fr: 'Parce que vous avez dit à Marin « vas-y »', cause_scene_id: 's-2026-09-13', cause_date: '2026-09-13', character_id: 'marin' },
                { text_fr: '' },
              ],
            }),
            day('2026-09-14', 3, { special: 'epreuve' }),
          ],
        },
        { index: 3, title_fr: 'Vide', closed: false, days: [] },
      ],
    },
  ],
  current: { season: 2, chapter: 2 },
};

const ARCHIVE = model.normalizeArchive(RAW);

/* ------------------------------------------------------ 1. the model */

test('the archive is ordered as the volume prints it', () => {
  assert.deepEqual(ARCHIVE.seasons.map((s) => s.number), [2, 1], 'seasons newest first');
  const s2 = ARCHIVE.seasons[0];
  assert.deepEqual(s2.chapters.map((c) => c.index), [2, 1], 'chapters newest first; an empty non-current chapter is dropped');
  assert.deepEqual(s2.chapters[1].days.map((d) => d.date), ['2026-09-12', '2026-09-13'], 'days oldest first');
  assert.deepEqual(s2.chapters[0].days[1].margin_notes.length, 1, 'a note without a sentence is dropped');
  // the header-only tome stays on the shelf, with its count
  const s1 = ARCHIVE.seasons[1];
  assert.equal(s1.loaded, false);
  assert.equal(model.seasonPageCount(s1), 21);
  assert.equal(model.seasonPageCount(s2), 4);
  assert.equal(model.archiveIsEmpty(ARCHIVE), false);
  assert.equal(model.archiveIsEmpty(model.normalizeArchive({})), true);
  assert.equal(model.archiveIsEmpty(model.normalizeArchive(null)), true);
  // every day in reading order
  assert.deepEqual(model.archiveDays(ARCHIVE).map((d) => d.edition_no), [1, 2, 3, 4]);
});

test('W14: the authored first day is a planche with its own page', () => {
  const first = model.findArchiveDay(ARCHIVE, { date: '2026-09-12' });
  assert.equal(first.authored, true);
  assert.equal(first.scene_id, null);
  const episode = model.archiveDayEpisode(first);
  assert.equal(episode.panels.length, 1, 'an empty panel is not a panel');
  assert.equal(episode.panels[0].dialogue[0].text_fr, 'Bonjour !');
  assert.equal(episode.status, 'completed');
  assert.equal(model.archiveDayEpisode(model.findArchiveDay(ARCHIVE, { date: '2026-09-13' })), null, 'engine days are fetched');
});

test('a season fetched on its own folds into the volume', () => {
  const fetched = model.normalizeArchive({
    seasons: [{ number: 1, title_fr: 'S’installer', finished: true, loaded: true, chapters: [{ index: 1, title_fr: 'Arrivée', closed: true, days: [day('2026-06-01', 1)] }] }],
    current: { season: 2, chapter: 2 },
  });
  const merged = model.mergeArchiveSeason(ARCHIVE, fetched, 1);
  assert.equal(merged.seasons[1].loaded, true);
  assert.equal(merged.seasons[1].chapters[0].title_fr, 'Arrivée');
  assert.equal(model.mergeArchiveSeason(ARCHIVE, model.normalizeArchive({}), 1), ARCHIVE, 'nothing fetched, nothing changed');
});

test('the current chapter is open; closed chapters fold; a tome opens nothing', () => {
  assert.deepEqual(model.defaultOpenChapters(ARCHIVE), ['s2c2']);
  const noCurrent = model.normalizeArchive({ ...RAW, current: null });
  assert.deepEqual(model.defaultOpenChapters(noCurrent), ['s2c2'], 'else the newest chapter of the running season');
  const allFinished = model.normalizeArchive({ seasons: [{ ...RAW.seasons[1], finished: true }], current: null });
  assert.deepEqual(model.defaultOpenChapters(allFinished), []);
  const s2 = ARCHIVE.seasons[0];
  assert.equal(model.chapterIsCurrent(ARCHIVE, s2, s2.chapters[0]), true);
  assert.equal(model.chapterIsCurrent(ARCHIVE, s2, s2.chapters[1]), false);
});

test('the digest line «question → résolution»', () => {
  assert.deepEqual(model.digestParts('Qui a pris la clé ? → Marin.'), { question: 'Qui a pris la clé ?', resolution: 'Marin.' });
  assert.deepEqual(model.digestParts('A -> B'), { question: 'A', resolution: 'B' });
  assert.deepEqual(model.digestParts('Une seule phrase.'), { question: 'Une seule phrase.', resolution: '' });
  assert.equal(model.digestParts(''), null);
  assert.equal(model.digestParts(null), null);
});

/* -------------------------------------------------------- 3. routes */

test('planche and margin-note routes find their day', () => {
  const d = model.findArchiveDay(ARCHIVE, { date: '2026-09-13' });
  assert.equal(model.archiveDayHref(d), '/graphic-novel?day=2026-09-13&journey=j-2026-09-13');
  const note = model.findArchiveDay(ARCHIVE, { date: '2026-09-15' }).margin_notes[0];
  assert.equal(model.marginNoteHref(note), '/graphic-novel?day=2026-09-13&cause=s-2026-09-13');
  assert.equal(model.marginNoteHref({ text_fr: 'x', cause_scene_id: null, cause_date: null, character_id: null }), null, 'no cause, no link');
  // identity wins over the date
  assert.equal(model.findArchiveDay(ARCHIVE, { date: '2026-09-15', sceneId: 's-2026-09-13' }).edition_no, 2);
  assert.equal(model.findArchiveDay(ARCHIVE, { journeyId: 'j-2026-09-14' }).edition_no, 3);
  assert.equal(model.findArchiveDay(ARCHIVE, { date: '2020-01-01' }), null);
  // a note without its own Nº takes the cause day's
  assert.equal(model.marginNoteEdition(note, ARCHIVE), 2);
  assert.equal(model.marginNoteEdition({ ...note, cause_edition_no: 9 }, ARCHIVE), 9);
});

test('an older server: the season projection prints as one chapter', () => {
  const fallback = model.archiveFromSeason({
    thread_id: 't', season_number: 1, chapter: { number: 2, title_fr: 'Les voisins' }, today: null, commitments: [],
    read_episodes: [{ scene_id: 's3', number: 3, title_fr: 'Le marché', brief_fr: '', image_url: null, character: '', location: '', status: 'completed' }],
  });
  assert.equal(fallback.seasons[0].chapters[0].title_fr, 'Les voisins');
  assert.equal(fallback.seasons[0].chapters[0].days[0].edition_no, 3);
  assert.equal(model.archiveDayHref(fallback.seasons[0].chapters[0].days[0]), '/graphic-novel?cause=s3');
  assert.equal(model.archiveFromSeason(null), null);
});

/* ---------------------------------------------- 4. margin placement */

test('a margin note sits on the panel where it is paid back', () => {
  const panels = [
    { id: 'p2', index: 1, dialogue: [{ character_id: 'marin' }] },
    { id: 'p1', index: 0, dialogue: [{ character_id: 'lila' }] },
    { id: 'p3', index: 2, dialogue: [{ character_id: 'marin' }] },
  ];
  const notes = [
    { text_fr: 'engine', cause_scene_id: null, cause_date: null, character_id: 'marin', panel_id: 'p3' },
    { text_fr: 'speaker', cause_scene_id: null, cause_date: null, character_id: 'Marin' },
    { text_fr: 'nobody', cause_scene_id: null, cause_date: null, character_id: 'romy' },
    { text_fr: 'bogus panel', cause_scene_id: null, cause_date: null, character_id: null, panel_id: 'zz' },
  ];
  const placed = model.placeMarginNotes(panels, notes);
  assert.deepEqual(placed.byPanel.p3.map((n) => n.text_fr), ['engine']);
  assert.deepEqual(placed.byPanel.p2.map((n) => n.text_fr), ['speaker'], 'the first panel the character speaks in');
  assert.deepEqual(placed.end.map((n) => n.text_fr), ['nobody', 'bogus panel']);
  assert.deepEqual(model.placeMarginNotes(null, null), { byPanel: {}, end: [] });
});

/* ------------------------------------------------ 5. trombinoscope */

test('trust is five marks, filled then outlined — and it can fall', () => {
  assert.deepEqual(trombi.trustMarks(3), ['filled', 'filled', 'filled', 'empty', 'empty']);
  assert.deepEqual(trombi.trustMarks(0), ['empty', 'empty', 'empty', 'empty', 'empty']);
  assert.deepEqual(trombi.trustMarks(9), Array(5).fill('filled'));
  assert.equal(trombi.trustMarks(null), null, 'no measure, no meter');
  assert.equal(trombi.castTrust({ trust: 4 }), 4);
  assert.equal(trombi.castTrust({ relationship: { trust: 2 } }), 2, 'nested payload');
  assert.equal(trombi.castTrust({ relationship: { closeness: 5 } }), null, 'closeness is not trust');
  // a fall: yesterday 4, today 2 — the meter shows fewer filled marks
  const before = trombi.trustMarks(trombi.castTrust({ trust: 4 }));
  const after = trombi.trustMarks(trombi.castTrust({ trust: 2 }));
  assert.ok(after.filter((m) => m === 'filled').length < before.filter((m) => m === 'filled').length);
});

test('the register: «tu depuis le 12 sept.» or «vous», in the chrome language', () => {
  const tu = { register: 'tu', tu_since: { date: '2026-09-12', scene_id: 's' } };
  assert.equal(trombi.registerLine(tu, 'fr'), 'tu depuis le 12 sept.');
  assert.equal(trombi.registerLine(tu, 'en'), 'tu since 12 Sep');
  assert.equal(trombi.registerLine(tu, 'de'), 'tu seit 12. Sept.');
  assert.equal(trombi.registerLine({ register: 'tu' }, 'fr'), 'tu');
  assert.equal(trombi.registerLine({ relationship: { register: 'vous' } }, 'fr'), 'vous');
  assert.equal(trombi.registerLine({ register: 'vous', tu_since: { date: '2026-09-12' } }, 'en'), 'vous · formal');
});

test('«Ce que … sait de vous»: five at most, newest first, each dated', () => {
  const facts = Array.from({ length: 7 }, (_, i) => ({ text_fr: `fait ${i}`, date: `2026-09-1${i}`, scene_id: null }));
  const known = trombi.knownAboutYou({ known_about_you: [...facts, { text_fr: '  ', date: null }] });
  assert.equal(known.length, 5);
  assert.deepEqual(known.map((k) => k.text_fr), ['fait 6', 'fait 5', 'fait 4', 'fait 3', 'fait 2']);
  assert.deepEqual(trombi.knownAboutYou({}), []);
});

/* --------------------------------------------------- 6. précédemment */

test('«Précédemment»: ≤3 lines, never on day 1, never twice', () => {
  const lines = ['Un.', ' ', 'Deux.', 'Trois.', 'Quatre.'];
  assert.deepEqual(prev.precedemmentLines(lines), ['Un.', 'Deux.', 'Trois.']);
  assert.deepEqual(prev.precedemmentView({ lines, firstDay: false, dismissed: false }), ['Un.', 'Deux.', 'Trois.']);
  assert.equal(prev.precedemmentView({ lines, firstDay: true, dismissed: false }), null, 'day 1 has no before');
  assert.equal(prev.precedemmentView({ lines, firstDay: false, dismissed: true }), null, 'read once');
  assert.equal(prev.precedemmentView({ lines: [], firstDay: false, dismissed: false }), null);
  assert.equal(prev.precedemmentView({ lines: null, firstDay: false, dismissed: false }), null, 'an older server');
  assert.equal(prev.precedemmentKey('j', 's'), 'atelier:precedemment:j:s');
});

/* ------------------------------------------------------- copy */

test('the copy table is complete in en / de / fr, names stay French', () => {
  const fr = archiveCopy('fr');
  const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
  for (const lang of ['en', 'de']) {
    const table = archiveCopy(lang);
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort());
    for (const key of Object.keys(fr)) {
      assert.ok(String(table[key]).trim(), `${lang}.${key}`);
      assert.equal(holes(table[key]), holes(fr[key]), `${lang}.${key} placeholders`);
    }
    for (const name of ['archive_title', 'cast_title', 'chapter_end', 'tome_n', 'edition_n']) {
      assert.equal(table[name], fr[name], `${name} is a name`);
    }
  }
  assert.equal(archiveCopy().retry, 'Réessayer');
  assert.equal(faPlural(archiveCopy('en'), 'season_pages', 1, { season: 2 }), 'Season 2 · one page');
  assert.equal(archiveDate('2026-09-12'), '12 sept.');
  assert.equal(archiveDate('2026-13-01', 'en'), '');
  assert.equal(archiveDate(null), '');
});

/* ------------------------------------------------------ 7. renders */

const inRoot = (el, language = 'en') => renderToStaticMarkup(h(AtelierV2Root, { language }, el));

test('the volume: the open chapter with its planches, the closed one folded on its digest, the tome', () => {
  const html = decode(inRoot(h(surface.ArchiveVolume, {
    archive: ARCHIVE,
    language: 'en',
    openKeys: ['s2c2'],
    onToggleChapter: () => {},
    onToggleTome: () => {},
  })));
  // open chapter: rows with Nº · date · title, «Numéro spécial» on the épreuve
  assert.match(html, /aria-expanded="true"[\s\S]*Le plombier/);
  assert.match(text(html), /Nº 3 · 14 Sep · Numéro spécial/);
  assert.match(html, /href="\/graphic-novel\?day=2026-09-15&journey=j-2026-09-15"/);
  assert.match(text(html), /Chapter 2 · 2 pages · in progress/);
  // closed chapter: folded, the digest line is its summary, no colophon until opened
  assert.match(html, /aria-expanded="false"[\s\S]*La clé perdue[\s\S]*data-digest/);
  assert.match(text(html), /Qui a pris la clé \? → Marin, pour la rendre à Lila\./);
  assert.doesNotMatch(html, /data-colophon/);
  // the finished season is a tome with a seal
  assert.match(html, /data-tome="1"/);
  assert.match(html, /Tome 1 — season finished/);
  assert.match(text(html), /21 pages/);
  // opening the closed chapter prints the colophon under the mark
  const open = decode(inRoot(h(surface.ArchiveVolume, { archive: ARCHIVE, language: 'fr', openKeys: ['s2c1'], onToggleChapter: () => {} })));
  assert.match(open, /data-colophon[\s\S]*class="av2-mark"[\s\S]*Fin du chapitre/);
  assert.match(text(open), /Chapitre 1 · 2 planches/);
});

test('a planche reread: the reply in Garamond italic, the ending, the notes', () => {
  const d = model.findArchiveDay(ARCHIVE, { date: '2026-09-15' });
  const html = decode(inRoot(h(surface.ArchiveDayPage, { day: { ...d, ending_fr: 'Le plombier arrive.' }, archive: ARCHIVE, language: 'en', episode: null })));
  assert.match(html, /Back to the archive/);
  assert.match(html, /class="fa-reply__line" lang="fr">«\sJe peux vous aider\s\?\s»/);
  assert.match(text(html), /Your reply/);
  assert.match(text(html), /How it ended Le plombier arrive\./);
  // no page to reread: the notes print at the end, signed with the cause's Nº
  assert.match(html, /href="\/graphic-novel\?day=2026-09-13&cause=s-2026-09-13"/);
  assert.match(text(html), /Parce que vous avez dit à Marin « vas-y » — Nº 2/);
  // a day with no reply says so, in the chrome language
  const quiet = decode(inRoot(h(surface.ArchiveDayPage, { day: model.findArchiveDay(ARCHIVE, { date: '2026-09-14' }), language: 'de', episode: null }, ), 'de'));
  assert.match(text(quiet), /An diesem Tag hast du nichts geantwortet\./);
});

test('le trombinoscope: face, register, one trust meter, what they know — no closeness pips', () => {
  const member = {
    id: 'marin', name: 'Marin', role: 'le voisin', accent_colour: null,
    trust: 2, register: 'tu', tu_since: { date: '2026-09-12', scene_id: 's' },
    known_about_you: [{ text_fr: 'Vous avez un chat.', date: '2026-09-14', scene_id: 's' }],
    relationship: { closeness: 5, register: 'tu', mood: -1 },
  };
  const html = decode(inRoot(h(CastCard, { member, language: 'en' })));
  assert.match(html, /role="img" aria-label="Trust: 2 of 5"/);
  assert.equal((html.match(/data-mark="filled"/g) || []).length, 2);
  assert.equal((html.match(/data-mark="empty"/g) || []).length, 3);
  assert.match(text(html), /tu since 12 Sep/);
  assert.match(text(html), /What Marin knows about you 14 Sep Vous avez un chat\./);
  assert.doesNotMatch(html, /closeness|cast-closeness/);
  const fresh = decode(inRoot(h(CastCard, { member: { id: 'lila', name: 'Lila', relationship: { register: 'vous' } }, language: 'fr' }), 'fr'));
  assert.match(text(fresh), /Pas encore d’échange/);
  assert.match(text(fresh), /Lila ne sait encore rien de vous\./);
  assert.match(text(fresh), /vous/);
  const list = inRoot(h(Trombinoscope, { cast: [member], withAvatar: false }));
  assert.match(list, /data-trombinoscope/);
});

test('«Précédemment» renders tappable French and one «Lire»', () => {
  const html = decode(inRoot(h(marks.Precedemment, { lines: ['Marin a trouvé la clé.'], language: 'en', onRead: () => {} })));
  assert.match(html, /data-precedemment/);
  assert.match(text(html), /^Previously/);
  assert.match(html, /<button[^>]*data-word=""[^>]*aria-label="Help with “Marin”"/);
  assert.equal((html.match(/class="av2-btn av2-btn--primary"/g) || []).length, 1, 'one primary');
  assert.match(text(html), /Read$/);
});

test('the recap: «Fin du chapitre» with the digest, «Tome N» pressed, the margin notes', () => {
  const journey = {
    id: 'j', contract_version: 1, revision: 1, status: 'completed', local_date: '2026-09-28', timezone: 'Europe/Paris',
    budget_seconds: 600, estimated_active_seconds: 540, current_step_id: null, scenario: {
      scenario_key: 'k', content_version: '1', title_fr: 'T', objective_key: 'o', objective_native: 'o', level_band: 'A1',
      character_id: 'marin', character_name: 'Marin', location_id: 'l', location_name: 'L', image_url: null,
      serial_thread_id: null, serial_episode_id: null, estimated_seconds: 540,
    }, steps: [], recap: null, retry: null, edition_no: 12, streak: { days: 3, today_done: true, freeze_available: false, freeze_used_on: null },
  };
  const recap = {
    completion_kind: 'complete', objective_outcome: 'met', practiced_targets: [], capability_evidence: [], next_focus: null,
    collectible_ids: [], story_outcome: null, active_seconds: 300,
    margin_notes: [{ text_fr: 'Parce que vous avez aidé Lila', cause_scene_id: 's9', cause_date: '2026-09-20', character_id: 'lila', cause_edition_no: 9 }],
    chapter_closed: { index: 3, title_fr: 'La clé perdue', digest_fr: 'Qui ? → Marin.' },
    season_finished: { number: 1, title_fr: 'S’installer' },
  };
  const html = decode(inRoot(h(JourneyRecap, { journey, recap, language: 'en', onExit: () => {} })));
  assert.match(html, /data-chapter-closed="3"[\s\S]*Fin du chapitre/);
  assert.match(text(html), /Qui \? → Marin\./);
  assert.match(html, /data-season-finished="1"[\s\S]*Tome 1/);
  assert.match(html, /data-stamp="true"/);
  assert.match(text(html), /Season 1 is finished: it is bound as a volume\./);
  assert.match(text(html), /Parce que vous avez aidé Lila — Nº 9/);
  // an older recap draws none of it
  const plain = inRoot(h(JourneyRecap, { journey, recap: { ...recap, margin_notes: undefined, chapter_closed: undefined, season_finished: undefined }, language: 'en' }));
  assert.doesNotMatch(plain, /data-colophon|data-season-finished|data-margin-notes/);
});

test('W14: the Feuilleton chrome never says «La Une» or the old season lines', () => {
  for (const lang of ['en', 'de', 'fr']) {
    const t = archiveCopy(lang);
    for (const value of Object.values(t)) {
      assert.doesNotMatch(String(value), /La Une|first scene opens in the session/);
    }
  }
});
