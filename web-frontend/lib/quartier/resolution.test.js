// node --test lib/quartier/resolution.test.js
//
// Le Quartier · the resolution follows the phone's work, not the display's cadence. The owner's
// iPhone showed Marin and Lila's flat blocky and smeared (13 Nov 2026): the old rule read a 30 Hz
// loop (Low Power Mode, a throttled web view) as a struggling phone and fell to the floor, and at
// 60 Hz it never climbed back after a hitch. These tests play the frame intervals a phone gives.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { ResolutionGovernor, SCALE_CEILING, SCALE_FLOOR } = require('./resolution.ts');

/** Play `seconds` of frames whose interval `interval(i)` gives (ms); returns the governor's last scale. */
function play(g, seconds, interval, clock = { t: 0, i: 0 }) {
  const end = clock.t + seconds * 1000;
  while (clock.t < end) {
    const ms = interval(clock.i++, g.scale);
    clock.t += ms;
    g.frame(ms, clock.t);
  }
  return g.scale;
}

test('a 60 Hz phone that keeps up stays at full resolution', () => {
  const g = new ResolutionGovernor(2);
  assert.equal(play(g, 20, () => 16.67), 2);
});

test('a phone in Low Power Mode (30 Hz) keeps its full resolution: fewer pixels would not make the display faster', () => {
  const g = new ResolutionGovernor(2);
  const clock = { t: 0, i: 0 };
  // the probe lowers it one step for a moment, finds the frames no faster, and puts it back
  const scales = [];
  for (let s = 0; s < 20; s++) scales.push(play(g, 1, () => 33.33, clock));
  assert.equal(scales[scales.length - 1], 2);
  assert.ok(Math.min(...scales) >= 1.4 - 1e-9, `it never fell further than the probe: ${scales.join(' ')}`);
  assert.ok(scales.filter((s) => s === 2).length >= 16, `the probe is a moment: ${scales.join(' ')}`);
  // the old rule ended this at the floor, a third of a phone's pixels
  assert.ok(SCALE_FLOOR < 1);
});

test('a hitch (a page handed over, the cast standing up) does not lower the resolution for good', () => {
  const g = new ResolutionGovernor(2);
  const clock = { t: 0, i: 0 };
  play(g, 3, () => 16.67, clock);
  for (let k = 0; k < 3; k++) {
    // a few frames of 45 ms, then the usual
    let left = 30;
    play(g, 2.5, () => (left-- > 0 ? 45 : 16.67), clock);
  }
  // back at full resolution within half a minute of steady frames
  assert.equal(play(g, 30, () => 16.67, clock), 2);
});

test('a phone that cannot keep up at full resolution draws fewer pixels until it can', () => {
  // the frame's cost grows with the pixels: 60 Hz is held only at 1.4 or less
  const cost = (scale) => (scale > 1.45 ? 33.33 : 16.67);
  const g = new ResolutionGovernor(2);
  const clock = { t: 0, i: 0 };
  play(g, 1, () => 16.67, clock);
  play(g, 30, (_i, scale) => cost(scale), clock);
  // over the next minute it draws at a scale the phone keeps up with nearly all the time, and
  // never lower than it needs
  let kept = 0;
  let all = 0;
  let low = 9;
  play(g, 60, (_i, scale) => {
    all++;
    if (scale <= 1.45) kept++;
    low = Math.min(low, scale);
    return cost(scale);
  }, clock);
  assert.ok(kept / all > 0.8, `frames at a scale it keeps up with: ${((100 * kept) / all).toFixed(0)}%`);
  assert.ok(low >= 1.2, `never lower than it needs: ${low}`);
});

test('a phone that runs at 30 fps from its first frame is told from a throttled display by the probe', () => {
  // a 60 Hz display, but the phone only manages 30 fps above 1.5
  const cost = (scale) => (scale > 1.5 ? 33.33 : 16.67);
  const g = new ResolutionGovernor(2);
  const clock = { t: 0, i: 0 };
  play(g, 10, (_i, scale) => cost(scale), clock);
  let kept = 0;
  let all = 0;
  play(g, 40, (_i, scale) => {
    all++;
    if (scale <= 1.5) kept++;
    return cost(scale);
  }, clock);
  assert.ok(kept / all > 0.8, `the probe found faster frames with fewer pixels, and it stays there: ${((100 * kept) / all).toFixed(0)}%`);
});

test('a ProMotion display (120 Hz) and the ceiling', () => {
  const g = new ResolutionGovernor(3);
  assert.equal(play(g, 10, () => 8.33), SCALE_CEILING);
});
