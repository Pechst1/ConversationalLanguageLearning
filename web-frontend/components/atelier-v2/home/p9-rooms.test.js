// node --test components/atelier-v2/home/p9-rooms.test.js
//
// P9 stage 1 (walk of 17 Nov) — fewer rooms, and the Journal on Home:
//
//   1. a waiting retell gets one chip on Home, second after the letter, and none
//      once it is written or skipped;
//   2. «Check your level» speaks Home's chrome language (the server half — not
//      before the eighth completed day — is `tests/test_wp126_starting_points.py`);
//   3. the walkthrough is two cards: «Les quatre formes» and «Où tu en es» went;
//   4. the try-first coffee order accepts «Un café, merci»;
//   5. «Revoir» on a finished day opens the episode in the archive reader, with
//      the way back to Home, and keeps the end card while the day is not filed;
//   6. before an unplayed scene, «Arrêter ici» never ends the day: on a rule it
//      reads «Passer à la scène», on the «Avant la scène» drill it is not drawn.

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
  if (request === 'next/link') {
    return originalResolve.call(this, path.join(WEB_ROOT, 'components/feuilleton/reader/__fixtures__/next-link-stub.js'), ...rest);
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

const realConsoleError = console.error;
console.error = (...args) => {
  const first = String(args[0] || '');
  if (first.includes('non-boolean attribute') || first.includes('useLayoutEffect')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
global.React = React;

const { HomeScreen } = require('./HomeScreen.tsx');
const { JourneyTodayCard } = require('../journey/JourneyTodayCard.tsx');
const { JourneySession } = require('../journey/JourneySession.tsx');
const { journeyCopy } = require('../journey/journey-copy.ts');
const state = require('../journey/journey-state.ts');
const { dayMarkState } = require('../journey/day-mark.ts');
const { atelierCopy } = require('@/lib/atelier-v2-copy.ts');
const { AtelierV2Root } = require('@/components/atelier-v2/ui/index.ts');

const h = React.createElement;
const read = (relative) => fs.readFileSync(path.join(WEB_ROOT, relative), 'utf8');
const decode = (html) =>
  html
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/[  ]/g, ' ');
const visibleText = (html) =>
  decode(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<span class="av2-sr">[\s\S]*?<\/span>/g, ' ').replace(/<[^>]+>/g, ' '))
    .replace(/\s+/g, ' ')
    .trim();
const words = (text) => text.split(' ').filter((token) => /[\p{L}\p{N}]/u.test(token));

// ===========================================================================
// 1. The Journal on Home
// ===========================================================================

const offered = (extra = {}) => ({
  version: 'v1',
  status: 'offered',
  entry: {
    id: 'e-1',
    status: 'offered',
    scene_date: '2026-11-16',
    offered_on: '2026-11-17',
    followup_due_on: '2026-11-19',
    cue: { character_name: 'Lila', location_name: 'Le Mistral', days_ago: 1 },
    prompt_fr: 'De mémoire…',
    entry_text: null,
    ...extra,
  },
  followup: null,
  recall_offset_days: 1,
  followup_offset_days: 3,
  min_entry_words: 12,
});

test('1 · a waiting retell is one chip on Home, second after the letter, gone once written or skipped', () => {
  const journal = require('@/lib/journal-home.ts');
  const waiting = journal.journalWaiting(offered());
  assert.deepEqual(waiting, { daysAgo: 1 });
  for (const status of ['written', 'skipped', 'unavailable', 'none']) {
    assert.equal(journal.journalWaiting({ ...offered(), status }), null, status);
  }
  assert.equal(journal.journalWaiting(offered({ entry_text: 'Lila attend.' })), null, 'sent');
  assert.equal(journal.journalWaiting(null), null);

  const labels = { en: 'Retell yesterday', de: 'Gestern erzählen', fr: 'Raconter hier' };
  for (const [language, label] of Object.entries(labels)) {
    const chip = journal.journalHomeChip(waiting, language);
    assert.equal(chip.label, label, language);
    assert.equal(chip.href, '/notebook?mode=journal');
    assert.equal(chip.meta, '≈ 2 min');
    assert.ok(chip.ariaLabel.length > chip.label.length, `${language}: the accessible name says what it is`);
  }
  // A scene from further back is never «hier».
  assert.equal(journal.journalHomeChip({ daysAgo: 3 }, 'fr').label, 'Raconter la scène');
  assert.equal(journal.journalHomeChip(null, 'fr'), null);

  // Second after the letter, ahead of the Revue and the Radio that also follow it.
  const letter = { id: 'courrier' };
  const chip = journal.journalHomeChip(waiting, 'fr');
  assert.deepEqual(
    journal.withJournalChip([letter, { id: 'revue' }, { id: 'radio' }], chip).map((c) => c.id),
    ['courrier', 'journal', 'revue', 'radio'],
  );
  assert.deepEqual(journal.withJournalChip([{ id: 'lexique' }], chip).map((c) => c.id), ['journal', 'lexique']);
  assert.deepEqual(journal.withJournalChip([], chip, true), [], 'the Papier day keeps La Une whole');

  // Home wires it last, from the journal's own «today» read, and only with the day.
  const page = read('pages/atelier.tsx');
  assert.match(page, /const journalWaiting = useJournalWaiting\(Boolean\(homeDay\)\);/);
  assert.match(page, /withJournalChip<HomeChip>\(\s*withCorrecteurChip<HomeChip>/);
  assert.match(page, /homeDay \? journalHomeChip\(journalWaiting, chromeLanguage\) : null/);

  // Drawn on Home beside the letter, inside the 25-word budget, in every language.
  const fixture = JSON.parse(
    fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/first_day.json'), 'utf8'),
  ).response;
  for (const language of ['en', 'de', 'fr']) {
    const envelope = { ...fixture, control_language: language };
    const html = renderToStaticMarkup(
      h(HomeScreen, {
        dateLabel: 'mardi 18 novembre',
        editionLabel: 'Édition Nº 4 · A1.1',
        streak: 4,
        level: { band: 'A1.1', percent: 60 },
        language,
        day: dayMarkState(null, language),
        hero: h(JourneyTodayCard, {
          controller: {
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
          },
          onOpen: () => {},
        }),
        chips: journal.withJournalChip(
          [{ id: 'courrier', label: atelierCopy(language).home_letter, ariaLabel: atelierCopy(language).home_letter_aria, href: '/missions', shape: 'story' }],
          journal.journalHomeChip(waiting, language),
        ),
      }),
    );
    assert.match(html, /data-chip="journal"/, language);
    assert.match(html, /href="\/notebook\?mode=journal"/, language);
    assert.ok(visibleText(html).includes(labels[language]), language);
    const count = words(visibleText(html)).length;
    assert.ok(count <= 25, `${language}: ${count} words — ${visibleText(html)}`);
  }
});

// ===========================================================================
// 2. «Check your level» in Home's chrome language
// ===========================================================================

test('2 · the placement chip uses the level-aware chrome language, not the level-blind one', () => {
  const chip = read('components/onboarding/PlacementOfferChip.tsx');
  assert.match(chip, /placementCopy\(useChromeLanguage\(\)\)/);
  assert.doesNotMatch(chip, /useLearnerLanguage/);
  // The «not before day 8» half is the server's: `PLACEMENT_OFFER_MIN_DAYS`.
  const server = fs.readFileSync(path.join(REPO_ROOT, 'app/services/placement.py'), 'utf8');
  assert.match(server, /^PLACEMENT_OFFER_MIN_DAYS = 8$/m);
});

// ===========================================================================
// 3. The walkthrough: two cards
// ===========================================================================

test('3 · the walkthrough is «Bienvenue» and «Ton premier jour», nothing between', () => {
  const { Walkthrough } = require('@/components/onboarding/Walkthrough.tsx');
  const { firstStepsCopy } = require('@/lib/first-steps.ts');
  for (const language of ['en', 'de', 'fr']) {
    const html = renderToStaticMarkup(h(Walkthrough, { language, onDone: () => {} }));
    const dots = html.match(/<ol class="walkthrough__dots"[^>]*>([\s\S]*?)<\/ol>/)[1];
    assert.equal((dots.match(/<li/g) || []).length, 2, `${language}: two cards`);
    const copy = firstStepsCopy(language).walkthrough;
    assert.equal(copy.shapes_title, undefined, language);
    assert.equal(copy.progress_title, undefined, language);
    assert.ok(copy.welcome_title && copy.day_title, language);
  }
  const fr = JSON.stringify(firstStepsCopy('fr'));
  assert.doesNotMatch(fr, /Les quatre formes|Où tu en es/);
  const source = read('components/onboarding/Walkthrough.tsx');
  assert.match(source, /const cards = 2;/);
  assert.doesNotMatch(source, /index === 2|index === 3/);
});

// ===========================================================================
// 4. «Un café, merci»
// ===========================================================================

test('4 · the try-first coffee order accepts «Un café, merci» through an alternatives list', () => {
  const taste = require('@/lib/onboarding-taste.ts');
  const order = taste.TASTE_ITEMS[1];
  assert.equal(order.kind, 'tiles');
  assert.deepEqual(order.alternatives, [['cafe', 'merci']]);
  assert.equal(taste.gradeTiles(order, ['cafe', 'svp']), 'correct');
  assert.equal(taste.gradeTiles(order, ['cafe', 'merci']), 'correct');
  assert.equal(taste.tilesSentence(order, ['cafe', 'merci']), 'Un café, merci');
  assert.equal(taste.gradeTiles(order, ['merci', 'cafe']), 'wrong');
  assert.equal(taste.gradeTiles(order, ['bonsoir', 'cafe']), 'wrong');
  assert.equal(taste.gradeTiles(order, ['cafe']), 'pending');
  // No special case in the grader: the rule is the item's data.
  assert.doesNotMatch(read('lib/onboarding-taste.ts'), /'merci'\]\) \?|=== 'merci'/);
});

// ===========================================================================
// 5. «Revoir» replays the episode
// ===========================================================================

test('5 · «Revoir» opens the finished day in the archive reader, back to Home; an unfiled day keeps the end card', () => {
  const model = require('@/components/feuilleton/archive/archive-model.ts');
  const archive = model.normalizeArchive({
    seasons: [
      {
        number: 1,
        title_fr: 'S’installer',
        finished: false,
        loaded: true,
        chapters: [
          {
            index: 1,
            title_fr: 'Le Mistral',
            closed: false,
            days: [
              {
                date: '2026-11-17',
                journey_id: 'j-17',
                scene_id: 's-17',
                title_fr: 'Lila attend sous la pluie',
                edition_no: 3,
                image_url: null,
                learner_lines: [],
                ending_fr: null,
                margin_notes: [],
                can_do_id: null,
                special: null,
              },
            ],
          },
        ],
      },
    ],
    current: { season: 1, chapter: 1 },
  });
  assert.equal(model.homeReplayHref(archive, 'j-17'), '/graphic-novel?day=2026-11-17&journey=j-17&from=home');
  assert.equal(model.homeReplayHref(archive, 'j-18'), null, 'not filed yet');
  assert.equal(model.homeReplayHref(null, 'j-17'), null);
  assert.equal(model.homeReplayHref(archive, null), null);

  // The archive's day page, opened from Home, leads back to Home.
  const surface = require('@/components/feuilleton/archive/FeuilletonArchive.tsx');
  const { archiveCopy } = require('@/components/feuilleton/archive/archive-copy.ts');
  const filed = model.findArchiveDay(archive, { journeyId: 'j-17' });
  for (const language of ['en', 'de', 'fr']) {
    const fromHome = decode(
      renderToStaticMarkup(h(AtelierV2Root, { language }, h(surface.ArchiveDayPage, { day: filed, archive, language, episode: null, fromHome: true }))),
    );
    assert.match(fromHome, /<a href="\/atelier" class="fa-back"/, language);
    assert.ok(fromHome.includes(archiveCopy(language).back_home), language);
    const fromArchive = decode(
      renderToStaticMarkup(h(AtelierV2Root, { language }, h(surface.ArchiveDayPage, { day: filed, archive, language, episode: null }))),
    );
    assert.match(fromArchive, /<a href="\/graphic-novel" class="fa-back"/, `${language}: the archive's own way back is unchanged`);
  }
  assert.match(read('pages/graphic-novel.tsx'), /fromHome=\{archiveView === 'day' && query\.from === 'home'\}/);

  // Home hands the replay to the finished card's «Revoir»; any other phase still opens the day.
  const card = read('components/atelier-v2/journey/JourneyTodayCard.tsx');
  assert.match(card, /onOpen=\{phase\.kind === 'finished' && onReview \? onReview : onOpen\}/);
  const page = read('pages/atelier.tsx');
  assert.match(page, /onReview=\{\(\) => \{[\s\S]{0,200}getStoryArchive\(\)\.then\(\(archive\) => \{\s*const href = homeReplayHref\(archive, journeyId\);\s*if \(href\) void router\.push\(href\);\s*else setView\('journey'\);/);
});

// ===========================================================================
// 6. «Arrêter ici» before the scene
// ===========================================================================

const EN = journeyCopy('en');
const step = (id, ordinal, kind, status, prompt = {}) => ({
  id,
  ordinal,
  kind,
  status,
  estimated_seconds: 40,
  assistance_used: [],
  prompt,
});
const RULE_PROMPT = {
  concept_id: 12,
  title_native: 'The pluperfect',
  title_fr: 'Le plus-que-parfait',
  rule_card: {
    example: { fr: '[J’avais vu] Lila.' },
    rule: { en: 'The past of the past.', de: 'Die Vergangenheit der Vergangenheit.' },
    pattern: { kind: 'rows', rows: [{ shape: 'none', label: '', fr: 'J’avais vu.' }] },
    contrast: { wrong: 'J’ai eu vu.', right: 'J’avais vu.' },
  },
};
const RECALL_PROMPT = {
  task_type: 'word_bank',
  instruction_native: 'Build the sentence.',
  prompt_fr: null,
  options: [
    { id: 'a', text_fr: 'Je' },
    { id: 'b', text_fr: 'le' },
    { id: 'c', text_fr: 'lui' },
    { id: 'd', text_fr: 'donne' },
  ],
  target: { kind: 'grammar', id: 'g-1', label_fr: 'Deux pronoms', label_native: 'Two pronouns' },
  optional: false,
  help_available: [],
};

function dayThree(currentId, sceneStatus = 'pending') {
  // Day 3 of the B1 check: Règle (1), Avant la scène (2), the scene (3), the reply (4).
  return {
    id: 'journey-3',
    status: 'active',
    revision: 2,
    current_step_id: currentId,
    scenario: {
      scenario_key: 's',
      content_version: '1',
      title_fr: 'Lila attend sous la pluie',
      objective_key: 'o',
      objective_native: 'Answer Lila.',
      level_band: 'B1',
      character_id: 'lila_bonnet',
      character_name: 'Lila',
      location_id: 'le_mistral',
      location_name: 'Le Mistral',
      image_url: null,
      serial_thread_id: null,
      serial_episode_id: null,
      estimated_seconds: 300,
    },
    steps: [
      step('rule', 1, 'rule', currentId === 'rule' ? 'active' : 'completed', RULE_PROMPT),
      step('recall', 2, 'recall', currentId === 'recall' ? 'active' : currentId === 'rule' ? 'pending' : 'completed', RECALL_PROMPT),
      step('scene', 3, 'scene', sceneStatus, {}),
      step('reply', 4, 'respond', 'pending', {}),
    ],
    day_shape: 'standard',
  };
}

function sessionHtml(journey) {
  const current = journey.steps.find((entry) => entry.id === journey.current_step_id);
  return decode(
    renderToStaticMarkup(
      h(JourneySession, {
        controller: {
          phase: { kind: 'session', journey, step: current },
          feedback: { kind: 'idle' },
          envelope: null,
          journey,
          step: current,
          respondPrompt: null,
          controlLanguage: 'en',
          legacyResume: null,
          progress: { done: 0, total: journey.steps.length },
          busy: false,
          help: null,
          voice: { kind: 'idle' },
          recovery: null,
          actions: new Proxy({}, { get: () => () => Promise.resolve() }),
        },
      }),
    ),
  );
}

test('6 · before an unplayed scene the control skips to the scene (rule) or is not there (drill); never «Stop here»', () => {
  const onRule = dayThree('rule');
  const onDrill = dayThree('recall');
  assert.equal(state.sessionStopControl(onRule, onRule.steps[0]), 'skip');
  assert.equal(state.sessionStopControl(onDrill, onDrill.steps[1]), 'none');
  const forge = { ...onRule, steps: [step('forge', 1, 'forge', 'active'), ...onRule.steps.slice(2)], current_step_id: 'forge' };
  assert.equal(state.sessionStopControl(forge, forge.steps[0]), 'skip');
  // From the scene on, ending the day early stays as it was.
  const onScene = dayThree('scene', 'active');
  assert.equal(state.sessionStopControl(onScene, onScene.steps[2]), 'end');
  const ruleAfterScene = { ...onScene, steps: [step('scene', 1, 'scene', 'completed'), step('rule', 2, 'rule', 'active', RULE_PROMPT)], current_step_id: 'rule' };
  assert.equal(state.sessionStopControl(ruleAfterScene, ruleAfterScene.steps[1]), 'end');
  assert.equal(state.sessionStopControl(null, null), 'end');

  assert.deepEqual(
    ['en', 'de', 'fr'].map((language) => journeyCopy(language).skip_to_scene),
    ['Skip to the scene', 'Weiter zur Szene', 'Passer à la scène'],
  );

  // A B1 day: the session's chrome is French.
  const FR = journeyCopy('fr');
  const rule = sessionHtml(onRule);
  assert.ok(rule.includes(FR.skip_to_scene), 'the rule step offers the scene');
  assert.ok(!rule.includes(FR.finish_early) && !rule.includes(EN.finish_early), 'and never ends the day');
  const drill = sessionHtml(onDrill);
  assert.ok(!drill.includes(FR.finish_early) && !drill.includes(FR.skip_to_scene), 'the pre-scene drill has neither');
  // After the scene, the same drill keeps «Arrêter ici», as before.
  const afterScene = {
    ...onDrill,
    steps: [step('scene', 1, 'scene', 'completed'), step('recall', 2, 'recall', 'active', RECALL_PROMPT)],
    current_step_id: 'recall',
  };
  const later = sessionHtml(afterScene);
  assert.ok(later.includes(FR.finish_early) && !later.includes(FR.skip_to_scene), 'from the scene on, the day can still end early');

  // The press acknowledges the pre-scene steps; it never calls finish.
  const session = read('components/atelier-v2/journey/JourneySession.tsx');
  assert.match(session, /stopControl === 'skip' \? actions\.skipToScene\(\) : actions\.finish\('early'\)/);
  const hook = read('components/atelier-v2/journey/useDailyJourney.ts');
  const skip = hook.slice(hook.indexOf('const skipToScene = useCallback'), hook.indexOf('}, [advance]);', hook.indexOf('const skipToScene')));
  assert.match(skip, /sessionStopControl\(target, currentStepOf\(target\)\) !== 'skip'/);
  assert.match(skip, /await advance\(\)/);
  assert.doesNotMatch(skip, /finish/);
});
