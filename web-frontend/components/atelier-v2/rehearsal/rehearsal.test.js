/**
 * WP-31 «Répétition» — behavioural coverage for the screen's state.
 *
 * Same harness as `journey.test.js`: a plain node script with
 * `node:assert/strict` and sucrase, so it adds no test framework and no
 * dependency.
 *
 * These are failure-mode tests. What they hold down:
 *
 *   1. a rehearsal the provider could not prepare renders as `not_prepared`,
 *      never as a scene and never as a crash;
 *   2. the debrief outranks everything else — a finished rehearsal whose real
 *      event is due is what the learner is asked about, even mid-declaration;
 *   3. the turn index the client sends is the number of graded turns, so a
 *      replayed submit is a server-side no-op rather than a second grading;
 *   4. the cap is a French sentence, never a fraction, and cap 0 is "off"
 *      rather than "you have used them all";
 *   5. the private rubric is absent while a rehearsal is live — the state
 *      module never invents one;
 *   6. the screen's copy is French, and the three debrief answers are all
 *      offered as equals.
 *
 * Run: `node components/atelier-v2/rehearsal/rehearsal.test.js`
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const {
  DEBRIEF_CHOICES,
  capSentence,
  eventDateSentence,
  nextSlotSentence,
  nextTurnIndex,
  phaseFor,
  resultSentence,
  turnsRemaining,
} = require(path.join(HERE, 'rehearsal-state.ts'));
const { rehearsalCopy } = require(path.join(HERE, 'rehearsal-copy.ts'));
const FR = rehearsalCopy('fr');

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed += 1;
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

const CAP = { limit: 2, used: 0, remaining: 2, next_slot_at: null };

function rehearsal(overrides = {}) {
  return {
    version: 'rehearsal-v1',
    id: 'r1',
    status: 'ready',
    declaration: 'call the landlord about the heating, tuesday',
    brief: {
      goal_fr: 'Demander une réparation du chauffage',
      goal_native: 'Ask for the heating to be fixed',
      counterpart: 'le propriétaire',
      register: 'vous',
      date_text: 'mardi',
      date_iso: '2026-09-15',
      facts: ['le chauffage ne marche plus depuis samedi'],
    },
    scene: {
      title_fr: 'Le chauffage',
      place_fr: 'au téléphone',
      setup_fr: 'Vous appelez le propriétaire.',
      setup_native: 'You call the landlord.',
      objective_fr: 'Expliquez le problème et demandez une date.',
      objective_native: 'Explain the problem and ask for a date.',
      opening_line_fr: 'Allô, oui ? Vous êtes bien chez monsieur Renard.',
      register: 'vous',
      level_band: 'A2',
      turns_total: 4,
      phrases: [],
      phrases_revealed: false,
      rubric_native: null,
    },
    turns: [],
    turns_used: 0,
    turns_total: 4,
    result: null,
    event_date: '2026-09-15',
    debrief: null,
    outcome: null,
    debrief_available: false,
    ...overrides,
  };
}

function envelope(overrides = {}) {
  return {
    version: 'rehearsal-v1',
    rehearsal: null,
    debrief_due: null,
    cap: { ...CAP },
    min_turns: 3,
    max_turns: 6,
    ...overrides,
  };
}

// 1. Loading and transport failure are not rehearsal states.
test('loading and load failure are their own phases', () => {
  assert.equal(phaseFor(null, { loading: true }).kind, 'loading');
  assert.equal(phaseFor(null).kind, 'loading');
  const failed = phaseFor(envelope(), { error: 'nope' });
  assert.equal(failed.kind, 'load_failed');
  assert.equal(failed.message, 'nope');
});

// 2. An unprepared rehearsal never renders as a scene.
test('not_prepared is a phase of its own and keeps the declaration', () => {
  const row = rehearsal({ status: 'not_prepared', scene: null, turns_total: 0 });
  const phase = phaseFor(envelope({ rehearsal: row }));
  assert.equal(phase.kind, 'not_prepared');
  assert.equal(phase.rehearsal.declaration, row.declaration);
  assert.equal(phase.rehearsal.scene, null);
});

// 3. The debrief outranks everything, including a fresh declaration slot.
test('a due debrief is asked before anything else', () => {
  const due = rehearsal({ status: 'rehearsed', debrief_available: true });
  const phase = phaseFor(envelope({ rehearsal: null, debrief_due: due }));
  assert.equal(phase.kind, 'debrief');
  assert.equal(phase.rehearsal.id, due.id);
});

test('a rehearsed rehearsal whose day has not come waits, and says so', () => {
  const row = rehearsal({ status: 'rehearsed', debrief_available: false });
  assert.equal(phaseFor(envelope({ rehearsal: row })).kind, 'waiting');
});

// 4. The turn index is the idempotency key.
test('the next turn index is the count of graded turns', () => {
  const row = rehearsal({
    status: 'rehearsing',
    turns: [
      { index: 0, learner_text: 'Bonjour', mode: 'text' },
      { index: 1, learner_text: 'Le chauffage est en panne', mode: 'text' },
    ],
    turns_used: 2,
  });
  assert.equal(nextTurnIndex(row), 2);
  assert.equal(turnsRemaining(row), 2);
  const phase = phaseFor(envelope({ rehearsal: row }));
  assert.equal(phase.kind, 'rehearsing');
  assert.equal(phase.turnIndex, 2);
});

test('turnsRemaining never goes negative', () => {
  const row = rehearsal({
    turns_total: 1,
    turns: [
      { index: 0, learner_text: 'a', mode: 'text' },
      { index: 1, learner_text: 'b', mode: 'text' },
    ],
  });
  assert.equal(turnsRemaining(row), 0);
});

// 5. The cap is a sentence, and 0 means off.
test('the cap speaks French and distinguishes off from spent', () => {
  assert.equal(capSentence({ limit: 0, used: 0, remaining: 0 }), 'Les répétitions sont désactivées.');
  assert.equal(
    capSentence({ limit: 2, used: 2, remaining: 0 }),
    'Vous avez utilisé vos répétitions de la semaine.',
  );
  assert.equal(capSentence({ limit: 2, used: 1, remaining: 1 }), 'Il vous reste une répétition cette semaine.');
  assert.match(capSentence({ limit: 3, used: 1, remaining: 2 }), /2 répétitions/);
});

test('cap 0 is the disabled phase, not the capped one', () => {
  const off = phaseFor(envelope({ cap: { limit: 0, used: 0, remaining: 0, next_slot_at: null } }));
  assert.equal(off.kind, 'disabled');
  const spent = phaseFor(
    envelope({ cap: { limit: 2, used: 2, remaining: 0, next_slot_at: '2026-09-20T08:00:00+00:00' } }),
  );
  assert.equal(spent.kind, 'capped');
  assert.equal(spent.nextSlotAt, '2026-09-20T08:00:00+00:00');
});

test('an unparsable date says nothing rather than something wrong', () => {
  assert.equal(nextSlotSentence(null), null);
  assert.equal(nextSlotSentence('not-a-date'), null);
  assert.equal(eventDateSentence(rehearsal({ event_date: null })), null);
  assert.match(eventDateSentence(rehearsal()), /^C’est /);
});

// 6. The private rubric is not available while the rehearsal is live.
test('a live rehearsal carries no rubric for the screen to leak', () => {
  const phase = phaseFor(envelope({ rehearsal: rehearsal() }));
  assert.equal(phase.kind, 'rehearsing');
  assert.equal(phase.rehearsal.scene.rubric_native, null);
  assert.deepEqual(phase.rehearsal.scene.phrases, []);
  assert.equal(phase.rehearsal.scene.phrases_revealed, false);
});

// 7. The rehearsal result is modest and never a grade.
test('the result line reports coverage, never a score', () => {
  const met = rehearsal({
    status: 'rehearsed',
    result: { outcome: 'met', points_total: 3, points_covered: 3 },
  });
  assert.match(resultSentence(met), /tout ce qu’il fallait/);
  const partial = rehearsal({
    status: 'rehearsed',
    result: { outcome: 'partially_met', points_total: 3, points_covered: 1 },
  });
  assert.equal(resultSentence(partial), 'Vous avez couvert 1 point sur 3.');
  const none = rehearsal({
    status: 'rehearsed',
    result: { outcome: 'not_yet', points_total: 3, points_covered: 0 },
  });
  assert.match(resultSentence(none), /reste à faire/);
  assert.doesNotMatch(resultSentence(met), /%/);
});

// 8. The three debrief answers are equals, in French, and "not yet" is not a failure.
test('the debrief offers three equal answers in French', () => {
  assert.equal(DEBRIEF_CHOICES.length, 3);
  assert.deepEqual(
    DEBRIEF_CHOICES.map((choice) => choice.id),
    ['done', 'partly', 'not_yet'],
  );
  for (const choice of DEBRIEF_CHOICES) {
    assert.ok(choice.label.length > 0, 'every answer has a label');
    assert.ok(choice.hint.length > 0, 'every answer explains itself');
    assert.doesNotMatch(choice.label, /[A-Z]{4,}/, 'no shouting labels');
  }
  assert.match(DEBRIEF_CHOICES[2].hint, /pas un échec/);
});

// 9. The screen is French, on the av2 system, with no English chrome.
test('the screen and the page carry no English chrome', () => {
  const screen = fs.readFileSync(path.join(HERE, 'RehearsalScreen.tsx'), 'utf8');
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/repetition.tsx'), 'utf8');
  for (const source of [screen, page]) {
    for (const english of ['>Continue<', '>Submit<', '>Next<', '>Cancel<', '>Retry<']) {
      assert.ok(!source.includes(english), `no English chrome: ${english}`);
    }
  }
  // WP-82: the words live in `rehearsal-copy.ts`; the French table keeps them.
  assert.equal(FR.not_prepared_title, 'Répétition non préparée', 'the honest failure state is named');
  assert.ok(screen.includes('{copy.not_prepared_title}'));
  assert.ok(FR.reveal_phrases.includes('c’est noté comme une aide'), 'asking for help is declared before it is used');
  assert.ok(screen.includes('{copy.reveal_phrases}'));
  for (const phrase of ['Répétition non préparée', 'Revenir à l’Atelier', 'Préparer la répétition', 'Cette action n’a pas abouti']) {
    assert.ok(!screen.includes(phrase) && !page.includes(phrase), `inline chrome: ${phrase}`);
  }
  assert.ok(screen.includes('useChromeLanguage()') && page.includes('useChromeLanguage()'), 'one language rule');
  assert.ok(page.includes('AtelierV2Root'), 'the page is on the av2 system');
  // Dark capability comes from the tokens; a hard-coded hex would opt out of it.
  const hexes = page.match(/#[0-9a-fA-F]{3,8}\b/g) || [];
  assert.deepEqual(hexes, [], 'no hard-coded colours: the theme owns them');
});

// 10. One primary action per state.
test('every state offers exactly one primary action', () => {
  const screen = fs.readFileSync(path.join(HERE, 'RehearsalScreen.tsx'), 'utf8');
  const primaries = screen.match(/tone="primary"/g) || [];
  const returns = screen.match(/return \(\n/g) || [];
  assert.ok(primaries.length > 0, 'there are primary actions');
  assert.ok(
    primaries.length <= returns.length,
    'no branch stacks two primary actions on one screen',
  );
});

// 11. WP-45 — the screen foot, on `Repetition.dc.html` + canvas note
//     «note-pied». At 390x844 the four-tab bar is fixed, so an action that is
//     not *after* the body in the DOM ends up under it.
test('every state carries its actions in a foot below the body', () => {
  const screen = fs.readFileSync(path.join(HERE, 'RehearsalScreen.tsx'), 'utf8');
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/repetition.tsx'), 'utf8');

  const body = screen.indexOf('className="av2-screen__body rp-body"');
  const foot = screen.indexOf('<ScreenFoot className="rp-foot">');
  assert.ok(body > -1 && foot > -1, 'the scaffold is the av2 screen body + foot');
  assert.ok(body < foot, 'the foot comes after the body in the DOM');

  // Every state hands its actions to the frame; the old in-flow spacer is gone.
  assert.ok(!screen.includes('rp-spacer'), 'no spacer stands in for a foot');
  // Nine states, nine frames. A state that returned a bare fragment would be a
  // state whose action is back in the body, under the tab bar.
  assert.equal((screen.match(/<\/Frame>/g) || []).length, 9, 'every state is framed');
  assert.ok(
    !/return \(\n\s*<>\n/.test(screen.slice(screen.indexOf('export function RehearsalScreen'))),
    'no state returns a bare fragment',
  );

  // Walked in the pane at 390x844: the clearance comes from the page frame this
  // route is mounted in, which already ends 96px above the viewport floor. The
  // screen must not reserve the bar a second time — that pushed the foot back
  // under it — and the foot gives back its own inset, which the bar owns.
  assert.ok(page.includes('@media (max-width: 760px)'), 'the phone breakpoint is handled');
  assert.ok(
    !page.includes('padding-bottom: var(--phone-bottom-nav-space'),
    'the screen must not reserve the tab bar height a second time',
  );
  assert.ok(page.includes('--av2-safe-bottom: 0px;'), 'the foot does not add a second inset');
  // Sized by its parent, never by the viewport: 100dvh is taller than the space
  // left under the masthead, which is what pushed the foot below the fold.
  assert.ok(page.includes('min-height: 100%;'), 'the screen is sized by its parent');
  assert.ok(!page.includes('min-height: 100dvh'), 'no viewport-height screen');
});

// 12. WP-45 — «Ce qui vous attend» is the artboard's taller field, and it is
//     the shared av2 control rather than a second field in the system.
test('the declaration field is the av2 field, drawn 120px tall', () => {
  const screen = fs.readFileSync(path.join(HERE, 'RehearsalScreen.tsx'), 'utf8');
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/repetition.tsx'), 'utf8');
  assert.ok(screen.includes('label: copy.declare_label,'), 'the field is labelled');
  assert.equal(FR.declare_label, 'Ce qui vous attend');
  assert.ok(screen.includes('className="rp-declare"'), 'the field carries the page hook');
  assert.match(
    page,
    /\.av2 \.rp-declare \.av2-field__control \{\s*min-height: 120px;/,
    'the design height is 120px on the shared control',
  );
});

console.log(`rehearsal-state: ${passed} tests passed`);
