// node --test components/atelier-v2/home/atelier-revue-entry.test.js
//
// WP-119 phase 1 — La Revue's entry on La Une, as `pages/atelier.tsx` wires it.
// The page has no mount harness, so the decision lives in `lib/revue-une.ts`
// (pure) and is rendered here through the real HomeScreen with the same props
// the page passes; a source check pins the page to that helper.
//
//   1. the Revue off (404 → `{ enabled: false }`), unread or failed: no chip, no card;
//   2. an ordinary day with a live dossier: the chip, after the letter;
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
  const chips = une.revueHomeChips(entry, [...(letter ? [letterChip(language)] : []), wordsChip]);
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

function assertHomeBudget(html, label) {
  const sections = (html.match(/class="av2-home__mast"|class="av2-home__section[ "]/g) || []).length;
  assert.ok(sections <= 5, `${label}: ${sections} elements`);
  const count = words(prose(html)).length;
  assert.ok(count <= 25, `${label}: ${count} words — ${visibleText(html)}`);
}

test('the Revue off, unread or failed: La Une is exactly as before — no chip, no card', () => {
  for (const week of [{ enabled: false }, null, undefined]) {
    for (const dayShape of ['standard', une.REVUE_DAY_SHAPE]) {
      assert.deepEqual(une.revueUneEntry({ week, language: 'en', dayShape, special: false }), { chip: null, hero: null });
    }
  }
  const off = laUne('en', { week: { enabled: false }, dayShape: une.REVUE_DAY_SHAPE });
  assert.doesNotMatch(off.html, /data-chip="revue"|data-revue-card|rv-une/);
  assert.match(off.html, /av2-day-plan/, 'the plan row stays');
  assert.deepEqual(off.chips.map((chip) => chip.id), ['courrier', 'lexique']);
  // And identical to a Home that never heard of the Revue.
  assert.equal(off.html, laUne('en', { week: null }).html);
});

test('a live dossier: the chip on an ordinary day, the card in hero with planHidden on the Revue day, in en/de/fr', () => {
  for (const language of ['en', 'de', 'fr']) {
    const ordinary = laUne(language, { week: live });
    assert.equal(ordinary.entry.hero, null, 'phase 1 / any other day: no hero');
    assert.equal(ordinary.entry.chip.href, '/revue');
    assert.match(ordinary.html, /data-chip="revue"/);
    assert.doesNotMatch(ordinary.html, /data-revue-card/);
    assert.match(ordinary.html, /av2-day-plan/);
    assertHomeBudget(ordinary.html, `${language} chip`);

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
  // On an ordinary day the chip resumes too.
  const chip = une.revueUneEntry({ week: { enabled: true, offer: resumeOffer }, language: 'fr', dayShape: 'standard', special: false }).chip;
  assert.match(chip.href, /^\/revue\?session=/);
});

test('a letter and a Revue the same day: §2 — the letter first, then the Revue, then words due', () => {
  for (const language of ['en', 'de', 'fr']) {
    const both = laUne(language, { week: live });
    assert.deepEqual(both.chips.map((chip) => chip.id), ['courrier', 'revue', 'lexique']);
    const shown = [...both.html.matchAll(/data-chip="([^"]+)"/g)].map((match) => match[1]);
    assert.deepEqual(shown, ['courrier', 'revue'], `${language}: HomeScreen's two — words due drop`);
    assert.equal((both.html.match(/av2-btn--primary/g) || []).length, 1, 'a chip is never a press');
    assertHomeBudget(both.html, `${language} letter + revue`);
    // Once the day is done, the one chip is the letter.
    const done = laUne(language, { week: live, dayDone: true });
    assert.deepEqual([...done.html.matchAll(/data-chip="([^"]+)"/g)].map((match) => match[1]), ['courrier']);
    // No letter: the Revue leads the row.
    assert.deepEqual(laUne(language, { week: live, letter: false }).chips.map((chip) => chip.id), ['revue', 'lexique']);
    // The Revue day: the Revue is the day's route and takes La Une whole — its
    // card spends the words a chip would need; the letter waits in the Courrier.
    for (const offer of [liveOffer, resumeOffer, filedOffer]) {
      const revueDay = laUne(language, { week: { enabled: true, offer }, dayShape: une.REVUE_DAY_SHAPE });
      assert.match(revueDay.html, /data-revue-card=/);
      assert.doesNotMatch(revueDay.html, /data-chip=|av2-home__chips/);
    }
  }
});

test('a special edition keeps its hero; a filed Revue shows only on the Revue day', () => {
  const special = laUne('fr', { week: live, dayShape: une.REVUE_DAY_SHAPE, special: true });
  assert.equal(special.entry.hero, null, 'never on a special edition');
  assert.match(special.html, /data-chip="revue"/, 'the Revue stays a chip');
  assert.match(special.html, /av2-day-plan/);

  for (const language of ['en', 'de', 'fr']) {
    const filed = laUne(language, { week: { enabled: true, offer: filedOffer }, dayShape: une.REVUE_DAY_SHAPE });
    assert.equal(filed.entry.hero.state, 'filed');
    assert.match(filed.html, /data-revue-card="filed"/);
    assert.equal((filed.html.match(/av2-btn--primary/g) || []).length, 0, 'filed: no press');
    assertHomeBudget(filed.html, `${language} filed`);
  }
  const filedOrdinary = laUne('en', { week: { enabled: true, offer: filedOffer } });
  assert.deepEqual(filedOrdinary.entry, { chip: null, hero: null }, 'filed: the chip is gone');
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
  assert.match(page, /revueHomeChips<HomeChip>\(revueEntry, dayChips\)/);
  assert.match(page, /hero=\{revueHero \?\? journeyCard\}/);
  assert.match(page, /planHidden=\{Boolean\(revueHero\) \|\|/);
  assert.match(page, /onOpen=\{\(\) => \{ void router\.push\(revueOpenHref\(offer\)\); \}\}/);
  assert.match(page, /router\.push\(revueDossierHref\(dossierId\)\)/);
  assert.match(page, /onAsk=\{\(text\) => revueClient\(\)\.match\(text\)\}/);
  assert.match(page, /Precedence with a Courrier letter/, 'the precedence rule is written down where it is applied');
});
