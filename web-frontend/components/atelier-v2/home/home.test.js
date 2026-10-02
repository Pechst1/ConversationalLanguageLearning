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
      entries: [{ id: 'dossier', label: 'Votre dossier', hint: 'Ce que nous croyons savoir de vous', href: '/dossier' }],
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
    // WP-L7: the level figure («A1.1 · 60 %») is a figure, not prose — it sits
    // outside the word budget, the way the streak's number does not add a sentence.
    // WP-95: the next-step line replaces that figure in the same slot; it is
    // held to its own budget (≤ 9 words) in the WP-95 test below.
    const prose = html
      .replace(/<span aria-hidden="true" data-level-figure="">[\s\S]*?<\/span>/g, ' ')
      .replace(/<a [^>]*data-next-step=""[^>]*>[\s\S]*?<\/a>/g, ' ');
    const count = words(visibleText(prose)).length;
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
    'Votre dossier', // the rows (dossier, documents, practice, rehearsal)
    'Demain', // the colophon
    'Édition Nº', // the kicker
    'Plus de pratique',
    'Vos documents',
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

const NEXT = {
  fr: { band: 'A1.1', line: 'Prochaine étape : demander un prix et payer', ariaLabel: 'Niveau A1.1. Prochaine étape : demander un prix et payer. Ouvrir le Carnet', href: '/notebook?mode=carnet' },
  en: { band: 'A1.1', line: 'Next step: ask a price and pay', ariaLabel: 'Level A1.1. Next step: ask a price and pay. Open the Carnet', href: '/notebook?mode=carnet' },
  de: { band: 'A1.1', line: 'Nächster Schritt: ask a price and pay', ariaLabel: 'Niveau A1.1. Nächster Schritt: ask a price and pay. Carnet öffnen', href: '/notebook?mode=carnet' },
};

test('WP-95 / W12: the masthead shows the band and the next can-do, never a percentage', () => {
  for (const language of ['en', 'de', 'fr']) {
    const html = home(language, { nextStep: NEXT[language], level: { band: 'A1.1', percent: 0 } });
    const text = visibleText(html);
    assert.doesNotMatch(text, /%/, `${language}: no percentage on Home`);
    assert.match(text, new RegExp(`A1\\.1 · ${NEXT[language].line}`), language);
    assert.match(html, /<a class="av2-carnet__home-link"[^>]*href="\/notebook\?mode=carnet"/);
    const link = html.match(/<a [^>]*data-next-step=""[^>]*>([\s\S]*?)<\/a>/)[1];
    assert.ok(words(visibleText(link)).length <= 9, `${language}: the next step is one short line`);
    assert.match(html, /class="av2-home__kicker av2-home__level"/);
    // One Garamond line on the masthead (the date): the level is a label, not a headline.
    const mast = html.slice(html.indexOf('av2-home__mast"'), html.indexOf('</header>'));
    assert.equal((mast.match(/av2-headline[ "]/g) || []).length, 1, `${language}: one headline in the masthead`);
    // Still one press and ≤ 25 words of prose.
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  }
  // An older server (coverage but no can-do): the band code alone — the «0 %» is gone.
  const old = visibleText(home('fr', { level: { band: 'A1.1', percent: 0 } }));
  assert.match(old, /A1\.1/);
  assert.doesNotMatch(old, /%/);
  assert.match(home('fr'), /Votre niveau : A1\.1/);
  // Nothing from the server, no level line.
  assert.doesNotMatch(home('en', { level: null }), /av2-home__level/);
});

test('WP-94: a special edition double-rules the masthead; an ordinary day does not', () => {
  assert.match(home('fr', { special: true }), /<header class="av2-home__mast" data-special="">/);
  assert.doesNotMatch(home('fr'), /data-special/);
});

test('WP-L6: «Cette semaine, on consolide.» on Home while the throttle is on, in the chrome language', () => {
  assert.doesNotMatch(home('fr'), /data-consolidating/);
  assert.match(visibleText(home('fr', { consolidating: true })), /Cette semaine, on consolide\./);
  assert.match(visibleText(home('en', { consolidating: true })), /This week, we consolidate\./);
  assert.match(visibleText(home('de', { consolidating: true })), /Diese Woche festigen wir\./);
  const mast = home('fr', { consolidating: true });
  const header = mast.slice(mast.indexOf('av2-home__mast"'), mast.indexOf('</header>'));
  assert.equal((header.match(/av2-headline[ "]/g) || []).length, 1, 'a label, never a second headline');
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
  const de = visibleText(home('de'));
  assert.match(de, /4 Tage/);
  assert.match(de, /Szene Wörter Antwort Fertig/);
  assert.match(de, /Heute starten/);
  assert.doesNotMatch(de, /jours de suite|Commencer|Start today/);
  const fr = visibleText(home('fr'));
  assert.match(fr, /jours de suite/);
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
      entries: [{ id: 'dossier', label: 'Votre dossier', href: '/dossier' }],
      tiles: [],
      colophon: { lead: 'Demain — ', focus: 'le passé composé', focusHref: '/grammar' },
    }),
  );
  const text = visibleText(html);
  assert.match(text, /Édition Nº 4 · A1\.1/);
  assert.match(text, /Votre dossier/);
  assert.match(text, /Demain/);
  assert.match(html, /aria-label="4 jours de suite · vos sceaux"/);
  assert.doesNotMatch(html, /av2-home__chips/);
});

// WP-119 · La Revue on La Une, as data in the existing slots (no HomeScreen change):
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
    assert.match(visibleText(html), /New letter La Revue|Neuer Brief La Revue|Nouvelle lettre La Revue|La Revue/);
    assert.match(html, /aria-label="[^"]*(semaine|week|Woche) 40"/, 'the week is in the label, not the 25 words');
    assert.ok(words(prose(html)).length <= 25, `${language}: ${visibleText(html)}`);
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, 'a chip is never a press');
  }
  assert.equal(revueHomeChip({ enabled: false }, 'en'), null, 'flag off: no chip');
  assert.equal(revueHomeChip({ enabled: true, offer: revueTypes.parseOffer(REVUE.offer_filed) }, 'en'), null, 'filed: no chip');
  const resume = revueHomeChip({ enabled: true, offer: revueTypes.parseOffer(REVUE.offer_resume) }, 'fr');
  assert.match(resume.href, /^\/revue\?session=/);
});
