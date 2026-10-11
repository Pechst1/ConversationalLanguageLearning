// node --test lib/forge-combo.test.js
//
// WP-S7 — La Forge's combo and its soft sound.
//   1. only checked verdicts count: unchecked / provisional answers neither
//      extend nor break the run; a checked error resets it;
//   2. the server's run wins over the page's own count;
//   3. five tokens light from the left; the feel is a tap, then the combo's
//      double tap and tone from the second link;
//   4. the combo tone is on by default and respects the Réglages toggle.

const assert = require('node:assert/strict');
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

const C = require('./forge-combo.ts');

const right = { verdict: 'correct', errata: [], assessment_status: 'checked', ai_review: { status: 'not_applicable' } };
const wrong = { verdict: 'incorrect', errata: [{ task_error_type: 'agreement' }], assessment_status: 'checked' };
const unchecked = { verdict: 'needs_review', errata: [], assessment_status: 'unavailable', ai_review: { status: 'failed' } };
const provisional = { verdict: 'accepted', errata: [], assessment_status: 'provisional', ai_review: { status: 'pending' } };
const provisionalMiss = { ...provisional, verdict: 'partial', errata: [{ task_error_type: 'agreement' }] };

test('unchecked and provisional answers neither extend nor break the combo', () => {
  assert.deepEqual(C.comboFromCorrections([right, unchecked, right, provisional, right]), { run: 3, best: 3 });
  assert.deepEqual(C.comboFromCorrections([right, right, provisionalMiss]), { run: 2, best: 2 });
  assert.deepEqual(C.comboFromCorrections([unchecked, provisional]), { run: 0, best: 0 });
});

test('only a checked error resets the combo, and the best run is kept', () => {
  assert.deepEqual(C.comboFromCorrections([right, right, right, wrong, right]), { run: 1, best: 3 });
  assert.deepEqual(C.comboFromCorrections([wrong]), { run: 0, best: 0 });
  // A task-compliance note alone is not an error.
  const note = { verdict: 'accepted', errata: [{ task_error_type: 'task_compliance' }], assessment_status: 'checked' };
  assert.deepEqual(C.comboFromCorrections([right, note]), { run: 2, best: 2 });
});

test("the server's run wins; the page counts only for an older server", () => {
  assert.deepEqual(C.comboOf({ combo: { run: 4, best: 6 } }, [wrong]), { run: 4, best: 6 });
  assert.deepEqual(C.comboOf({ combo: { run: 0, best: 0 } }, [right, right]), { run: 0, best: 0 });
  assert.deepEqual(C.comboOf(null, [right, unchecked, right]), { run: 2, best: 2 });
  assert.equal(C.comboEnabled({ features: { combo: false } }), false);
  assert.equal(C.comboEnabled({ features: {} }), true);
  assert.equal(C.comboEnabled(null), true);
});

test('five tokens light from the left; the combo is felt from its second link', () => {
  assert.deepEqual(C.comboTokens(0), [false, false, false, false, false]);
  assert.deepEqual(C.comboTokens(3), [true, true, true, false, false]);
  assert.deepEqual(C.comboTokens(9), [true, true, true, true, true]);
  assert.equal(C.comboStep(2, 3), 'extend');
  assert.equal(C.comboStep(3, 0), 'reset');
  assert.equal(C.comboStep(0, 0), 'hold');
  assert.deepEqual(C.comboFeel('extend', 1), { haptic: 'correct', tone: false });
  assert.deepEqual(C.comboFeel('extend', 2), { haptic: 'token', tone: true });
  assert.deepEqual(C.comboFeel('reset', 0), { haptic: null, tone: false });
  assert.deepEqual(C.comboFeel('hold', 4), { haptic: null, tone: false });
});

// ---------------------------------------------------------------------------
// The sound
// ---------------------------------------------------------------------------

function fakeBrowser(stored) {
  const store = new Map(stored == null ? [] : [['atelier.sounds', stored]]);
  const made = { contexts: 0, oscillators: 0, frequencies: [] };
  class FakeContext {
    constructor() {
      made.contexts += 1;
      this.state = 'running';
      this.currentTime = 0;
      this.destination = {};
    }
    createOscillator() {
      made.oscillators += 1;
      return {
        type: '',
        frequency: { setValueAtTime: (value) => made.frequencies.push(value) },
        connect() {},
        start() {},
        stop() {},
      };
    }
    createGain() {
      return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} };
    }
  }
  global.window = {
    localStorage: { getItem: (key) => (store.has(key) ? store.get(key) : null), setItem: (key, value) => store.set(key, value) },
    AudioContext: FakeContext,
  };
  global.document = { visibilityState: 'visible' };
  return made;
}

function freshSound() {
  const S = require('./sound.ts');
  S.resetSoundContextForTests();
  return S;
}

test('the combo tone is on by default — on the web too — and plays a soft sine', () => {
  const made = fakeBrowser(null);
  const S = freshSound();
  assert.equal(S.soundsEnabled(), false, 'the three feel sounds stay off on the web');
  assert.equal(S.comboSoundEnabled(), true, 'owner decision 4: the combo sound is on by default');
  assert.equal(S.playComboTone(3), true);
  assert.equal(made.oscillators, 1);
  assert.equal(made.frequencies[0], S.comboToneFrequency(3));
  assert.ok(S.COMBO_TONE_GAIN <= 0.1, 'quiet');
  assert.ok(S.comboToneFrequency(20) >= S.comboToneFrequency(2), 'rises with the run, held at the top');
});

test('the combo tone respects the Réglages toggle', () => {
  let made = fakeBrowser('off');
  let S = freshSound();
  assert.equal(S.comboSoundEnabled(), false);
  assert.equal(S.playComboTone(4), false);
  assert.equal(made.contexts, 0, 'no audio context is even created');
  assert.equal(made.oscillators, 0);

  made = fakeBrowser('on');
  S = freshSound();
  assert.equal(S.comboSoundEnabled(), true);
  assert.equal(S.playComboTone(2), true);
  assert.equal(made.oscillators, 1);

  // Switching sounds off in Réglages silences the next link at once.
  S.setSoundsEnabled(false);
  assert.equal(S.playComboTone(3), false);
  assert.equal(made.oscillators, 1);
});

test('a hidden page stays quiet', () => {
  const made = fakeBrowser(null);
  global.document = { visibilityState: 'hidden' };
  const S = freshSound();
  assert.equal(S.playComboTone(5), false);
  assert.equal(made.oscillators, 0);
  delete global.window;
  delete global.document;
});
