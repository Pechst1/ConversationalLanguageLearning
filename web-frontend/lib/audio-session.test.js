// node --test lib/audio-session.test.js
//
// 2026-11-04 (Vincent): La Forge's «Anhören» played no word. The first feel
// sound set `navigator.audioSession.type = 'ambient'` for the whole page, and
// WebKit applies that type as an override to every `<audio>` and browser voice
// too: with the iPhone on silent, a sentence the learner tapped to hear was
// muted. A voice the learner asks for now holds `playback` while it sounds;
// the chimes keep their `ambient` rest.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test, beforeEach } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

// An iPhone's page: the Audio Session API, Web Audio, «Sons» on, sounds fetchable.
const session = { type: 'auto', history: [] };
const audioSession = {
  get type() { return session.type; },
  set type(value) { session.type = value; session.history.push(value); },
};
Object.defineProperty(globalThis, 'navigator', { value: { audioSession }, configurable: true, writable: true });
const storage = new Map([['atelier.sounds', 'on']]);
class FakeContext {
  constructor() { this.state = 'running'; this.destination = {}; }
  resume() { return Promise.resolve(); }
  decodeAudioData(_bytes, ok) { ok({}); }
  createBufferSource() { return { connect() {}, start() {} }; }
}
const spoken = [];
globalThis.window = {
  localStorage: { getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v) },
  AudioContext: FakeContext,
  speechSynthesis: { cancel() {}, speak(u) { spoken.push({ text: u.text, type: session.type, u }); } },
};
globalThis.document = { visibilityState: 'visible' };
globalThis.fetch = async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) });

const sound = require(path.join(WEB_ROOT, 'lib/sound.ts'));
const voice = require(path.join(WEB_ROOT, 'lib/audio-session.ts'));

/** An `<audio>` stand-in: records the session type at `play()`, fires its events on demand. */
function fakePlayer({ refuse = false } = {}) {
  const listeners = {};
  return {
    typeAtPlay: null,
    addEventListener(name, fn) { (listeners[name] ||= []).push(fn); },
    fire(name) { for (const fn of listeners[name] || []) fn(); listeners[name] = []; },
    play() {
      this.typeAtPlay = session.type;
      return refuse ? Promise.reject(new Error('NotAllowedError')) : Promise.resolve();
    },
  };
}

beforeEach(() => {
  voice.resetAudioSessionForTests();
  // The device's type between tests; the page's resting type (once a chime set it) stays.
  session.type = 'auto';
  session.history = [];
  spoken.length = 0;
});

// First, before any chime: the page has no resting type of its own yet.
test('without a chime first, an asked voice gives back the platform’s own type', async () => {
  const player = fakePlayer();
  await voice.playAskedVoice(player);
  assert.equal(player.typeAtPlay, 'playback');
  player.fire('ended');
  assert.equal(session.type, 'auto');
});

test('a chime rests the page at ambient, so the ringer switch silences it', () => {
  sound.playFeelSound('correct');
  assert.equal(session.type, 'ambient');
});

test('after a chime, a dictation tapped to hear plays at playback, then the page rests again', async () => {
  sound.playFeelSound('correct');
  const player = fakePlayer();
  await voice.playAskedVoice(player);
  assert.equal(player.typeAtPlay, 'playback', 'an ambient session mutes «Anhören» on a silent iPhone');
  player.fire('ended');
  assert.equal(session.type, 'ambient');
});

test('a chime during an asked voice does not take the session from it', async () => {
  const player = fakePlayer();
  await voice.playAskedVoice(player);
  sound.playFeelSound('wrong');
  assert.equal(session.type, 'playback');
  player.fire('pause');
  assert.equal(session.type, 'ambient');
});

test('two asked voices: the session rests only when both are done; a release counts once', async () => {
  sound.playFeelSound('correct');
  const a = fakePlayer();
  const b = fakePlayer();
  await voice.playAskedVoice(a);
  await voice.playAskedVoice(b);
  a.fire('pause');
  a.fire('ended');
  a.fire('error');
  assert.equal(session.type, 'playback');
  b.fire('ended');
  assert.equal(session.type, 'ambient');
});

test('a refused play gives the session back and still rejects, so the caller can read aloud instead', async () => {
  sound.playFeelSound('correct');
  await assert.rejects(voice.playAskedVoice(fakePlayer({ refuse: true })));
  assert.equal(session.type, 'ambient');
});

test('the browser voice, asked for, speaks at playback and rests after', () => {
  sound.playFeelSound('correct');
  let ended = false;
  const utterance = { text: 'Hier, il est venu.', onend: () => { ended = true; }, onerror: null };
  assert.equal(voice.speakAskedVoice(utterance), true);
  assert.equal(spoken[0].type, 'playback');
  spoken[0].u.onend({});
  assert.equal(ended, true, 'the caller’s own end handler still runs');
  assert.equal(session.type, 'ambient');
});

// Every button that speaks a sentence on a tap goes through the asked session:
// La Forge's dictation and model answer, the rule card, the word review.
const ASKED = {
  'components/epreuve/ForgeDrills.tsx': ['playAskedVoice(player)', 'speakAskedVoice(utterance)'],
  'pages/atelier.tsx': ['playAskedVoice(player)', 'speakAskedVoice(utterance)'],
  'components/atelier-v2/rule/RuleCard.tsx': ['playAskedVoice(audio)'],
  'pages/vocabulary/review.tsx': ['playAskedVoice(player)', 'speakAskedVoice(utterance)'],
};
for (const [file, calls] of Object.entries(ASKED)) {
  test(`${file}: a tapped voice plays through the ringer switch`, () => {
    const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
    for (const call of calls) assert.ok(source.includes(call), `${file} should call ${call}`);
    assert.doesNotMatch(source, /speechSynthesis\.speak\(/, `${file}: a bare browser voice stays ambient`);
    assert.doesNotMatch(source, /\b(player|audio)\.play\(\)/, `${file}: a bare play() stays ambient`);
  });
}
