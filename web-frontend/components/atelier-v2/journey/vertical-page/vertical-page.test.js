/* WP-144 «La page verticale» — the guarantees that must not regress silently.
 *   node --test components/atelier-v2/journey/vertical-page/vertical-page.test.js
 *
 *   · a balloon, a caption or a tail never covers a face (any panel size, any
 *     line lengths, one to three speakers);
 *   · what does not fit goes to the sheet, in reading order, and the sheet never
 *     docks over a face;
 *   · Reduce Motion: everything at once, no push-in, no pan;
 *   · the old/new switch: the current reader stays the default;
 *   · the lines arrive with the voice (the reveal model).
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');

require('../../../../node_modules/sucrase/register/ts');
require('../../../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../../../..');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  if (request === 'next/link') return originalResolve.call(this, path.join(ROOT, 'components/feuilleton/reader/__fixtures__/next-link-stub.js'), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const { PanelStage } = require('../../../cast/PanelStage.tsx');
const { stageFrame, headIndexFor, pushInBounds, plateFocus } = require('./page-geometry.ts');
const { layoutPanel, coversAFace, intersects, tailCrosses, tailLength, readsAfter, TAIL_MAX_SHARE } = require('./balloon-layout.ts');
const {
  revealPlan,
  revealInitial,
  revealReduce,
  revealDone,
  revealedChars,
  revealModeName,
  timedDelayMs,
  tokenShown,
} = require('./reveal-model.ts');
const { VerticalPageStyles } = require('./vertical-page-styles.tsx');
const layoutSwitch = require('../../../../lib/reader-layout.ts');
const launchFlags = require('../../../../launch-flags.json');

const CAST3 = [
  { id: 'margaux_barman', mood: 'happy', speaking: true },
  { id: 'marin_leveque', mood: 'neutral' },
  { id: 'lila_bonnet', mood: 'cold' },
];

// A small deterministic random, so a failure can be replayed.
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// geometry
// ---------------------------------------------------------------------------

/** The faces on a panel of this size for the first `count` of CAST3 (or `members`). */
function headsFor(panel, count, members = CAST3.slice(0, count), inflate) {
  return stageFrame(panel, members, inflate)?.heads ?? [];
}

test('the head boxes are the ones PanelStage draws (WP-143 fill framing, data-head)', () => {
  const panel = { w: 390, h: 650 };
  for (const count of [1, 2, 3]) {
    const members = CAST3.slice(0, count);
    const frame = stageFrame(panel, members, 0);
    const html = renderToStaticMarkup(React.createElement(PanelStage, { members, framing: 'fill', aspect: frame.aspect, light: false }));
    const drawn = [...html.matchAll(/data-head="([^"]+)"/g)].map((match) => match[1].split(' ').map(Number));
    assert.equal(drawn.length, count, `${count} figures drawn`);
    drawn.forEach(([x, y, w, h], index) => {
      const head = frame.heads[index];
      const px = { x: frame.box.x + (x / 100) * frame.box.w, y: frame.box.y + (y / 100) * frame.box.h, w: (w / 100) * frame.box.w, h: (h / 100) * frame.box.h };
      for (const key of ['x', 'y', 'w', 'h']) assert.ok(Math.abs(px[key] - head[key]) < 1, `${count}/${index}: ${key} ${px[key]} vs ${head[key]}`);
    });
  }
});

test('a medium shot: the faces are large and above the panel foot, never on its bottom edge', () => {
  for (const panel of [{ w: 390, h: 650 }, { w: 375, h: 620 }, { w: 320, h: 460 }, { w: 414, h: 720 }]) {
    for (const count of [1, 2, 3]) {
      const heads = headsFor(panel, count, undefined, 0);
      assert.equal(heads.length, count);
      heads.forEach((head) => {
        assert.ok(head.y >= 0 && head.x >= 0 && head.x + head.w <= panel.w + 0.5, 'head inside the panel');
        assert.ok(head.y + head.h <= panel.h * 0.83, `${count}: the face clears the panel's foot`);
        assert.ok(head.w >= panel.w * 0.25, `${count}: a face a quarter of the width at least (${head.w.toFixed(0)}px)`);
      });
    }
  }
  const panel = { w: 390, h: 650 };
  assert.ok(headsFor(panel, 1, undefined, 0)[0].w > headsFor(panel, 3, undefined, 0)[0].w, 'one speaker is a closer shot than three');
  // Toi and an unknown speaker have no face on the stage.
  const heads = headsFor(panel, 1, [{ id: 'toi', speaking: true }, { id: 'margaux_barman' }]);
  assert.equal(heads.length, 1);
  assert.equal(headIndexFor(heads, { speakerId: 'margaux_barman', who: 'Margaux' }), 0);
  assert.equal(headIndexFor(heads, { speakerId: null, who: 'Vous' }), -1);
  assert.equal(stageFrame(panel, []), null);
});

test('the push-in bound contains the face at the start and at the end of the beat', () => {
  const box = { x: 100, y: 200, w: 80, h: 90 };
  const bound = pushInBounds(box, { x: 0, y: 0 }, 1.1);
  assert.ok(bound.x <= 100 && bound.y <= 200);
  assert.ok(bound.x + bound.w >= 110 + 88 - 0.001 && bound.y + bound.h >= 220 + 99 - 0.001);
});

test('the plate is cropped per beat: the first panel is the establishing middle, then the lead speaker’s side', () => {
  assert.deepEqual(plateFocus({ ordinal: 1, cast: CAST3 }), { x: 50, y: 50 });
  assert.ok(plateFocus({ ordinal: 2, cast: CAST3 }).x < 50, 'the lead stands left: the camera looks left');
  const a = plateFocus({ ordinal: 2, cast: [], silent: true }).x;
  const b = plateFocus({ ordinal: 3, cast: [], silent: true }).x;
  assert.notEqual(a, b, 'two silent beats are two crops');
});

// ---------------------------------------------------------------------------
// balloon placement — never over a face
// ---------------------------------------------------------------------------

function randomItems(random, heads) {
  const items = [];
  if (random() < 0.6) items.push({ key: 'cap', kind: 'caption', size: { w: 140 + random() * 200, h: 30 + random() * 50 }, anchor: -1 });
  const n = 1 + Math.floor(random() * 6);
  for (let i = 0; i < n; i += 1) {
    const you = random() < 0.15;
    items.push({
      key: `l${i}`,
      kind: you ? 'you' : 'speech',
      size: { w: 70 + random() * 240, h: 36 + random() * 140 },
      anchor: you || !heads.length ? -1 : Math.floor(random() * (heads.length + 1)) - 1,
    });
  }
  return items;
}

test('placement never covers a face, never overlaps two balloons, never leaves the panel', () => {
  const random = rng(144);
  const panels = [{ w: 375, h: 620 }, { w: 320, h: 460 }, { w: 414, h: 720 }, { w: 560, h: 840 }];
  let placedTotal = 0;
  for (let round = 0; round < 1500; round += 1) {
    const panel = panels[round % panels.length];
    const count = 1 + (round % 3);
    const heads = headsFor(panel, count);
    const items = randomItems(random, heads);
    const result = layoutPanel(panel, heads, items, { topInset: round % 5 === 0 ? 36 : 0 });
    assert.equal(coversAFace(result, heads), false, `round ${round}: a face is covered`);
    result.placed.forEach((entry) => {
      if (!entry.tail) return;
      assert.ok(tailLength(entry.tail) <= panel.h * TAIL_MAX_SHARE + 0.5, `round ${round}: ${entry.key}'s tail is too long`);
      result.placed.forEach((other) => {
        if (other !== entry) assert.equal(tailCrosses(entry.tail, other), false, `round ${round}: ${entry.key}'s tail crosses ${other.key}`);
      });
    });
    result.placed.forEach((a, i) => {
      assert.ok(a.x >= 0 && a.y >= 0 && a.x + a.w <= panel.w + 0.5 && a.y + a.h <= panel.h + 0.5, `round ${round}: inside the panel`);
      result.placed.slice(i + 1).forEach((b) => assert.equal(intersects(a, b), false, `round ${round}: ${a.key} overlaps ${b.key}`));
    });
    // Every item is either placed or in the sheet, exactly once.
    const keys = [...result.placed.map((entry) => entry.key), ...result.overflow].sort();
    assert.deepEqual(keys, items.map((item) => item.key).sort());
    placedTotal += result.placed.length;
  }
  assert.ok(placedTotal > 3000, 'the layout places most lines, it does not dodge by overflowing everything');
});

test('a short line sits above its speaker, with a tail that points down at them', () => {
  const panel = { w: 375, h: 620 };
  const heads = headsFor(panel, 1);
  const result = layoutPanel(panel, heads, [{ key: 'a', kind: 'speech', size: { w: 200, h: 60 }, anchor: 0 }]);
  const [balloon] = result.placed;
  assert.ok(balloon, 'placed');
  assert.equal(balloon.tail.side, 'down');
  assert.ok(balloon.y + balloon.h < heads[0].y, 'above the head');
  assert.ok(heads[0].y - (balloon.y + balloon.h) <= 40, 'settled near the speaker, not left at the top');
  assert.equal(result.sheet.mode, 'none');
});

test('three speakers read in the order they speak', () => {
  const panel = { w: 375, h: 620 };
  const heads = headsFor(panel, 3);
  const items = [0, 1, 2].map((i) => ({ key: `l${i}`, kind: 'speech', size: { w: 170, h: 58 }, anchor: i }));
  const result = layoutPanel(panel, heads, items);
  assert.ok(result.placed.length >= 2, 'two of three wide lines on the picture at least');
  result.placed.forEach((entry, i) =>
    result.placed.slice(0, i).forEach((prev) => assert.ok(readsAfter(entry, prev), `${entry.key} reads after ${prev.key}`)),
  );
});

test('a later line is to the right on the same row, or clearly lower (wholly, when it sits to the left)', () => {
  // The gallery's third panel: Marin, Margaux, then «Vous» with no face on stage.
  const panel = { w: 390, h: 650 };
  const heads = headsFor(panel, 2);
  const items = [
    { key: 'cap', kind: 'caption', size: { w: 200, h: 40 }, anchor: -1 },
    { key: 'l0', kind: 'speech', size: { w: 160, h: 62 }, anchor: 0 },
    { key: 'l1', kind: 'speech', size: { w: 120, h: 62 }, anchor: 1 },
    { key: 'l2', kind: 'speech', size: { w: 110, h: 62 }, anchor: -1 },
  ];
  const result = layoutPanel(panel, heads, items);
  const spoken = result.placed.filter((entry) => entry.kind === 'speech');
  for (let i = 1; i < spoken.length; i += 1) {
    const [before, after] = [spoken[i - 1], spoken[i]];
    const right = after.x >= before.x + before.w - 2 && after.y >= before.y - 4;
    assert.ok(right || after.y - before.y >= 24, `${after.key} is to the right of ${before.key}, or clearly below it`);
    if (!right && after.x + after.w / 2 < before.x + before.w / 2) {
      assert.ok(after.y >= before.y + before.h, `${after.key}, to the left, starts under ${before.key}`);
    }
  }
});

test('the learner’s own line is the bottom-edge balloon, the point of view', () => {
  const panel = { w: 375, h: 620 };
  const result = layoutPanel(panel, [], [{ key: 'you', kind: 'you', size: { w: 220, h: 64 }, anchor: -1 }]);
  const [you] = result.placed;
  assert.ok(Math.abs(you.y + you.h - (panel.h - 12)) < 1, 'on the bottom edge');
  assert.ok(Math.abs(you.x + you.w - (panel.w - 12)) < 1, 'on the right');
});

test('three speakers: every balloon within a short tail of its own head, or the oldest goes to the sheet', () => {
  // The gallery's three-speaker beat at phone sizes: a caption, then each speaker once.
  for (const panel of [{ w: 390, h: 650 }, { w: 375, h: 620 }, { w: 414, h: 720 }]) {
    const heads = headsFor(panel, 3);
    const items = [
      { key: 'cap', kind: 'caption', size: { w: 190, h: 40 }, anchor: -1 },
      { key: 'l0', kind: 'speech', size: { w: 162, h: 62 }, anchor: 0 },
      { key: 'l1', kind: 'speech', size: { w: 118, h: 62 }, anchor: 1 },
      { key: 'l2', kind: 'speech', size: { w: 140, h: 62 }, anchor: 2 },
    ];
    const result = layoutPanel(panel, heads, items);
    const cap = panel.h * TAIL_MAX_SHARE;
    const spoken = result.placed.filter((entry) => entry.kind === 'speech');
    assert.ok(spoken.length >= 2, `${panel.w}: at least two of three on the picture`);
    spoken.forEach((entry) => {
      assert.ok(entry.tail, `${entry.key} points at its speaker`);
      assert.ok(tailLength(entry.tail) <= cap + 0.5, `${entry.key}: tail ${tailLength(entry.tail).toFixed(0)} > ${cap.toFixed(0)}`);
      const head = heads[entry.anchor];
      const reach = Math.max(head.x - (entry.x + entry.w), entry.x - (head.x + head.w), head.y - (entry.y + entry.h), 0);
      assert.ok(reach <= cap, `${entry.key} sits near its own head`);
    });
    // Whatever left the picture is the oldest line(s).
    const spokenKeys = ['l0', 'l1', 'l2'];
    assert.deepEqual(result.overflow.filter((key) => spokenKeys.includes(key)), spokenKeys.slice(0, 3 - spoken.length));
    assert.equal(coversAFace(result, heads), false);
  }
});

test('a four-line, three-speaker panel never hangs a line on a long tail', () => {
  const panel = { w: 390, h: 650 };
  const heads = headsFor(panel, 3);
  const items = [0, 1, 2, 3].map((i) => ({ key: `l${i}`, kind: 'speech', size: { w: 150, h: 62 }, anchor: i % 3 }));
  const result = layoutPanel(panel, heads, items);
  result.placed.forEach((entry) => assert.ok(tailLength(entry.tail) <= panel.h * TAIL_MAX_SHARE + 0.5));
  assert.equal(result.placed.length + result.overflow.length, 4);
});

// ---------------------------------------------------------------------------
// overflow — the sheet
// ---------------------------------------------------------------------------

test('lines that do not fit go to the sheet, in reading order, docked under the faces', () => {
  const panel = { w: 375, h: 620 };
  const heads = headsFor(panel, 3);
  const items = [0, 1, 2, 3, 4, 5].map((i) => ({ key: `l${i}`, kind: 'speech', size: { w: 300, h: 150 }, anchor: i % 3 }));
  const result = layoutPanel(panel, heads, items);
  assert.ok(result.overflow.length > 0, 'something overflows');
  const placedKeys = result.placed.map((entry) => entry.key);
  // Reading order: the sheet holds the oldest lines or the newest, never a hole in the dialogue.
  const all = items.map((item) => item.key);
  const sheet = result.overflow;
  const prefix = all.slice(0, sheet.length);
  const suffix = all.slice(all.length - sheet.length);
  assert.ok(
    JSON.stringify(sheet) === JSON.stringify(prefix) || JSON.stringify(sheet) === JSON.stringify(suffix),
    `the sheet ${sheet} is the start or the end of the dialogue`,
  );
  assert.deepEqual([...placedKeys].sort(), all.filter((key) => !sheet.includes(key)).sort());
  const lowestFace = Math.max(...heads.map((head) => head.y + head.h));
  if (result.sheet.mode === 'dock') {
    assert.ok(panel.h - result.sheet.maxHeight >= lowestFace, 'the docked sheet stays under the lowest face');
  } else {
    assert.equal(result.sheet.mode, 'below');
  }
  assert.equal(coversAFace(result, heads), false);
});

test('a close shot leaves no room under the face: the sheet goes under the panel', () => {
  const panel = { w: 375, h: 620 };
  const heads = headsFor(panel, 1);
  const items = [0, 1, 2, 3].map((i) => ({ key: `l${i}`, kind: 'speech', size: { w: 320, h: 170 }, anchor: 0 }));
  const result = layoutPanel(panel, heads, items, { minSheet: 400 });
  assert.ok(result.overflow.length > 0);
  assert.equal(result.sheet.mode, 'below');
});

test('a painted panel (faces unknown) keeps its lines high and sends the rest under the panel', () => {
  const panel = { w: 375, h: 620 };
  const items = [0, 1, 2, 3].map((i) => ({ key: `l${i}`, kind: 'speech', size: { w: 240, h: 90 }, anchor: -1 }));
  const result = layoutPanel(panel, [], items, { unknownFaces: true });
  result.placed.forEach((entry) => assert.ok(entry.y + entry.h <= panel.h * 0.4 + 0.5, 'in the top zone'));
  assert.ok(result.overflow.length > 0);
  assert.equal(result.sheet.mode, 'below');
});

test('the learner’s line joins a docked sheet rather than sitting on it', () => {
  const panel = { w: 375, h: 620 };
  const heads = headsFor(panel, 3);
  const items = [
    ...[0, 1, 2, 3, 4].map((i) => ({ key: `l${i}`, kind: 'speech', size: { w: 300, h: 140 }, anchor: i % 3 })),
    { key: 'you', kind: 'you', size: { w: 200, h: 60 }, anchor: -1 },
  ];
  const result = layoutPanel(panel, heads, items);
  if (result.sheet.mode === 'dock') assert.ok(result.overflow.includes('you'));
});

// ---------------------------------------------------------------------------
// the reveal
// ---------------------------------------------------------------------------

test('reveal plan: voice, timed, or all at once (Reduce Motion)', () => {
  const voice = revealPlan({ reducedMotion: false, voicesAloud: true, voiceSupported: true, lineCount: 3 });
  assert.deepEqual(voice, { text: 'sequence', speak: true, words: true });
  assert.equal(revealModeName(voice), 'voice');
  const timed = revealPlan({ reducedMotion: false, voicesAloud: false, voiceSupported: true, lineCount: 3 });
  assert.equal(revealModeName(timed), 'timed');
  assert.equal(timed.words, false);
  const reduced = revealPlan({ reducedMotion: true, voicesAloud: true, voiceSupported: true, lineCount: 3 });
  assert.equal(revealModeName(reduced), 'all');
  assert.equal(reduced.words, false, 'no word-by-word under Reduce Motion');
  assert.equal(reduced.speak, true, 'sound is not motion: the lines are still said');
  assert.equal(revealInitial(reduced, 3).shown, 3, 'everything there at once');
  assert.equal(revealModeName(revealPlan({ reducedMotion: false, voicesAloud: false, voiceSupported: false, lineCount: 1 })), 'all');
});

test('lines open one at a time with the voice, and a tap shows everything', () => {
  const plan = revealPlan({ reducedMotion: false, voicesAloud: true, voiceSupported: true, lineCount: 3 });
  let state = revealInitial(plan, 3);
  assert.equal(state.shown, 0);
  state = revealReduce(state, { type: 'line-started', index: 0 }, 3);
  assert.deepEqual(state, { shown: 1, speaking: 0 });
  state = revealReduce(state, { type: 'line-ended', index: 0 }, 3);
  assert.deepEqual(state, { shown: 2, speaking: -1 }, 'the next balloon opens when the line ends');
  // A late «ended» for an old line changes nothing.
  assert.deepEqual(revealReduce(state, { type: 'line-ended', index: 0 }, 3), state);
  state = revealReduce(state, { type: 'all' }, 3);
  assert.ok(revealDone(state, 3));
});

test('the words follow the audio clock; punctuation comes with its word', () => {
  const line = 'Bonjour, Lila.';
  assert.equal(revealedChars(line, 0), 0);
  assert.equal(revealedChars(line, null), line.length, 'no clock: the whole line');
  assert.equal(revealedChars(line, 1), line.length);
  const half = revealedChars(line, 0.5);
  assert.ok(half > 0 && half < line.length);
  assert.equal(tokenShown(0, 0), true, 'the first word is there as the voice starts');
  assert.equal(tokenShown(9, 4), false);
  assert.equal(tokenShown(9, null), true);
  assert.ok(timedDelayMs('Non.') >= 900 && timedDelayMs('x'.repeat(400)) <= 2600);
});

test('TappableFrench hides the words not yet said, without reflowing the line', () => {
  const { FrenchLine } = require('../../../feuilleton/reader/TappableFrench.tsx');
  const html = renderToStaticMarkup(
    React.createElement(FrenchLine, { text: 'Bonjour, Lila.', idPrefix: 'x', onWord: () => {}, revealChars: 3 }),
  );
  assert.match(html, /<button[^>]*data-word=""(?![^>]*data-unrevealed)[^>]*>Bonjour<\/button>/);
  assert.match(html, /<button[^>]*data-unrevealed=""[^>]*>Lila<\/button>/);
  assert.match(html, /aria-label="Bonjour, Lila\."/, 'a screen reader still hears the whole sentence');
  const full = renderToStaticMarkup(React.createElement(FrenchLine, { text: 'Bonjour, Lila.', idPrefix: 'x', onWord: () => {} }));
  assert.doesNotMatch(full, /data-unrevealed/);
});

test('Reduce Motion stops the push-in, the pan and the arrival', () => {
  const css = renderToStaticMarkup(React.createElement(VerticalPageStyles));
  const reduced = css.slice(css.indexOf('prefers-reduced-motion: reduce'));
  assert.match(reduced, /\.vp-camera,\s*\.av2 \.vp-plate \{ animation: none !important; transform: none !important; \}/);
  // Every animation in the sheet sits inside the no-preference block.
  const motion = css.slice(css.indexOf('prefers-reduced-motion: no-preference'), css.indexOf('prefers-reduced-motion: reduce'));
  const outside = css.replace(motion, '');
  assert.doesNotMatch(outside, /animation:(?!\s*none)/, 'no animation outside the motion block');
});

// ---------------------------------------------------------------------------
// the switch, and the panel in the reader
// ---------------------------------------------------------------------------

test('the switch: the current reader stays the default until the owner’s A/B', () => {
  assert.equal(layoutSwitch.defaultReaderLayout(launchFlags), 'list');
  assert.equal(layoutSwitch.defaultReaderLayout({}), 'list');
  assert.equal(layoutSwitch.defaultReaderLayout({ readerLayout: 'vertical' }), 'vertical');
  assert.equal(layoutSwitch.defaultReaderLayout({ readerLayout: 'sideways' }), 'list');
  assert.equal(layoutSwitch.readerLayoutFromQuery('?readerLayout=vertical'), 'vertical');
  assert.equal(layoutSwitch.readerLayoutFromQuery('?readerLayout=list'), 'list');
  assert.equal(layoutSwitch.readerLayoutFromQuery('?readerLayout=default'), null);
  assert.equal(layoutSwitch.readerLayoutFromQuery('?reader=ready'), undefined);
  assert.equal(layoutSwitch.readerLayoutFromQuery('?readerLayout=nonsense'), undefined);
});

function storyEpisode() {
  const panels = [
    {
      id: 'p1',
      index: 0,
      narration_fr: 'Le Mistral, huit heures.',
      dialogue: [{ character_id: 'margaux_barman', character_name: 'Margaux', text_fr: 'Bonjour ! Qu’est-ce que je vous sers ?', text_native: 'Hello!' }],
      image_url: '/assets/serial/locations/le_mistral-counter.webp',
      image_status: 'panel_art',
      plate_url: '/assets/serial/locations/le_mistral-counter.webp',
    },
    { id: 'p2', index: 1, narration_fr: '', dialogue: [], image_url: '/assets/serial/locations/le_mistral-counter.webp', image_status: 'setting_reference' },
    {
      id: 'p3',
      index: 2,
      narration_fr: '',
      dialogue: [
        { character_id: 'toi', character_name: 'Vous', you: true, text_fr: 'Un café, s’il vous plaît.' },
        { character_id: 'margaux_barman', character_name: 'Margaux', text_fr: 'Tout de suite.' },
      ],
      image_url: '/assets/serial/locations/le_mistral-counter.webp',
      image_status: 'panel_art',
    },
  ];
  return {
    id: 'ep-1',
    scene_id: 'ep-1',
    serial_thread_id: '',
    serial_episode_id: null,
    journey_id: 'j',
    title_fr: 'Le Mistral',
    status: 'available',
    chapter: { id: 'c1', title_fr: 'Chapitre 1' },
    panel_index: 0,
    panels,
    resolution: null,
    grammar_focus: null,
  };
}

function renderReader(props) {
  const { StoryEpisodeReader } = require('../StoryEpisodeReader.tsx');
  return renderToStaticMarkup(React.createElement(StoryEpisodeReader, { episode: storyEpisode(), mode: 'continue', savePosition: false, ...props }));
}

test('the vertical page replaces only the panel body; the reader around it is kept', () => {
  const html = renderReader({ layout: 'vertical' });
  assert.match(html, /data-layout="vertical"/);
  assert.match(html, /class="vp-panel"/);
  assert.match(html, /class="vp-caption__title"[^>]*>Le Mistral</, 'the headline is the establishing caption');
  assert.doesNotMatch(html, /class="fr-head"/, 'no headline above the panel');
  assert.match(html, /class="fr-dots"/, 'the progress dots stay');
  assert.match(html, /class="fr-btn fr-prev"/, '← stays');
  assert.match(html, /class="fr-btn fr-next"/, 'Weiter stays');
  assert.match(html, /aria-pressed="false"[^>]*>(<span[^>]*><\/span>)?Traduire/, '«Übersetzen» stays in the bar');
  assert.doesNotMatch(html, /class="fr-captions"/, 'no list of grey cards under a picture');
  // Every word of a line is still a word to tap.
  assert.match(html, /<button[^>]*class="fr-word"[^>]*>Bonjour<\/button>/);
});

test('the current reader is untouched when the switch says list', () => {
  const html = renderReader({ layout: 'list' });
  assert.doesNotMatch(html, /vp-panel|data-layout/);
  assert.match(html, /class="fr-head"/);
});

test('the silent panel keeps its caption on the vertical page (WP-137)', () => {
  const { FeuilletonReader } = require('../../../feuilleton/reader/FeuilletonReader.tsx');
  const { buildStoryStages } = require('../story-episode-model.ts');
  const stages = buildStoryStages(storyEpisode());
  const html = renderToStaticMarkup(
    React.createElement(FeuilletonReader, {
      episodeLabel: 'Épisode 1',
      title: 'Le Mistral',
      stages,
      index: 1,
      furthest: 1,
      onIndexChange: () => {},
      answers: {},
      setAnswer: () => {},
      onSubmit: () => {},
      submittingTask: null,
      attemptsByTask: {},
      submitError: null,
      liveTaskId: null,
      panelVariant: () => 'line',
      layout: 'vertical',
    }),
  );
  assert.match(html, /data-silent="true"/);
  assert.match(html, /vp-caption__line--silent[^>]*>Un silence\.</);
});

test('the learner’s line is drawn as the you-balloon', () => {
  const { FeuilletonReader } = require('../../../feuilleton/reader/FeuilletonReader.tsx');
  const { buildStoryStages } = require('../story-episode-model.ts');
  const stages = buildStoryStages(storyEpisode());
  const html = renderToStaticMarkup(
    React.createElement(FeuilletonReader, {
      episodeLabel: 'Épisode 1', title: 'Le Mistral', stages, index: 2, furthest: 2,
      onIndexChange: () => {}, answers: {}, setAnswer: () => {}, onSubmit: () => {}, submittingTask: null,
      attemptsByTask: {}, submitError: null, liveTaskId: null, panelVariant: () => 'bubble', layout: 'vertical',
    }),
  );
  assert.match(html, /class="vp-balloon vp-balloon--you[^"]*"[^>]*data-measure/);
});
