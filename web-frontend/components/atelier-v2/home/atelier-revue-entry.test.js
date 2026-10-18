// node --test components/atelier-v2/home/atelier-revue-entry.test.js
//
// WP-119 phase 1 — Le Papier's entry on La Une, as `pages/atelier.tsx` wires it.
// The page has no mount harness, so the decision lives in `lib/revue-une.ts`
// (pure) and is rendered here through the real HomeScreen with the same props
// the page passes; a source check pins the page to that helper.
//
//   1. the Revue off (404 → `{ enabled: false }`), unread or failed: no chip, no card;
//   2. an ordinary day with a live dossier: the news card under the day's card
//      (2026-10-18; it replaced the chip), every day until the Papier is filed;
//      the Revue day (`DayShape.REVUE`): the card in `hero` with `planHidden`;
//   3. a session to resume: the card's state is `resume`, its press goes to `/revue?session=`;
//   4. a letter and a Revue the same day: design spec §2 — letter first, then the Revue;
//   5. a special edition never gives its hero to the Revue.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const { WEB_ROOT, h, render, visibleText, fixture: revueFixture } = require('../../revue/revue-test-setup.js');

const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const { HomeScreen } = require('./HomeScreen.tsx');
const { JourneyTodayCard } = require('../journey/JourneyTodayCard.tsx');
const state = require('../journey/journey-state.ts');
const { dayMarkState } = require('../journey/day-mark.ts');
const { atelierCopy } = require('@/lib/atelier-v2-copy.ts');
const revueTypes = require('@/lib/revue-types.ts');
const { RvUneCard } = require('@/components/revue/RvUneCard.tsx');
const { RvNewsCard } = require('@/components/revue/RvNewsCard.tsx');
const { revueCopy } = require('@/components/revue/revue-copy.ts');
const une = require('@/lib/revue-une.ts');

const WIRE = revueFixture('mock-wire');
const evergreenOffer = revueTypes.parseOffer(WIRE.offer);
/** This week's offer with a live (non-evergreen) dossier recommended. */
const liveOffer = {
  ...evergreenOffer,
  evergreenOnly: false,
  recommended: { ...evergreenOffer.recommended, dossierId: 'dossier-2026-w40-velib', titleFr: 'Les Vélib’ changent de prix', evergreen: false },
};
const resumeOffer = revueTypes.parseOffer(WIRE.offer_resume);
const filedOffer = revueTypes.parseOffer(WIRE.offer_filed);
const live = { enabled: true, offer: liveOffer };
const NOW = new Date('2026-10-02T09:00:00Z');

const words = (text) => text.split(' ').filter((token) => /[\p{L}\p{N}]/u.test(token));
const prose = (html) => visibleText(html.replace(/<span aria-hidden="true" data-level-figure="">[\s\S]*?<\/span>/g, ' '));
const FIXTURES = path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public');
const dayFixture = (name) => JSON.parse(fs.readFileSync(path.join(FIXTURES, `${name}.json`), 'utf8')).response;

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

const letterChip = (language) => ({
  id: 'courrier',
  label: atelierCopy(language).home_letter,
  ariaLabel: atelierCopy(language).home_letter_aria,
  href: '/missions?mission=1',
  shape: 'story',
});
const wordsChip = { id: 'lexique', label: '3 words', href: '/vocabulary/review', shape: 'reward' };

/**
 * La Une as `TodayView` composes it: the Revue entry decides the hero (else the
 * journey card), `planHidden`, and the chip spliced in after the letter.
 */
function laUne(language, { week, dayShape = 'standard', special = false, letter = true, dayDone = false } = {}) {
  const entry = une.revueUneEntry({ week, language, dayShape, special });
  const copy = revueCopy(language);
  let hero = h(JourneyTodayCard, { controller: controllerFor({ ...dayFixture('first_day'), control_language: language }, language), onOpen: () => {} });
  if (entry.hero) {
    const { offer, story, state: cardState } = entry.hero;
    hero = h(RvUneCard, {
      story,
      week: offer.week,
      state: cardState,
      resumeLine: cardState === 'resume' ? une.revueResumeLine(offer, copy, NOW) : null,
      filed: cardState === 'filed' && offer.filed ? { made: offer.filed.made, headlineFr: offer.filed.dispatch?.headlineFr ?? offer.filed.titleFr } : null,
      onOpen: () => {},
      onOtherSubject: () => {},
      copy,
    });
  }
  if (entry.news) hero = h(React.Fragment, null, hero, h(RvNewsCard, { story: entry.news.story, href: entry.news.href, copy }));
  const unfiledAfterDay = dayDone && Boolean(week?.enabled && !week.offer.filed);
  const chips = une.revueHomeChips(entry, [...(letter ? [letterChip(language)] : []), wordsChip], unfiledAfterDay);
  const html = render(
    h(HomeScreen, {
      dateLabel: 'vendredi 2 octobre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      level: { band: 'A1.1', percent: 60 },
      language,
      day: dayMarkState(null, language),
      dayDone,
      special,
      hero,
      planHidden: Boolean(entry.hero),
      chips,
    }),
  );
  return { entry, chips, html };
}

const NEWS_CARD = /<a class="rv-news"[\s\S]*?<\/a>/;

/**
 * WP-81: ≤ 5 elements and ≤ 25 words. 2026-10-18 (owner): the news card sits under
 * the day's card on top of that budget, and spends at most nine words of its own
 * (the sticker's three, a headline of six).
 */
function assertHomeBudget(html, label) {
  const sections = (html.match(/class="av2-home__mast"|class="av2-home__section[ "]/g) || []).length;
  assert.ok(sections <= 5, `${label}: ${sections} elements`);
  const card = html.match(NEWS_CARD);
  const count = words(prose(html.replace(NEWS_CARD, ' '))).length;
  assert.ok(count <= 25, `${label}: ${count} words — ${visibleText(html)}`);
  if (card) assert.ok(words(prose(card[0])).length <= 9, `${label}: the news card — ${visibleText(card[0])}`);
}

test('the Revue off, unread or failed: La Une is exactly as before — no chip, no card', () => {
  for (const week of [{ enabled: false }, null, undefined]) {
    for (const dayShape of ['standard', une.REVUE_DAY_SHAPE]) {
      assert.deepEqual(une.revueUneEntry({ week, language: 'en', dayShape, special: false }), { chip: null, hero: null, news: null });
    }
  }
  const off = laUne('en', { week: { enabled: false }, dayShape: une.REVUE_DAY_SHAPE });
  assert.doesNotMatch(off.html, /data-chip="revue"|data-revue-card|rv-une|rv-news/);
  assert.match(off.html, /av2-day-plan/, 'the plan row stays');
  assert.deepEqual(off.chips.map((chip) => chip.id), ['courrier', 'lexique']);
  // And identical to a Home that never heard of the Revue.
  assert.equal(off.html, laUne('en', { week: null }).html);
});

test('a live dossier: the news card under the day on an ordinary day, the card in hero with planHidden on the Revue day, in en/de/fr', () => {
  for (const language of ['en', 'de', 'fr']) {
    const ordinary = laUne(language, { week: live });
    assert.equal(ordinary.entry.hero, null, 'any other day: no hero');
    assert.equal(ordinary.entry.chip, null, 'the news card replaced the «Le Papier» chip');
    assert.equal(ordinary.entry.news.href, '/revue');
    assert.equal(ordinary.entry.news.story.dossierId, 'dossier-2026-w40-velib');
    assert.doesNotMatch(ordinary.html, /data-chip="revue"/);
    assert.match(ordinary.html, /data-revue-card="news"/);
    assert.match(ordinary.html, /class="rv-news__sticker"[^>]*>À la une !/, 'the sticker says it is the news');
    assert.match(visibleText(ordinary.html), /Les Vélib’ changent de prix/, 'no short headline yet: the title');
    assert.ok(ordinary.html.indexOf('av2-journey-today') < ordinary.html.indexOf('rv-news'), 'under the day\'s card');
    assert.match(ordinary.html, /av2-day-plan/);
    assert.equal((ordinary.html.match(/av2-btn--primary/g) || []).length, 1, 'the card is a link, never a second press');
    assertHomeBudget(ordinary.html, `${language} news card`);
    // After the day the card stays until the Papier is filed.
    assert.match(laUne(language, { week: live, dayDone: true }).html, /data-revue-card="news"/);
    // The six-word headline when the dossier has one.
    const short = { enabled: true, offer: { ...liveOffer, recommended: { ...liveOffer.recommended, headlineFr: 'Le Vélib’ coûte plus cher' } } };
    const withHeadline = laUne(language, { week: short });
    assert.match(visibleText(withHeadline.html), /Le Vélib’ coûte plus cher/);
    assert.doesNotMatch(visibleText(withHeadline.html), /changent de prix/);

    const revueDay = laUne(language, { week: live, dayShape: une.REVUE_DAY_SHAPE });
    assert.equal(revueDay.entry.hero.state, 'offer');
    assert.equal(revueDay.entry.hero.story.dossierId, 'dossier-2026-w40-velib');
    assert.equal(revueDay.entry.chip, null, 'the hero is the door: no second Revue chip');
    assert.match(revueDay.html, /data-revue-card="offer"/);
    assert.match(visibleText(revueDay.html), /Les Vélib’ changent de prix/);
    assert.doesNotMatch(revueDay.html, /av2-day-plan/, 'planHidden: the card is the route');
    assert.doesNotMatch(revueDay.html, /data-chip="revue"/);
    assert.equal((revueDay.html.match(/av2-btn--primary/g) || []).length, 1, `${language}: one primary`);
    assertHomeBudget(revueDay.html, `${language} hero`);
  }
  // The evergreen week labels itself.
  assert.equal(une.revueUneEntry({ week: { enabled: true, offer: evergreenOffer }, language: 'fr', dayShape: 'revue', special: false }).hero.state, 'evergreen');
  assert.equal(une.revueOpenHref(liveOffer), '/revue');
  assert.equal(une.revueDossierHref('evergreen-greve-transports'), '/revue?dossier=evergreen-greve-transports');
});

test('a session to resume: the card says resume, its press goes to /revue?session=', () => {
  for (const language of ['en', 'de', 'fr']) {
    const { entry, html } = laUne(language, { week: { enabled: true, offer: resumeOffer }, dayShape: une.REVUE_DAY_SHAPE });
    assert.equal(entry.hero.state, 'resume');
    assert.equal(entry.hero.story.dossierId, resumeOffer.resume.dossierId, 'the story being resumed');
    assert.match(html, /data-revue-card="resume"/);
    assert.doesNotMatch(html, /av2-day-plan/);
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
    assertHomeBudget(html, `${language} resume`);
  }
  assert.equal(une.revueOpenHref(resumeOffer), `/revue?session=${resumeOffer.resume.sessionId}`);
  // The clause: an open question waits; otherwise the beat it stopped at.
  const fr = revueCopy('fr');
  assert.equal(une.revueResumeLine(resumeOffer, fr, NOW), 'Commencée hier · ta question attend.');
  const noQuestion = { ...resumeOffer, resume: { ...resumeOffer.resume, openQuestionFr: null } };
  assert.equal(une.revueResumeLine(noQuestion, revueCopy('en'), NOW), `${revueCopy('en').started_yesterday} · you were on «Follow up».`);
  assert.equal(une.revueResumeLine(liveOffer, fr, NOW), null);
  // On an ordinary day the news card resumes too, on the story being resumed.
  const news = une.revueUneEntry({ week: { enabled: true, offer: resumeOffer }, language: 'fr', dayShape: 'standard', special: false }).news;
  assert.match(news.href, /^\/revue\?session=/);
  assert.equal(news.story.dossierId, resumeOffer.resume.dossierId);
});

test('a letter and a Revue the same day: §2 — the letter first, then the Revue, then words due', () => {
  for (const language of ['en', 'de', 'fr']) {
    // 2026-10-18: the Revue is the news card under the day's card, so the chip row is
    // the letter's and words due's again.
    const both = laUne(language, { week: live });
    assert.deepEqual(both.chips.map((chip) => chip.id), ['courrier', 'lexique']);
    const shown = [...both.html.matchAll(/data-chip="([^"]+)"/g)].map((match) => match[1]);
    assert.deepEqual(shown, ['courrier', 'lexique'], `${language}: HomeScreen's two`);
    assert.match(both.html, /data-revue-card="news"/);
    assert.equal((both.html.match(/av2-btn--primary/g) || []).length, 1, 'a chip is never a press');
    assertHomeBudget(both.html, `${language} letter + revue`);
    // Once the day is done HomeScreen keeps one chip, the letter; today's unread
    // Papier keeps its card (2026-10-18 «the news did not appear»).
    const done = laUne(language, { week: live, dayDone: true });
    assert.deepEqual([...done.html.matchAll(/data-chip="([^"]+)"/g)].map((match) => match[1]), ['courrier']);
    assert.match(done.html, /data-revue-card="news"/);
    // A filed Papier: no card, the letter keeps the one chip.
    const filedWeek = { enabled: true, offer: { ...live.offer, filed: { sessionId: 's', dossierId: live.offer.recommended.dossierId, titleFr: 'x', closedAt: NOW.toISOString(), made: null, dispatch: null } } };
    const doneFiled = laUne(language, { week: filedWeek, dayDone: true });
    assert.deepEqual([...doneFiled.html.matchAll(/data-chip="([^"]+)"/g)].map((match) => match[1]), ['courrier']);
    assert.doesNotMatch(doneFiled.html, /rv-news/);
    // A special edition keeps the quiet chip, after the letter (and first without one).
    const special = laUne(language, { week: live, special: true });
    assert.deepEqual(special.chips.map((chip) => chip.id), ['courrier', 'revue', 'lexique']);
    assert.deepEqual(laUne(language, { week: live, letter: false, special: true }).chips.map((chip) => chip.id), ['revue', 'lexique']);
    // The Revue day: the Revue is the day's route and takes La Une whole — its
    // card spends the words a chip would need; the letter waits in the Courrier.
    for (const offer of [liveOffer, resumeOffer]) {
      const revueDay = laUne(language, { week: { enabled: true, offer }, dayShape: une.REVUE_DAY_SHAPE });
      assert.match(revueDay.html, /data-revue-card=/);
      assert.doesNotMatch(revueDay.html, /data-chip=|av2-home__chips/);
    }
  }
});

test('a special edition keeps its hero; a filed Revue never takes the hero', () => {
  const special = laUne('fr', { week: live, dayShape: une.REVUE_DAY_SHAPE, special: true });
  assert.equal(special.entry.hero, null, 'never on a special edition');
  assert.match(special.html, /data-chip="revue"/, 'the Revue stays a chip');
  assert.match(special.html, /av2-day-plan/);

  // 2026-10-14 (owner, iPhone): a filed Papier pushed today's day card off
  // Home on the Revue day. Filed, it gives the hero back to the day.
  for (const language of ['en', 'de', 'fr']) {
    const filed = laUne(language, { week: { enabled: true, offer: filedOffer }, dayShape: une.REVUE_DAY_SHAPE });
    assert.equal(filed.entry.hero, null, `${language} filed: no hero on the Revue day`);
    assert.doesNotMatch(filed.html, /data-revue-card=/);
    assert.match(filed.html, /av2-day-plan/, `${language} filed: the day's plan row is back`);
  }
  const filedOrdinary = laUne('en', { week: { enabled: true, offer: filedOffer } });
  assert.equal(filedOrdinary.entry.hero, null, 'filed: no hero on an ordinary day');
  if ((filedOffer.alternatives ?? []).length > 0) {
    assert.equal(filedOrdinary.entry.chip.label, 'Another Papier?', 'filed: a quiet offer of another Papier (WP-119 §12.2)');
  } else {
    assert.equal(filedOrdinary.entry.chip, null, 'filed with nothing else at the kiosk: no chip');
  }
});

test('the day shape is read from the journey, else the envelope', () => {
  assert.equal(une.dayShapeFrom({ day_shape: 'revue' }, null), 'revue');
  assert.equal(une.dayShapeFrom(null, { journey: { day_shape: 'letter' } }), 'letter');
  assert.equal(une.dayShapeFrom(null, { day_shape: 'revue' }), 'revue');
  assert.equal(une.dayShapeFrom({ day_shape: '' }, null), null);
  assert.equal(une.dayShapeFrom(null, null), null);
  assert.equal(une.isRevueDay('revue', false), true);
  assert.equal(une.isRevueDay('revue', true), false);
  assert.equal(une.isRevueDay('standard', false), false);
});

test('pages/atelier.tsx wires La Une through lib/revue-une.ts, beside the day and never ahead of it', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(page, /oncePerLoad\('revue\/week', \(\) => revueClient\(\)\.week\(\)\)/);
  assert.match(page, /\.catch\(\(\) => \{ \/\* the Revue is an enrichment/, 'a failed read is swallowed');
  assert.match(page, /revueUneEntry\(\{[\s\S]*?dayShape: dayShapeFrom\(dayJourney, dayEnvelope\),[\s\S]*?special: specialEdition,/);
  assert.match(page, /revueHomeChips<HomeChip>\(revueEntry, dayChips, revueDayDone && Boolean\(revueWeek\?\.enabled && !revueWeek\.offer\.filed\)\)/);
  // 2026-10-18: the news card goes under the day's card (and its next step), in the hero slot.
  assert.match(page, /const revueNews = revueEntry\.news \? \(\s*<RvNewsCard/);
  assert.match(page, /\{revueHero \?\? journeyCard\}\s*<DaySessionNext [\s\S]*?\} \/>\s*\{revueNews\}/);
  // Round 3: the hero is the Revue's (else the journey card), with the day's one
  // next-step button under it; on a news day the programme stays, Le Papier first.
  assert.match(page, /const homeHero = [\s\S]*?\{revueHero \?\? journeyCard\}[\s\S]*?: \(revueHero \?\? journeyCard\);/);
  assert.match(page, /hero=\{homeHero\}/);
  assert.match(page, /planHidden=\{\(Boolean\(revueHero\) && !daySession\) \|\|/);
  // WP-119 phase 3: the hero opens the day until it is done (the hero hides the plan row), then /revue.
  assert.match(page, /if \(revueHeroOpensDay\(revueDayDone, Boolean\(onOpenDay\)\) && onOpenDay\) onOpenDay\(\);\s*else void router\.push\(revueOpenHref\(offer\)\);/);
  assert.match(page, /router\.push\(revueDossierHref\(dossierId\)\)/);
  assert.match(page, /onAsk=\{\(text\) => revueClient\(\)\.match\(text\)\}/);
  assert.match(page, /Precedence with a Courrier letter/, 'the precedence rule is written down where it is applied');
});
