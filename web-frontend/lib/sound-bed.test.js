// node --test lib/sound-bed.test.js
//
// WP-145 «Ambiance» — the sound bed under a story scene.
//   1. every place of season 1 has a bed; unknown places get the quiet default;
//      a plate's file name names its place;
//   2. the beds are 10–20 s, seamless at the loop point, levelled, deterministic;
//   3. ducking: −12 dB while a line plays, a short ramp down, a slower one up,
//      and a new ramp starts from wherever the last one is;
//   4. gates: «Sons» (the mute switch) and «Ambiance» (off by default on the
//      web, on in the app), and the page being hidden;
//   5. no AudioContext is created before the learner's gesture, nor at all when
//      a gate is closed; hiding the page stops the bed and suspends the context.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const B = require('./sound-bed.ts');

// ---------------------------------------------------------------------------

test('every season-1 place has a bed, and the brief\'s places sound as asked', () => {
  const world = fs.readFileSync(path.join(WEB_ROOT, '..', 'app/services/season/world.py'), 'utf8');
  const block = world.split('SEASON_ONE_LOCATIONS')[1].split('\n}\n')[0];
  const ids = [...block.matchAll(/^\s+"([a-z_]+)": \{"name_fr"/gm)].map((m) => m[1]);
  assert.ok(ids.length >= 20, `expected the season's places, read ${ids.length}`);
  for (const id of ids) assert.ok(B.PLACE_BEDS[id], `${id} has no bed`);
  assert.equal(B.bedForPlace('le_mistral'), 'cafe');
  assert.equal(B.bedForPlace('quai_de_valmy'), 'canal');
  assert.equal(B.bedForPlace('boulangerie'), 'market');
  assert.equal(B.bedForPlace('marche_canal'), 'market');
  assert.equal(B.bedForPlace('metro_platform'), 'metro');
  assert.equal(B.bedForPlace('user_apartment'), 'room');
  assert.equal(B.bedForPlace('marin_lila_flat'), 'room');
  assert.equal(B.bedForPlace('stairwell'), 'stairwell');
  assert.equal(B.bedForPlace('ngo_office'), 'office');
  assert.equal(B.bedForPlace(' LE_MISTRAL '), 'cafe');
  for (const unknown of [null, undefined, '', 'atlantis']) assert.equal(B.bedForPlace(unknown), B.DEFAULT_BED);
  assert.equal(B.DEFAULT_BED, 'room');
  for (const bed of Object.values(B.PLACE_BEDS)) assert.ok(B.BED_IDS.includes(bed));
});

test("a plate's file name names its place; the location id wins over it", () => {
  assert.equal(B.placeFromPlate('/assets/serial/locations/le_mistral-counter.webp'), 'le_mistral');
  assert.equal(B.placeFromPlate('https://cdn.example/assets/serial/locations/metro_platform.webp?v=2'), 'metro_platform');
  assert.equal(B.placeFromPlate('/assets/serial/characters/odile/portrait.webp'), null);
  assert.equal(B.placeFromPlate(null), null);
  assert.equal(B.scenePlace('quai_de_valmy', '/assets/serial/locations/le_mistral-counter.webp'), 'quai_de_valmy');
  assert.equal(B.scenePlace(null, '/assets/serial/locations/ngo_office.webp'), 'ngo_office');
  assert.equal(B.scenePlace('', null), null);
});

test('each bed is a 10–20 s stereo loop with no seam, levelled and repeatable', () => {
  assert.ok(B.BED_SECONDS >= 10 && B.BED_SECONDS <= 20);
  for (const bed of B.BED_IDS) {
    const out = B.renderBed(bed);
    const [left, right] = out.channels;
    assert.equal(out.sampleRate, B.BED_SAMPLE_RATE);
    assert.equal(left.length, B.BED_SECONDS * B.BED_SAMPLE_RATE, bed);
    assert.equal(right.length, left.length);
    let sum = 0;
    let top = 0;
    for (const ch of out.channels) {
      for (const v of ch) {
        assert.ok(Number.isFinite(v), `${bed} has a non-finite sample`);
        sum += v * v;
        top = Math.max(top, Math.abs(v));
      }
    }
    const rms = Math.sqrt(sum / (2 * left.length));
    assert.ok(Math.abs(rms - B.BED_LEVEL[bed]) / B.BED_LEVEL[bed] < 0.05 || top >= B.BED_PEAK - 1e-6, `${bed} rms ${rms}`);
    assert.ok(top <= B.BED_PEAK + 1e-6, `${bed} peaks at ${top}`);
    // The jump from the last sample back to the first is an ordinary step.
    for (const ch of out.channels) {
      const steps = [];
      for (let i = 1; i < ch.length; i += 1) steps.push(Math.abs(ch[i] - ch[i - 1]));
      steps.sort((a, b) => a - b);
      const ordinary = steps[Math.floor(steps.length * 0.999)];
      const seam = Math.abs(ch[0] - ch[ch.length - 1]);
      assert.ok(seam <= ordinary, `${bed} seam ${seam} > ${ordinary}`);
    }
  }
  const a = B.renderBed('cafe', { seconds: 2 });
  const b = B.renderBed('cafe', { seconds: 2 });
  assert.deepEqual(Array.from(a.channels[0].slice(0, 64)), Array.from(b.channels[0].slice(0, 64)));
  // Quiet rooms are quieter than streets.
  assert.ok(B.BED_LEVEL.room < B.BED_LEVEL.cafe && B.BED_LEVEL.room < B.BED_LEVEL.market);
});

test('ducking: −12 dB under a line, a short ramp down and a slower one up', () => {
  assert.ok(Math.abs(B.dbToGain(-12) - 0.2512) < 1e-3);
  assert.equal(B.duckTarget(false), 1);
  assert.ok(Math.abs(20 * Math.log10(B.duckTarget(true)) - B.DUCK_DB) < 1e-9);
  assert.equal(B.DUCK_DB, -12);
  assert.ok(B.DUCK_ATTACK_S > 0 && B.DUCK_ATTACK_S <= 0.25);
  assert.ok(B.DUCK_RELEASE_S > B.DUCK_ATTACK_S);

  const down = B.duckRamp(B.holdRamp(1), true, 10);
  assert.deepEqual([down.from, down.start], [1, 10]);
  assert.ok(Math.abs(down.end - (10 + B.DUCK_ATTACK_S)) < 1e-9);
  assert.equal(B.rampValueAt(down, 9), 1);
  assert.ok(Math.abs(B.rampValueAt(down, 10 + B.DUCK_ATTACK_S / 2) - (1 + B.duckTarget(true)) / 2) < 1e-9);
  assert.equal(B.rampValueAt(down, 11), B.duckTarget(true));

  const up = B.duckRamp(down, false, 12);
  assert.equal(up.from, B.duckTarget(true));
  assert.ok(Math.abs(up.end - (12 + B.DUCK_RELEASE_S)) < 1e-9);

  // A line that starts halfway back up ducks from there, in half the attack.
  const mid = 12 + B.DUCK_RELEASE_S / 2;
  const again = B.duckRamp(up, true, mid);
  assert.ok(Math.abs(again.from - B.rampValueAt(up, mid)) < 1e-9);
  assert.ok(Math.abs(again.end - mid - B.DUCK_ATTACK_S / 2) < 1e-6);
  // Already there: a zero-length ramp.
  const still = B.duckRamp(B.holdRamp(1), false, 3);
  assert.equal(still.end, 3);
});

// ---------------------------------------------------------------------------
// Gates

function withWindow(store, native, fn) {
  global.window = {
    localStorage: { getItem: (key) => (store.has(key) ? store.get(key) : null), setItem: (key, value) => store.set(key, value) },
  };
  try {
    return fn();
  } finally {
    delete global.window;
  }
}

test('gates: «Sons» is the mute switch; «Ambiance» is off by default on the web, on in the app', () => {
  assert.equal(B.ambianceGate({ sounds: true, ambiance: true }), true);
  assert.equal(B.ambianceGate({ sounds: false, ambiance: true }), false);
  assert.equal(B.ambianceGate({ sounds: true, ambiance: false }), false);
  assert.equal(B.ambianceGate({ sounds: true, ambiance: true, hidden: true }), false);
  assert.equal(B.defaultAmbianceEnabled(false), false);
  assert.equal(B.defaultAmbianceEnabled(true), true);
  assert.equal(B.AMBIANCE_PREFERENCE_KEY, 'atelier.ambiance');

  const store = new Map();
  withWindow(store, false, () => {
    // The web, nobody has chosen: off (and «Sons» is off by default too).
    assert.equal(B.ambiancePreferred(), false);
    assert.equal(B.ambianceEnabled(), false);
    B.setAmbianceEnabled(true);
    assert.equal(store.get('atelier.ambiance'), 'on');
    assert.equal(B.ambiancePreferred(), true);
    assert.equal(B.ambianceEnabled(), false, '«Sons» off silences the bed');
    store.set('atelier.sounds', 'on');
    assert.equal(B.ambianceEnabled(), true);
    B.setAmbianceEnabled(false);
    assert.equal(B.ambianceEnabled(), false);
  });
  // No window (server rendering): never.
  assert.equal(B.ambianceEnabled(), false);
  assert.equal(B.ambiancePreferred(), false);
});

// ---------------------------------------------------------------------------
// Playback with a fake AudioContext

function fakeParam(log, name) {
  return {
    value: 1,
    cancelScheduledValues: (t) => log.push([name, 'cancel', t]),
    setValueAtTime: (v, t) => log.push([name, 'set', v, t]),
    linearRampToValueAtTime: (v, t) => log.push([name, 'ramp', v, t]),
  };
}

function fakeContext() {
  const log = [];
  let gains = 0;
  const ctx = {
    log,
    state: 'suspended',
    currentTime: 5,
    destination: { name: 'destination' },
    sources: [],
    resume() {
      log.push(['resume']);
      ctx.state = 'running';
      return Promise.resolve();
    },
    suspend() {
      log.push(['suspend']);
      ctx.state = 'suspended';
      return Promise.resolve();
    },
    createGain() {
      gains += 1;
      const name = gains === 1 ? 'duck' : `fade${gains - 1}`;
      return { name, gain: fakeParam(log, name), connect: (to) => log.push([name, 'connect', to.name]), disconnect() {} };
    },
    createBuffer(channels, length, rate) {
      const data = Array.from({ length: channels }, () => new Float32Array(length));
      return { channels, length, rate, getChannelData: (c) => data[c] };
    },
    createBufferSource() {
      const source = {
        name: 'source',
        loop: false,
        stopped: null,
        connect: (to) => log.push(['source', 'connect', to.name]),
        disconnect() {},
        start: (t) => log.push(['source', 'start', t]),
        stop: (t) => {
          source.stopped = t;
          log.push(['source', 'stop', t]);
        },
      };
      ctx.sources.push(source);
      return source;
    },
  };
  return ctx;
}

const tinyRender = () => ({ sampleRate: 22050, channels: [new Float32Array(32), new Float32Array(32)] });

function makeBed({ enabled = true, hidden = false } = {}) {
  const ctx = fakeContext();
  let made = 0;
  const bed = new B.SoundBed({
    context: () => {
      made += 1;
      return ctx;
    },
    enabled: () => enabled,
    hidden: () => hidden,
    render: tinyRender,
  });
  return { bed, ctx, made: () => made };
}

test('no AudioContext before the gesture; the gesture resumes it and fades the bed in', () => {
  const { bed, ctx, made } = makeBed();
  bed.open('cafe');
  bed.setSpeaking(true);
  bed.setSpeaking(false);
  bed.setBed('market');
  assert.equal(made(), 0, 'opening, ducking and moving made no context');
  assert.equal(bed.snapshot().playing, null);

  assert.equal(bed.gesture(), true);
  assert.equal(made(), 1);
  assert.equal(ctx.state, 'running');
  assert.deepEqual(ctx.log[0], ['resume']);
  const source = ctx.sources[0];
  assert.equal(source.loop, true);
  assert.equal(bed.snapshot().playing, 'market');
  // source → fade → duck → speakers, and the fade rises from silence over FADE_IN_S.
  assert.ok(ctx.log.some((e) => e[0] === 'duck' && e[1] === 'connect' && e[2] === 'destination'));
  assert.ok(ctx.log.some((e) => e[0] === 'fade1' && e[1] === 'ramp' && e[2] === 1 && Math.abs(e[3] - (5 + B.FADE_IN_S)) < 1e-9));

  // A second gesture neither makes another context nor starts another loop.
  bed.gesture();
  assert.equal(made(), 1);
  assert.equal(ctx.sources.length, 1);
});

test('closed gates: no context, no sound', () => {
  for (const opts of [{ enabled: false }, { hidden: true }]) {
    const { bed, made } = makeBed(opts);
    bed.open('cafe');
    assert.equal(bed.gesture(), false);
    assert.equal(made(), 0);
  }
  // A gesture outside a scene does nothing either.
  const { bed, made } = makeBed();
  assert.equal(bed.gesture(), false);
  assert.equal(made(), 0);
});

test('a line ducks the bed 12 dB on the duck gain, and lets it back up', () => {
  const { bed, ctx } = makeBed();
  bed.open('cafe');
  bed.gesture();
  ctx.currentTime = 8;
  bed.setSpeaking(true);
  const down = ctx.log.filter((e) => e[0] === 'duck' && e[1] === 'ramp').pop();
  assert.ok(Math.abs(down[2] - B.dbToGain(-12)) < 1e-9);
  assert.ok(Math.abs(down[3] - (8 + B.DUCK_ATTACK_S)) < 1e-9);
  assert.equal(bed.snapshot().duckTarget, B.dbToGain(-12));
  ctx.currentTime = 11;
  bed.setSpeaking(false);
  const up = ctx.log.filter((e) => e[0] === 'duck' && e[1] === 'ramp').pop();
  assert.equal(up[2], 1);
  assert.ok(Math.abs(up[3] - (11 + B.DUCK_RELEASE_S)) < 1e-9);
});

test('a line already playing when the bed starts: the bed starts ducked', () => {
  const { bed, ctx } = makeBed();
  bed.open('metro');
  bed.setSpeaking(true);
  bed.gesture();
  const first = ctx.log.find((e) => e[0] === 'duck' && e[1] === 'set');
  assert.ok(Math.abs(first[2] - B.dbToGain(-12)) < 1e-9);
});

test('closing fades out and stops; hiding the page stops at once and suspends', () => {
  const { bed, ctx } = makeBed();
  bed.open('cafe');
  bed.gesture();
  ctx.currentTime = 20;
  bed.close();
  assert.ok(Math.abs(ctx.sources[0].stopped - (20 + B.FADE_OUT_S + 0.05)) < 1e-9);
  assert.equal(bed.snapshot().open, false);
  assert.equal(bed.gesture(), false, 'a closed scene does not restart on a tap');

  bed.open('room');
  bed.gesture();
  ctx.currentTime = 30;
  bed.hide();
  assert.ok(Math.abs(ctx.sources[1].stopped - (30 + B.HIDE_FADE_S + 0.05)) < 1e-9);
  assert.equal(ctx.state, 'suspended');
  assert.equal(bed.snapshot().playing, null);
});

test('moving to another place cross-fades to its bed', () => {
  const { bed, ctx } = makeBed();
  bed.open('cafe');
  bed.gesture();
  bed.setBed('metro');
  assert.equal(ctx.sources.length, 2);
  assert.ok(ctx.sources[0].stopped !== null);
  assert.equal(bed.snapshot().playing, 'metro');
});

test('the shared bed creates no context on its own, and sound.ts shares one context', () => {
  B.resetSoundBedForTests();
  let constructed = 0;
  global.window = {
    AudioContext: function Fake() {
      constructed += 1;
      return fakeContext();
    },
    localStorage: { getItem: () => 'on', setItem() {} },
  };
  global.document = { visibilityState: 'visible' };
  try {
    const sound = require('./sound.ts');
    sound.resetSoundContextForTests();
    const shared = B.soundBed();
    shared.open('cafe');
    shared.setSpeaking(true);
    assert.equal(constructed, 0);
    assert.equal(sound.existingAudioContext(), null);
    shared.gesture();
    assert.equal(constructed, 1);
    assert.equal(sound.existingAudioContext(), sound.sharedAudioContext());
    assert.equal(constructed, 1, 'the feel sounds reuse the same context');
    shared.close();
  } finally {
    delete global.window;
    delete global.document;
    B.resetSoundBedForTests();
  }
});
