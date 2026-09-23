// node --test components/atelier-v2/journey/day-mark.test.js
//
// WP-D1 — the mark is the day's plan; WP-D3 — progress tokens with faces.
//
//   1. `dayMarkState` for each of the five day shapes and an `ended_early`
//      day: done | active | todo | absent per group, and an accessible label;
//   2. the mark fills done shapes in their colour and draws the rest as
//      ghosts in `--av2-line` — never an outline, never a stroke;
//   3. Home: the mark at 44px carries the day, and the four-shape label row
//      replaces the tile grid; with the journey off Home is unchanged;
//   4. StepProgress: one shape per step, eyes on the active one, a grin or a
//      frown on a verdict, «Étape 3 sur 8», and Reduce Motion skips the face.

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

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { dayMarkState, STEP_SHAPE } = require('./day-mark.ts');
const ui = require('@/components/atelier-v2/ui/index.ts');
const { HomeScreen } = require('@/components/atelier-v2/home/HomeScreen.tsx');

const h = React.createElement;
const render = (element) => renderToStaticMarkup(element);
const css = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');

/** A journey with just what the mark reads: kinds, statuses, the cursor. */
function journeyOf(dayShape, kinds, { upTo = 0, status = 'active' } = {}) {
  const steps = kinds.map((kind, index) => ({
    id: `s${index}`,
    kind,
    status: index < upTo ? 'completed' : index === upTo && status === 'active' ? 'active' : 'pending',
  }));
  return {
    id: 'j',
    status,
    day_shape: dayShape,
    current_step_id: status === 'active' && upTo < steps.length ? `s${upTo}` : null,
    steps,
  };
}

// --- 1. dayMarkState --------------------------------------------------------

test('no journey yet: four parts ahead, nothing absent', () => {
  const state = dayMarkState(null);
  assert.deepEqual(state.groups, { scene: 'todo', recall: 'todo', respond: 'todo', resolution: 'todo' });
  assert.equal(state.done, 0);
  assert.equal(state.total, 4);
  assert.equal(
    state.label,
    'Aujourd’hui : 0 sur 4 — scène à venir, mots à venir, réponse à venir, fin à venir',
  );
});

test('standard day, in the reply: scene and words done, reply active', () => {
  const state = dayMarkState(
    journeyOf('standard', ['scene', 'recall', 'recall', 'respond', 'resolution'], { upTo: 3 }),
  );
  assert.deepEqual(state.groups, { scene: 'done', recall: 'done', respond: 'active', resolution: 'todo' });
  assert.equal(state.label, 'Aujourd’hui : 2 sur 4 — scène vue, mots revus, réponse en cours, fin à venir');
});

test('standard day: a recall group is active until every recall is resolved', () => {
  const state = dayMarkState(
    journeyOf('standard', ['scene', 'recall', 'recall', 'respond', 'resolution'], { upTo: 2 }),
  );
  assert.equal(state.groups.recall, 'active');
  assert.equal(state.done, 1);
});

test('letter day, completed: all four done, «journée bouclée»', () => {
  const state = dayMarkState(
    journeyOf('letter', ['scene', 'recall', 'respond', 'resolution'], { upTo: 4, status: 'completed' }),
  );
  assert.deepEqual(state.groups, { scene: 'done', recall: 'done', respond: 'done', resolution: 'done' });
  assert.equal(state.done, 4);
  assert.match(state.label, /^Aujourd’hui : 4 sur 4 — .*journée bouclée$/);
});

test('listening day, at the first dictation: the scene is done, words active', () => {
  const state = dayMarkState(journeyOf('listening', ['scene', 'recall', 'respond', 'resolution'], { upTo: 1 }));
  assert.deepEqual(state.groups, { scene: 'done', recall: 'active', respond: 'todo', resolution: 'todo' });
});

test('reprise day, at the ending: the close is active, not done', () => {
  const state = dayMarkState(
    journeyOf('reprise', ['scene', 'recall', 'recall', 'respond', 'resolution'], { upTo: 4 }),
  );
  assert.deepEqual(state.groups, { scene: 'done', recall: 'done', respond: 'done', resolution: 'active' });
  assert.equal(state.done, 3);
  assert.equal(state.total, 4);
});

test('short day: no recall steps, so recall is absent and the day counts three', () => {
  const state = dayMarkState(journeyOf('short', ['scene', 'respond', 'resolution'], { upTo: 1 }));
  assert.deepEqual(state.groups, { scene: 'done', recall: 'absent', respond: 'active', resolution: 'todo' });
  assert.equal(state.total, 3);
  assert.equal(state.label, 'Aujourd’hui : 1 sur 3 — scène vue, réponse en cours, fin à venir');
});

test('ended early: the skipped rest stays a ghost and never reads «Bouclé»', () => {
  const fixture = JSON.parse(
    fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/ended_early.json'), 'utf8'),
  ).response;
  assert.equal(fixture.status, 'ended_early');
  const state = dayMarkState(fixture);
  assert.deepEqual(state.groups, { scene: 'done', recall: 'done', respond: 'todo', resolution: 'todo' });
  assert.equal(state.done, 2);
  assert.doesNotMatch(state.label, /bouclée/);
});

test('a skipped step inside a running day still resolves its group', () => {
  const journey = journeyOf('standard', ['scene', 'recall', 'respond', 'resolution'], { upTo: 2 });
  journey.steps[1].status = 'skipped';
  assert.equal(dayMarkState(journey).groups.recall, 'done');
});

test('the step → shape mapping is the logo’s', () => {
  assert.deepEqual(STEP_SHAPE, { scene: 'story', recall: 'reward', respond: 'action', resolution: 'done' });
});

// --- 2. The mark ------------------------------------------------------------

test('the mark: done parts in colour, the rest ghosts in --av2-line, no stroke', () => {
  const state = dayMarkState(journeyOf('standard', ['scene', 'recall', 'respond', 'resolution'], { upTo: 2 }));
  const html = render(h(ui.AtelierMark, { size: 44, progress: state.groups, title: state.label }));
  assert.match(html, /width="44"/);
  assert.match(html, /role="img"/);
  assert.match(html, /aria-label="Aujourd’hui : 2 sur 4 — /);
  assert.match(html, /<circle[^>]*fill="var\(--av2-blue\)"[^>]*data-part="scene"/);
  assert.match(html, /<rect[^>]*fill="var\(--av2-yellow\)"[^>]*data-part="recall"/);
  assert.match(html, /<path[^>]*fill="var\(--av2-line\)"[^>]*data-part="respond"/);
  assert.match(html, /<rect[^>]*fill="var\(--av2-line\)"[^>]*data-part="resolution"/);
  assert.doesNotMatch(html, /stroke/, 'a shape is never outlined');
  // Nothing pops on first paint.
  assert.doesNotMatch(html, /av2-mark__pop/);

  // Without progress it is the plain logo, exactly as before.
  const plain = render(h(ui.AtelierMark, {}));
  assert.doesNotMatch(plain, /data-part|--av2-line/);
  assert.match(plain, /aria-hidden="true"/);
});

// --- 3. Home ----------------------------------------------------------------

function home(props) {
  return render(
    h(HomeScreen, {
      dateLabel: 'mardi 22 septembre',
      editionLabel: 'Édition Nº 4 · A1',
      streak: 0,
      episode: null,
      action: null,
      tiles: [
        { id: 'seance', title: 'Séance', meta: '1 règle · exercices', mark: 'story', bars: [null, null, null], href: '/x' },
      ],
      colophon: null,
      ...props,
    }),
  );
}

test('Home with the journey: 44px mark, the plan row, no tile grid', () => {
  const day = dayMarkState(journeyOf('short', ['scene', 'respond', 'resolution'], { upTo: 1 }));
  const html = home({ day });
  assert.match(html, /class="av2-mark"[^>]*width="44"/);
  assert.match(html, /aria-label="Aujourd’hui : 1 sur 3 — /);
  assert.doesNotMatch(html, /av2-home__tiles|av2-day-tile/);
  assert.match(html, /<ol class="av2-day-plan" aria-label="Le plan du jour">/);
  // Short day: three words, no «Mots».
  const words = [...html.matchAll(/av2-day-plan__part" data-part="(\w+)" data-state="(\w+)"/g)].map((m) => `${m[1]}:${m[2]}`);
  assert.deepEqual(words, ['scene:done', 'respond:active', 'resolution:todo']);
  assert.match(html, /Scène/);
  assert.match(html, /Réponse/);
  assert.match(html, /Bouclé/);
  assert.doesNotMatch(html, />Mots</);
  // Never colour alone: each part says its state in words.
  assert.match(html, /av2-sr"> — fait/);
  assert.match(html, /av2-sr"> — en cours/);
  assert.match(html, /av2-sr"> — à venir/);
  // No goal ring anywhere (owner, 2026-09-22).
  assert.doesNotMatch(html, /ring/i);
});

test('Home with the journey off: the plain 26px mark and the tiles, as before', () => {
  const html = home({});
  assert.match(html, /class="av2-mark"[^>]*width="26"/);
  assert.match(html, /av2-home__tiles/);
  assert.doesNotMatch(html, /av2-day-plan/);
});

test('Home: an entry with onSelect is a button, never a second primary', () => {
  // Rows are the flag-off Home's; with the journey on (WP-81) they are not
  // drawn at all, and a chip with onSelect is the button (home.test.js).
  const html = home({
    entries: [{ id: 'errata', label: 'Errata', hint: '2 à reprendre', href: '/n', onSelect: () => {} }],
  });
  assert.match(html, /<button type="button" class="av2-row" aria-label="Errata">/);
  assert.doesNotMatch(html, /av2-btn--primary/);
  const day = home({
    day: dayMarkState(null),
    entries: [{ id: 'errata', label: 'Errata', hint: '2 à reprendre', href: '/n', onSelect: () => {} }],
  });
  assert.doesNotMatch(day, /av2-row/, 'Home does one thing: no rows beside the day');
});

// --- 4. StepProgress tokens -------------------------------------------------

function tokens(count, activeIndex, face = null) {
  const kinds = ['story', 'reward', 'reward', 'action', 'done', 'reward', 'action', 'done'];
  return Array.from({ length: count }, (_, i) => ({
    id: String(i),
    shape: kinds[i % kinds.length],
    state: i < activeIndex ? 'done' : i === activeIndex ? 'active' : 'pending',
    face: i === activeIndex ? face : null,
  }));
}

test('tokens: one shape per step, ink when done, eyes on the active one only', () => {
  const html = render(h(ui.StepProgress, { steps: tokens(8, 2), label: 'Progression', caption: 'Étape 3 sur 8' }));
  assert.equal((html.match(/class="av2-token"/g) || []).length, 8);
  assert.match(html, /aria-valuetext="Étape 3 sur 8"/);
  assert.match(html, /aria-valuenow="2"/);
  assert.equal((html.match(/av2-token__face/g) || []).length, 1, 'faces only on the active token');
  assert.doesNotMatch(html, /av2-token__mouth/, 'no mouth without a verdict');
  // The caption stays, for screen readers only.
  assert.match(html, /class="av2-progress__count av2-sr">Étape 3 sur 8/);
  assert.doesNotMatch(html, /av2-progress__segment"/);
});

test('tokens: «Étape n sur m» without a caption', () => {
  const html = render(h(ui.StepProgress, { steps: tokens(3, 1), label: 'Progression' }));
  assert.match(html, /aria-valuetext="Étape 2 sur 3"/);
});

test('tokens: a verdict grins or frowns on the active token', () => {
  const grin = render(h(ui.StepProgress, { steps: tokens(5, 3, 'grin'), label: 'P' }));
  assert.match(grin, /data-state="active" data-face="grin"/);
  assert.equal((grin.match(/av2-token__mouth/g) || []).length, 1);
  const frown = render(h(ui.StepProgress, { steps: tokens(5, 3, 'frown'), label: 'P' }));
  assert.match(frown, /data-face="frown"/);
});

test('bars stay for callers without shapes (placement, reader, rehearsal)', () => {
  const html = render(
    h(ui.StepProgress, { steps: [{ id: 'a', state: 'done' }, { id: 'b', state: 'active' }], label: 'P' }),
  );
  assert.equal((html.match(/av2-progress__segment"/g) || []).length, 2);
  assert.doesNotMatch(html, /av2-token/);
});

test('css: flat fills, no wrap, Reduce Motion drops the pop and the face', () => {
  const block = css.slice(css.indexOf('WP-D1 — the mark is the day'), css.indexOf('end WP-D1 / WP-D3'));
  assert.ok(block.length > 0);
  assert.doesNotMatch(block, /\.av2-token__body[^{]*\{[^}]*stroke/, 'the token body is never stroked');
  assert.match(block, /\.av2-progress__tokens \{[^}]*flex-wrap: nowrap/);
  // 8 tokens at 18px + 7 gaps of 5px fit the session head at 320px.
  assert.ok(8 * 18 + 7 * 5 <= 320 - 2 * 14 - 44 - 2 * 14 - 28);
  const reduced = block.slice(block.indexOf('@media (prefers-reduced-motion: reduce)'));
  assert.match(reduced, /\.av2-mark__pop[\s\S]*animation: none/);
  assert.match(reduced, /\.av2-token__mouth \{ display: none/);
  // Only tokens: no new colour.
  assert.doesNotMatch(block, /#[0-9a-f]{3,6}\b|rgb\(/i);
});

test('the session head carries the mark in its right-hand slot', () => {
  const session = fs.readFileSync(path.join(__dirname, 'JourneySession.tsx'), 'utf8');
  const head = session.slice(session.indexOf('<header className="av2-session__head">'), session.indexOf('</header>'));
  assert.match(head, /<AtelierMark size=\{28\} progress=\{dayMark\.groups\} title=\{dayMark\.label\} \/>/);
  assert.match(session, /shape: STEP_SHAPE\[step\.kind\]/);
});
