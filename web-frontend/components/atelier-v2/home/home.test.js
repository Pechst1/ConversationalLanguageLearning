// node --test components/atelier-v2/home/home.test.js
//
// WP-81 — Home does one thing; WP-82 — the text diet and one language rule.
//
//   1. with the journey on, Home is the masthead, the day's card, the plan row
//      and at most one quiet row of chips: ≤ 5 elements and ≤ 25 visible
//      words at the offer, for an English, a German and a French learner;
//   2. nothing else is drawn in that mode — no episode, second action, phrase,
//      library, rows or colophon — and the edition kicker is cut;
//   3. at most two chips, one once the day is done; a chip is never a press;
//   4. one language per element: the streak, the plan row and the chips follow
//      the chrome language; the day's card never mixes two.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
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

const { HomeScreen } = require('./HomeScreen.tsx');
const { JourneyTodayCard } = require('../journey/JourneyTodayCard.tsx');
const state = require('../journey/journey-state.ts');
const { dayMarkState } = require('../journey/day-mark.ts');
const { atelierCopy } = require('@/lib/atelier-v2-copy.ts');

const h = React.createElement;
const FIXTURES = path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public');
const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIXTURES, `${name}.json`), 'utf8')).response;

const decode = (html) =>
  html
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
/** What a sighted learner reads: no screen-reader-only spans, no markup. */
const visibleText = (html) =>
  decode(html.replace(/<span class="av2-sr">[\s\S]*?<\/span>/g, ' ').replace(/<[^>]+>/g, ' '))
    .replace(/\s+/g, ' ')
    .trim();
const words = (text) => text.split(' ').filter((token) => /[\p{L}\p{N}]/u.test(token));

function controllerFor(envelope, language) {
  return {
    phase: state.phaseFromEnvelope(envelope),
    feedback: { kind: 'idle' },
    envelope,
    journey: envelope.journey ?? null,
    step: null,
    respondPrompt: null,
    controlLanguage: language,
    legacyResume: envelope.legacy_resume ?? null,
    progress: state.journeyProgress(envelope.journey ?? null),
    busy: false,
    help: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
}

function home(language, props = {}) {
  const envelope = { ...fixture('first_day'), control_language: language };
  return renderToStaticMarkup(
    h(HomeScreen, {
      dateLabel: 'mardi 23 septembre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      level: { band: 'A1.1', percent: 60 },
      language,
      day: dayMarkState(null, language),
      hero: h(JourneyTodayCard, { controller: controllerFor(envelope, language), onOpen: () => {} }),
      chips: [
        { id: 'courrier', label: atelierCopy(language).home_letter, ariaLabel: atelierCopy(language).home_letter_aria, href: '/missions?mission=1', shape: 'story' },
        { id: 'lexique', label: atelierCopy(language).home_words_many.replace('{n}', '3'), ariaLabel: atelierCopy(language).home_review_many.replace('{n}', '3'), href: '/vocabulary/review' },
      ],
      // Everything below is ignored while the journey owns the day.
      episode: { kicker: 'Feuilleton', headline: 'Un autre épisode', artUrl: null, artState: 'none', byline: 'Marin' },
      action: { label: 'Continuer', onSelect: () => {} },
      phrase: { text: 'Je reviens.', byline: 'Marin' },
      library: { title: 'Le Livre', chapter: 2, href: '/notebook' },
      entries: [{ id: 'dossier', label: 'Ton dossier', hint: 'Ce que nous croyons savoir de toi', href: '/dossier' }],
      tiles: [],
      colophon: { lead: 'Demain — ', focus: 'le passé composé', focusHref: '/grammar', tail: ', épisode 5.' },
      ...props,
    }),
  );
}

test('Home does one thing: ≤ 5 elements and ≤ 25 words, in every learner language', () => {
  for (const language of ['en', 'de', 'fr']) {
    const html = home(language);
    const sections = (html.match(/class="av2-home__mast"|class="av2-home__section[ "]/g) || []).length;
    assert.ok(sections <= 5, `${language}: ${sections} elements`);
    const count = words(visibleText(html)).length;
    if (process.env.HOME_WORDS) console.log(language, sections, count, visibleText(html));
    assert.ok(count <= 25, `${language}: ${count} words — ${visibleText(html)}`);
    // Exactly one red press: the day's.
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, `${language}: one primary`);
  }
});

test('with the journey on, nothing but the day is drawn', () => {
  const html = home('en');
  const text = visibleText(html);
  for (const gone of [
    'Un autre épisode', // a second episode card
    'Continuer', // a second action
    'Je reviens', // yesterday's phrase
    'Le Livre', // the library
    'Ton dossier', // the rows (dossier, documents, practice, rehearsal)
    'Demain', // the colophon
    'Édition Nº', // the kicker
    'Plus de pratique',
    'Tes documents',
  ]) {
    assert.ok(!text.includes(gone), `«${gone}» is not on Home`);
  }
  // The day is: the date, the card, the plan row, the chips.
  assert.match(text, /mardi 23 septembre/);
  assert.match(text, /Start today/);
  assert.match(text, /Scene Words Reply Done/);
  assert.match(text, /New letter/);
  assert.match(html, /aria-label="A letter is waiting"/);
  assert.match(text, /3 words/);
  assert.match(html, /aria-label="Review 3 words"/);
});

test('owner 2026-10-18: the masthead is the mark, the date and the streak, nothing else', () => {
  // The level line («B1.1 · Prochaine étape : …») and «Cette semaine, on consolide.»
  // are gone from Home, whatever the server sends; the next can-do lives in the Carnet.
  for (const language of ['en', 'de', 'fr']) {
    const html = home(language, {
      nextStep: { band: 'B1.1', line: 'Prochaine étape : donner son opinion', ariaLabel: 'x', href: '/notebook?mode=releve#carnet' },
      level: { band: 'B1.1', percent: 40 },
      consolidating: true,
    });
    const mast = html.slice(html.indexOf('av2-home__mast"'), html.indexOf('</header>'));
    assert.doesNotMatch(mast, /B1\.1|Prochaine étape|data-next-step|av2-home__level/, language);
    assert.doesNotMatch(html, /data-consolidating|on consolide|we consolidate|festigen wir/, language);
    assert.equal((mast.match(/av2-headline[ "]/g) || []).length, 1, `${language}: one headline in the masthead`);
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  }
});

test('owner 2026-10-18: the streak is a pile of saucers beside the number, no phrase', () => {
  const { saucersFor } = require('./StreakSaucers.tsx');
  assert.deepEqual([0, 1, 2, 5, 7, 300].map(saucersFor), [0, 1, 2, 5, 5, 5], 'one saucer a day, five at most');
  const fr = home('fr', { streak: 7 });
  const streak = fr.slice(fr.indexOf('class="av2-home__streak"'), fr.indexOf('</a>', fr.indexOf('class="av2-home__streak"')));
  assert.match(streak, /<svg class="av2-saucers"[^>]*aria-hidden="true"[^>]*data-saucers="5"/);
  assert.match(streak, /aria-label="7 jours de suite · tes sceaux"/);
  const inner = streak.slice(streak.indexOf('>') + 1);
  assert.doesNotMatch(visibleText(inner), /jours/, 'the words are the link’s name, not printed');
  assert.match(visibleText(inner).trim(), /^7$/);
  // Today's cup steams once today is done; not before.
  assert.doesNotMatch(streak, /data-steaming/);
  assert.match(home('fr', { streak: 7, dayDone: true }), /data-steaming=""/);
  assert.match(home('fr', { streak: 7, dayDone: true }), /aria-label="7 jours de suite · journée bouclée · tes sceaux"/);
  // No streak, no mark.
  assert.doesNotMatch(home('fr', { streak: 0 }), /av2-saucers/);
});

test('WP-94: a special edition double-rules the masthead; an ordinary day does not', () => {
  assert.match(home('fr', { special: true }), /<header class="av2-home__mast" data-special="">/);
  assert.doesNotMatch(home('fr'), /data-special/);
});

test('at most two chips, one once the day is done, and never a press', () => {
  const three = home('en', {
    chips: [
      { id: 'a', label: 'One', href: '/a' },
      { id: 'b', label: 'Two', href: '/b' },
      { id: 'c', label: 'Three', href: '/c' },
    ],
  });
  assert.equal((three.match(/data-chip=/g) || []).length, 2);
  assert.doesNotMatch(visibleText(three), /Three/);
  const done = home('en', { dayDone: true });
  assert.equal((done.match(/data-chip=/g) || []).length, 1, 'after the day: one next suggestion');
  assert.match(visibleText(done), /New letter/);
  const button = home('en', { chips: [{ id: 'x', label: 'Open', href: '/x', onSelect: () => {} }] });
  assert.match(button, /<button type="button" class="av2-chip" data-chip="x"/);
  assert.equal((button.match(/av2-btn--primary/g) || []).length, 1, 'still only the day’s press');
  // No chips: no row at all.
  assert.doesNotMatch(home('en', { chips: [] }), /av2-home__chips/);
});

test('one language per element: the streak, the plan and the chips follow the chrome language', () => {
  const en = home('en');
  assert.match(en, /aria-label="4 days · your seals"/);
  assert.match(en, /<ol class="av2-day-plan" aria-label="Today’s plan">/);
  assert.match(en, /aria-label="Today: 0 of 4 — /);
  assert.match(home('de'), /aria-label="4 Tage · Deine Siegel"/);
  const de = visibleText(home('de'));
  assert.match(de, /Szene Wörter Antwort Fertig/);
  assert.match(de, /Heute starten/);
  assert.doesNotMatch(de, /jours de suite|Commencer|Start today/);
  assert.match(home('fr'), /aria-label="4 jours de suite · tes sceaux"/);
  const fr = visibleText(home('fr'));
  assert.match(fr, /Scène Mots Réponse Bouclé/);
  assert.match(fr, /Commencer/);
  // The day's card is one chrome language; its French is the scene's title.
  const card = visibleText(renderToStaticMarkup(
    h(JourneyTodayCard, {
      controller: controllerFor({ ...fixture('first_day'), control_language: 'de' }, 'de'),
      onOpen: () => {},
    }),
  ));
  assert.match(card, /Heute/);
  assert.doesNotMatch(card, /Aujourd|Commencer/);
});

test('the flag-off Home is unchanged: French, the kicker, the rows and the colophon', () => {
  const html = renderToStaticMarkup(
    h(HomeScreen, {
      dateLabel: 'mardi 23 septembre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      episode: null,
      action: null,
      entries: [{ id: 'dossier', label: 'Ton dossier', href: '/dossier' }],
      tiles: [],
      colophon: { lead: 'Demain — ', focus: 'le passé composé', focusHref: '/grammar' },
    }),
  );
  const text = visibleText(html);
  assert.match(text, /Édition Nº 4 · A1\.1/);
  assert.match(text, /Ton dossier/);
  assert.match(text, /Demain/);
  assert.match(html, /aria-label="4 jours de suite · tes sceaux"/);
  assert.doesNotMatch(html, /av2-home__chips/);
});

// WP-119 · Le Papier on La Une, as data in the existing slots (no HomeScreen change):
// the Revue day's hero card with the plan row hidden, and the other days' chip.
const revueTypes = require('@/lib/revue-types.ts');
const { RvUneCard } = require('@/components/revue/RvUneCard.tsx');
const { revueCopy } = require('@/components/revue/revue-copy.ts');
const { revueHomeChip, revueUneState } = require('@/components/revue/revue-home.ts');
// The drawn rigs use the automatic JSX runtime's global React.
global.React = React;
/** The prose of Home, as the first test counts it (the level figure is a figure, not prose). */
const prose = (html) => visibleText(html.replace(/<span aria-hidden="true" data-level-figure="">[\s\S]*?<\/span>/g, ' '));
const REVUE = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, 'components/revue/fixtures/mock-wire.json'), 'utf8'));

function revueHero(language, offer, extra = {}) {
  const state = revueUneState(offer);
  return h(RvUneCard, {
    story: offer.recommended,
    week: offer.week,
    state,
    onOpen: () => {},
    onOtherSubject: () => {},
    copy: revueCopy(language),
    ...extra,
  });
}

test('WP-119: the Revue card on La Une does one thing: ≤ 5 elements, ≤ 25 words, one primary, in en/de/fr', () => {
  const offer = revueTypes.parseOffer(REVUE.offer);
  // A long title too (9 words): the card drops the place, then the week, then the topic, never the story.
  const long = { ...offer, recommended: { ...offer.recommended, titleFr: 'Un jour de grève dans les transports de la ville', evergreen: false } };
  for (const language of ['en', 'de', 'fr']) {
    for (const variant of [offer, long]) {
      const html = home(language, { hero: revueHero(language, variant), planHidden: true, chips: [] });
      const sections = (html.match(/class="av2-home__mast"|class="av2-home__section[ "]/g) || []).length;
      assert.ok(sections <= 5, `${language}: ${sections} elements`);
      const count = words(prose(html)).length;
      if (process.env.HOME_WORDS) console.log('revue', language, sections, count, visibleText(html));
      assert.ok(count <= 25, `${language}: ${count} words — ${visibleText(html)}`);
      assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, `${language}: one primary`);
      assert.doesNotMatch(html, /av2-day-plan/, 'the plan row is hidden: the card is the route');
      assert.match(visibleText(html), new RegExp(variant.recommended.titleFr.slice(0, 20)));
    }
    // Resume: one clause from the state, «Reprendre avec Romy».
    const resumeOffer = revueTypes.parseOffer(REVUE.offer_resume);
    const copy = revueCopy(language);
    const resume = home(language, {
      hero: revueHero(language, resumeOffer, { resumeLine: copy.resume_line_question.replace('{when}', copy.started_yesterday) }),
      planHidden: true,
      chips: [],
    });
    assert.ok(words(prose(resume)).length <= 25, `${language} resume: ${visibleText(resume)}`);
    assert.equal((resume.match(/av2-btn--primary/g) || []).length, 1);
    // Filed: no press at all; the day's other chip may show.
    const filedOffer = revueTypes.parseOffer(REVUE.offer_filed);
    const filed = home(language, { hero: revueHero(language, filedOffer, { filed: { made: filedOffer.filed.made } }), planHidden: true, chips: [] });
    assert.equal((filed.match(/av2-btn--primary/g) || []).length, 0);
    assert.ok(words(prose(filed)).length <= 25, `${language} filed: ${visibleText(filed)}`);
  }
});

test('WP-119: on other days the Revue is one quiet chip beside the letter, gone once filed or switched off', () => {
  const week = { enabled: true, offer: revueTypes.parseOffer(REVUE.offer) };
  for (const language of ['en', 'de', 'fr']) {
    const chip = revueHomeChip(week, language);
    assert.equal(chip.href, '/revue');
    const html = home(language, {
      chips: [
        { id: 'courrier', label: atelierCopy(language).home_letter, href: '/missions?mission=1', shape: 'story' },
        chip,
        { id: 'lexique', label: '3 words', href: '/vocabulary/review' },
      ],
    });
    assert.equal((html.match(/data-chip=/g) || []).length, 2, 'letter first, then the Revue');
    assert.match(html, /data-chip="revue"/);
    assert.match(visibleText(html), /New letter Le Papier|Neuer Brief Le Papier|Nouvelle lettre Le Papier|Le Papier/);
    assert.match(html, /aria-label="[^"]*(semaine|week|Woche) 40"/, 'the week is in the label, not the 25 words');
    assert.ok(words(prose(html)).length <= 25, `${language}: ${visibleText(html)}`);
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, 'a chip is never a press');
  }
  assert.equal(revueHomeChip({ enabled: false }, 'en'), null, 'flag off: no chip');
  {
    // WP-119 §12.2: once filed, the chip stays only as a quiet offer of another Papier when the kiosk has more.
    const filedOffer = revueTypes.parseOffer(REVUE.offer_filed);
    const filedChip = revueHomeChip({ enabled: true, offer: filedOffer }, 'en');
    if ((filedOffer.alternatives ?? []).length > 0) {
      assert.equal(filedChip.label, 'Another Papier?');
      assert.equal(filedChip.href, '/revue');
    } else {
      assert.equal(filedChip, null, 'filed with nothing else at the kiosk: no chip');
    }
  }
  const resume = revueHomeChip({ enabled: true, offer: revueTypes.parseOffer(REVUE.offer_resume) }, 'fr');
  assert.match(resume.href, /^\/revue\?session=/);
});

// Owner, 2026-10-19: a generated day has no title yet, and yesterday's whole
// «À suivre…» stood in at headline size. The headline is its heart, once.
test('an untitled day headlines the teaser’s heart, not the whole teaser', () => {
  const base = fixture('first_day');
  const envelope = {
    ...base,
    control_language: 'fr',
    available: { ...base.available, title_fr: 'Votre prochain chapitre' },
    headline: {
      edition_no: 7,
      title_fr: '',
      season_title_fr: 'La clé d’Odile',
      teaser_fr:
        'Toi, tu me caches quelque chose… Demain, peut-être, on saura : « Lila et Berlin : peut-on vouloir quelqu’un ici, et vouloir son départ pour elle ? »',
      cast: [],
    },
  };
  const html = renderToStaticMarkup(h(JourneyTodayCard, { controller: controllerFor(envelope, 'fr'), onOpen: () => {} }));
  const title = decode((html.match(/<h2 class="av2-headline av2-headline--title"[^>]*>([\s\S]*?)<\/h2>/) || [])[1] || '');
  assert.equal(title, 'Lila et Berlin');
  assert.doesNotMatch(visibleText(html), /caches quelque chose/);
  assert.equal((visibleText(html).match(/Lila et Berlin/g) || []).length, 1);
});
