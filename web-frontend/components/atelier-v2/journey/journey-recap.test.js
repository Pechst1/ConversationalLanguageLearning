// node --test components/atelier-v2/journey/journey-recap.test.js
//
// WP-79 — the end of the day feels like a reward.
//
//   1. a finished day renders ONE recap with the streak, the words, a face in
//      the right mood, the keepsake vignette, «La suite demain», «Continuer»
//      and a quiet «Plus de pratique» — and neither deleted line;
//   2. every number is the server's: an unmeasured day shows steps, not
//      minutes; no streak at 0; no words at 0; no mood line the ledger did not
//      write; no goal ring and no flame (owner, 2026-09-22);
//   3. the level move shows once with its evidence line, in the learner's
//      language; a partial day shows no keepsake and no teaser;
//   4. the day-complete haptic + sound fire on the transition into the recap;
//   5. Home: the streak carries the «done» mark, the Séance tile reads closed,
//      and a zero streak draws the gear, never a number.

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

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { JourneyRecap } = require('./JourneyRecap.tsx');
const model = require('./journey-recap-model.ts');
const { RECAP_CHROME } = require('./recap-copy.ts');
const { journeyCopy } = require('./journey-copy.ts');
const { feelForTransition } = require('./useJourneyFeel.ts');
const { HomeScreen } = require('@/components/atelier-v2/home/HomeScreen.tsx');

const FIXTURE = JSON.parse(
  fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/completed.json'), 'utf8'),
).response;

function day(recapOverrides = {}, journeyOverrides = {}) {
  const recap = {
    ...FIXTURE.recap,
    active_seconds: null,
    steps_done: 4,
    words: [
      { id: 'w1', label_fr: 'un café', label_native: 'a coffee', evidence_kind: 'produced_independent' },
      { id: 'w2', label_fr: 'la terrasse', label_native: 'the terrace', evidence_kind: 'recognized' },
    ],
    mood: { character_id: 'margaux_barman', character_name: 'Margaux', mood: 1, shift: 'warmer' },
    keepsake: {
      collectible_id: '33333333-3333-4333-8333-333333333301',
      title_fr: 'Un café au Mistral',
      location_name: 'Le Mistral',
      image_url: '/assets/serial/locations/le_mistral-counter.webp',
      local_date: '2026-09-22',
    },
    teaser: {
      text_fr: 'Je vous garde une place au Mistral. Vous venez ?',
      character_id: 'marin_leveque',
      character_name: 'Marin',
      source: 'authored',
    },
    teaser_fr: null,
    level: 'A1.1',
    level_up: null,
    ...recapOverrides,
  };
  const journey = {
    ...FIXTURE,
    recap,
    streak: { days: 4, today_done: true, freeze_available: false, freeze_used_on: null },
    ...journeyOverrides,
  };
  return { journey, recap };
}

function render({ journey, recap }, props = {}) {
  return renderToStaticMarkup(
    React.createElement(JourneyRecap, {
      journey,
      recap,
      language: 'en',
      onExit: () => {},
      morePractice: { label: '', onSelect: () => {} },
      ...props,
    }),
  );
}

const decode = (html) =>
  html
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
const textOf = (html) => decode(html.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();

const FR = journeyCopy('en');

test('a finished day is one screen: streak, words, face, keepsake, teaser, actions', () => {
  const html = render(day());
  const text = textOf(html);
  assert.equal((html.match(/class="journey-recap /g) || []).length, 1, 'exactly one recap');
  assert.match(text, /Série Jour 4/);
  assert.match(text, /Mots \+2/);
  assert.match(text, /un café/);
  assert.match(text, /la terrasse/);
  // The face, in the mood the ledger left, and the line that says so.
  assert.match(html, /portrait-happy\.webp/);
  assert.match(html, /margaux_barman/);
  assert.match(text, /Margaux vous sourit ↑/);
  // The keepsake vignette, stamped with the mark.
  assert.match(html, /data-keepsake="33333333-3333-4333-8333-333333333301"/);
  assert.match(html, /le_mistral-counter\.webp/);
  assert.match(text, /Un café au Mistral/);
  assert.match(text, /Le Mistral · 22 sept\./);
  assert.match(html, /aria-label="Journée bouclée"/);
  // «La suite demain».
  assert.match(text, /La suite demain « Je vous garde une place au Mistral\. Vous venez \? » — Marin/);
  // Actions: «Continuer» primary, «Plus de pratique» quiet.
  assert.match(html, /av2-btn--primary/);
  assert.match(text, /Continuer/);
  assert.match(html, /av2-btn--quiet/);
  assert.match(text, /Plus de pratique/);
});

test('the deleted lines stay deleted and no number is invented', () => {
  const html = render(day());
  const text = textOf(html);
  assert.doesNotMatch(text, /pas encore mesur|not measured|nicht gemessen/i);
  assert.doesNotMatch(text, /does not reopen|ne rouvre pas|nicht neu ge/i);
  // Unmeasured minutes read as the steps the learner did.
  assert.match(text, /Scène 4 étapes/);
  assert.doesNotMatch(text, /\b\d+\s?min\b/);
  // No goal ring, no flame (owner 2026-09-22), no mascot.
  assert.doesNotMatch(html, /ring|flame|🔥|confetti/i);

  const measured = textOf(render(day({ active_seconds: 268 })));
  assert.match(measured, /Scène 4 min/);

  // Zero streak and zero words: the facts are absent, not «0».
  const bare = textOf(render(day({ words: [] }, { streak: { days: 0, today_done: false, freeze_available: false, freeze_used_on: null } })));
  assert.doesNotMatch(bare, /Série|Jour 0|Mots/);
});

test('a mood line only when the ledger moved today; the face still reacts', () => {
  const steady = render(day({ mood: { character_id: 'margaux_barman', character_name: 'Margaux', mood: 0, shift: null } }));
  assert.doesNotMatch(textOf(steady), /vous sourit|vous en veut/);
  assert.match(steady, /portrait-neutral\.webp/);

  const colder = render(day({ mood: { character_id: 'margaux_barman', character_name: 'Margaux', mood: -1, shift: 'colder' } }));
  assert.match(textOf(colder), /Margaux vous en veut un peu ↓/);
  assert.match(colder, /portrait-cross\.webp/);

  // No ledger at all: the face reacts to the day's outcome, with no claim.
  const noLedger = render(day({ mood: null }));
  assert.match(noLedger, /portrait-happy\.webp/);
  assert.doesNotMatch(textOf(noLedger), /vous sourit/);
});

test('a «jour de relâche» is said in the learner language', () => {
  const html = render(day({}, { streak: { days: 8, today_done: true, freeze_available: false, freeze_used_on: '2026-09-20' } }));
  assert.match(textOf(html), /A day off kept your streak\./);
});

test('the level move: once, honest, with its evidence', () => {
  const up = day({ level: 'A1.2', level_up: { from_level: 'A1.1', to_level: 'A1.2', mastered_vocabulary: 312, mastered_grammar: 21 } });
  const text = textOf(render(up));
  assert.match(text, /Niveau A1\.1 → A1\.2/);
  assert.match(text, /312 words and 21 rules mastered\./);
  const fr = textOf(render(up, { language: 'fr' }));
  assert.match(fr, /312 mots et 21 règles maîtrisés\./);
  assert.doesNotMatch(textOf(render(day())), /Niveau/);
});

test('a partial day: no keepsake, no teaser', () => {
  const { journey, recap } = day({ completion_kind: 'early' }, { status: 'ended_early' });
  const html = render({ journey, recap });
  assert.match(html, /data-state="partial"/);
  assert.doesNotMatch(html, /data-keepsake/);
  assert.doesNotMatch(textOf(html), /La suite demain/);
});

test('a recap written before WP-79 still shows its words and steps', () => {
  const legacy = { ...FIXTURE.recap, active_seconds: null };
  const view = model.rewardView(FIXTURE, legacy, 'en');
  assert.deepEqual(view.words.map((w) => w.label_fr), ['un café'], 'vocabulary only, from practiced_targets');
  assert.equal(view.facts.find((f) => f.id === 'scene').value, '4 étapes');
  assert.equal(view.keepsake, null);
  assert.equal(view.teaser, null);
});

test('«Plus de pratique» opens the server href for what today practised', () => {
  const opened = [];
  const withHref = day({
    practiced_targets: [
      { ...FIXTURE.recap.practiced_targets[1], practice_href: '/atelier?mode=practice&concept=7' },
    ],
  });
  const view = model.rewardView(withHref.journey, withHref.recap, 'en');
  assert.equal(view.practiceHref, '/atelier?mode=practice&concept=7');
  const element = JourneyRecap({
    ...withHref,
    language: 'en',
    onPractice: (href) => opened.push(href),
  });
  const find = (node) => {
    if (!node || typeof node !== 'object') return null;
    if (node.props?.tone === 'quiet') return node;
    for (const child of [].concat(node.props?.children || [])) {
      const hit = find(child);
      if (hit) return hit;
    }
    return null;
  };
  find(element).props.onClick();
  assert.deepEqual(opened, ['/atelier?mode=practice&concept=7']);
});

test('the recap chrome stays under 15 words', () => {
  const chrome = [
    FR.finished_title,
    RECAP_CHROME.streak_label,
    RECAP_CHROME.words_label,
    RECAP_CHROME.scene_label,
    RECAP_CHROME.teaser_label,
    FR.continue,
    'Plus de pratique',
  ].join(' ');
  assert.ok(chrome.split(/\s+/).length <= 15, chrome);
});

test('the day-complete haptic and sound fire on the way into the recap', () => {
  const idle = { kind: 'idle' };
  assert.equal(
    feelForTransition({ phase: 'session', stepId: 's', result: null }, { phase: 'finished', stepId: null, feedback: idle }),
    'complete',
  );
  // Re-opening a finished day is not a new event.
  assert.equal(
    feelForTransition({ phase: null, stepId: null, result: null }, { phase: 'finished', stepId: null, feedback: idle }),
    null,
  );
});

test('the session shell mounts the new recap and keeps the push pre-prompt', () => {
  const session = fs.readFileSync(path.join(__dirname, 'JourneySession.tsx'), 'utf8');
  const recap = session.slice(session.indexOf('export function JourneyRecapView'));
  assert.match(recap, /<JourneyRecap\b/);
  assert.match(recap, /<PushOptIn[^>]*\n?[^>]*dayFinished/);
  assert.doesNotMatch(session, /duration_not_measured|more_practice_note/);
});

// --- Home ------------------------------------------------------------------

function home(props) {
  return renderToStaticMarkup(
    React.createElement(HomeScreen, {
      dateLabel: 'mardi 22 septembre',
      editionLabel: 'Édition Nº 4 · A1',
      streak: 4,
      episode: null,
      action: null,
      tiles: [
        {
          id: 'seance',
          title: 'Séance',
          meta: '1 règle · exercices',
          mark: 'story',
          bars: [null, null, null],
          href: '/atelier?mode=practice',
          secondary: { label: 'Plus de pratique', href: '/atelier?mode=practice' },
        },
      ],
      colophon: null,
      ...props,
    }),
  );
}

test('Home after the day: the streak carries the done mark, the Séance tile reads closed', () => {
  const before = home({});
  assert.match(textOf(before), /1 règle · exercices/);
  assert.doesNotMatch(before, /journée bouclée/);

  const after = home({ dayDone: true });
  assert.match(after, /aria-label="4 jours de suite · journée bouclée · réglages"/);
  assert.match(after, /av2-home__streak[^"]*"[^>]*data-state="done"/);
  assert.match(textOf(after), /Séance Journée bouclée/);
  assert.doesNotMatch(textOf(after), /1 règle · exercices/);
  assert.match(textOf(after), /Plus de pratique/, 'extra practice is still one tap away');
});

test('Home at a zero streak draws the gear, never a number', () => {
  const html = home({ streak: 0, dayDone: false });
  assert.doesNotMatch(html, /av2-home__streak-n/);
  assert.match(html, /aria-label="Réglages"/);
});
