// WP-80 — «A reason to come back tomorrow», the device half.
//
// Pins when the push pre-prompt is offered (after a finished day, once, only
// where a push can arrive and the OS has not been asked), what it says (one
// language per card, a character's name, no emoji), that the old post-séance
// OS prompt is gone, that native push is on by default in the native build,
// and the «Reprise en douceur» label after an absence.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const {
  LEGACY_NATIVE_PROMPT_KEY,
  PUSH_OPT_IN_STORAGE_KEY,
  normalizePermission,
  pushOptInCopy,
  readOptInAnswer,
  rememberOptInAnswer,
  shouldOfferPushOptIn,
} = require('./push-opt-in.ts');
const { GENTLE_RETURN_LABEL, gentleReturnLabel } = require('./gentle-return.ts');

const WEB_ROOT = path.resolve(__dirname, '..');
const read = (...parts) => fs.readFileSync(path.join(WEB_ROOT, ...parts), 'utf8');

function memoryStorage(initial = {}) {
  const values = { ...initial };
  return {
    getItem: (key) => (key in values ? values[key] : null),
    setItem: (key, value) => {
      values[key] = String(value);
    },
    values,
  };
}

const offer = (overrides = {}) => shouldOfferPushOptIn({
  dayFinished: true,
  capability: 'native',
  permission: 'prompt',
  answered: null,
  ...overrides,
});

test('the pre-prompt is offered after a finished day, and only then', () => {
  assert.equal(offer(), true);
  assert.equal(offer({ dayFinished: false }), false, 'never mid-scene or before the first day');
  assert.equal(offer({ capability: 'web' }), true);
  assert.equal(offer({ capability: 'none' }), false, 'no push in this build: nothing to ask');
  assert.equal(offer({ permission: 'granted' }), false);
  assert.equal(offer({ permission: 'denied' }), false);
  assert.equal(offer({ permission: 'unknown' }), false);
});

test('once answered — yes or later — it is never offered again', () => {
  const storage = memoryStorage();
  assert.equal(readOptInAnswer(storage), null);
  assert.equal(offer({ answered: readOptInAnswer(storage) }), true, 'first finished day');

  rememberOptInAnswer(storage, 'later');
  assert.equal(storage.values[PUSH_OPT_IN_STORAGE_KEY], 'later');
  assert.equal(offer({ answered: readOptInAnswer(storage) }), false, 'second finished day');

  const yes = memoryStorage();
  rememberOptInAnswer(yes, 'yes');
  assert.equal(offer({ answered: readOptInAnswer(yes) }), false);

  // A device the pre-WP-80 séance prompt already asked counts as answered.
  assert.equal(readOptInAnswer(memoryStorage({ [LEGACY_NATIVE_PROMPT_KEY]: 'true' })), 'yes');
  // Blocked storage behaves as "not answered" and never throws.
  const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
  assert.equal(readOptInAnswer(broken), null);
  assert.doesNotThrow(() => rememberOptInAnswer(broken, 'yes'));
  assert.equal(readOptInAnswer(null), null);
});

test('Capacitor and browser permission states are normalised', () => {
  assert.equal(normalizePermission('prompt'), 'prompt');
  assert.equal(normalizePermission('prompt-with-rationale'), 'prompt');
  assert.equal(normalizePermission('default'), 'prompt');
  assert.equal(normalizePermission('granted'), 'granted');
  assert.equal(normalizePermission('denied'), 'denied');
  assert.equal(normalizePermission(undefined), 'unknown');
});

test('the copy is one card in the learner language, with a face and no emoji', () => {
  assert.deepEqual(pushOptInCopy('fr'), {
    line: 'Marin vous prévient quand la suite arrive.',
    yes: 'Oui',
    later: 'Plus tard',
    label: 'Notifications',
  });
  assert.equal(pushOptInCopy('en').line, 'Marin lets you know when the story continues.');
  assert.equal(pushOptInCopy('de').yes, 'Ja');
  assert.match(pushOptInCopy('de', 'Romy').line, /^Romy /);
  assert.equal(pushOptInCopy('xx').yes, 'Yes', 'unknown language falls back to English');
  const emoji = /[\u{1F300}-\u{1FAFF}☀-➿]/u;
  for (const language of ['en', 'de', 'fr']) {
    for (const value of Object.values(pushOptInCopy(language))) assert.doesNotMatch(value, emoji);
  }
});

test('the recap mounts the pre-prompt; the séance no longer asks the OS', () => {
  const session = read('components', 'atelier-v2', 'journey', 'JourneySession.tsx');
  const recap = session.slice(session.indexOf('export function JourneyRecapView'));
  assert.match(recap, /<PushOptIn[^>]*dayFinished/);
  assert.equal(session.indexOf('<PushOptIn'), session.indexOf('<PushOptIn', session.indexOf('export function JourneyRecapView')), 'only in the recap');

  const optIn = read('components', 'atelier-v2', 'journey', 'PushOptIn.tsx');
  // The OS dialog is behind «Oui» only.
  assert.match(optIn, /if \(value === 'yes'\) await enablePush/);

  const atelier = read('pages', 'atelier.tsx');
  assert.doesNotMatch(atelier, /registerNativePushToken/);
  assert.doesNotMatch(atelier, /pilot:native-push-prompted:v1/);
});

test('native push is on by default in the native build; web push needs VAPID', () => {
  const build = read('scripts', 'build-native.mjs');
  assert.match(build, /NEXT_PUBLIC_NATIVE_PUSH_ENABLED: process\.env\.NEXT_PUBLIC_NATIVE_PUSH_ENABLED === 'false' \? 'false' : 'true'/);
  const push = read('lib', 'push.ts');
  assert.match(push, /if \(!\(await vapidPublicKey\(\)\)\) return NONE;/);
});

test('an absence of two days or more labels the short day «Reprise en douceur»', () => {
  assert.equal(gentleReturnLabel({ missedDays: 0, dayShape: null, estimatedSeconds: null }), null);
  assert.equal(gentleReturnLabel({ missedDays: 1, dayShape: 'short', estimatedSeconds: 180 }), null);
  assert.equal(gentleReturnLabel({ missedDays: 2, dayShape: null, estimatedSeconds: null }), GENTLE_RETURN_LABEL);
  assert.equal(gentleReturnLabel({ missedDays: 3, dayShape: 'short', estimatedSeconds: 180 }), 'Reprise en douceur · 3 min');
  assert.equal(gentleReturnLabel({ missedDays: 5, dayShape: 'standard', estimatedSeconds: 300 }), null);
  assert.equal(gentleReturnLabel({ missedDays: undefined, dayShape: 'short', estimatedSeconds: 180 }), null);
});
