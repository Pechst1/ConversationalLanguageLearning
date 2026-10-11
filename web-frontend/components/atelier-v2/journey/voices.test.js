// node --test components/atelier-v2/journey/voices.test.js
//
// WP-91 «Les voix» — every character has a voice.
//
//   1. the line-audio resolver: `disabled` → the device voice (and the server
//      is not asked again), a second play is a cache hit (no request, no
//      fetch), a failure is not remembered, every URL is released;
//   2. the device voice: fr-FR first, the same voice per character;
//   3. the autoplay rule: on, typed in, and never twice for the same line;
//   4. the setting: stored like «Sons», on in the app, off on the web;
//   5. the dictation model and its field (no autocorrect, no second primary);
//   6. every new string in the three languages;
//   7. the rendered faces: the thread's and the Courrier's portraits are buttons.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

// The transport is injected everywhere it matters; the real client stays out.
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const lineAudio = require('./line-audio.ts');
const autoplay = require('./voice-autoplay.ts');
const dictation = require('./dictation-model.ts');
const formats = require('./practice-formats.ts');
const { journeyCopy } = require('./journey-copy.ts');
const { listenLabel } = require('./useStepVoice.ts');
const { Dictation } = require('./Dictation.tsx');
const { RespondThread } = require('./RespondThread.tsx');
const preference = require('../../../lib/voice-preference.ts');
const { settingsCopy } = require('../../../lib/settings-copy.ts');

const h = React.createElement;

function fakeUrls() {
  let n = 0;
  const live = new Set();
  return {
    live,
    urls: {
      create: () => {
        n += 1;
        const url = `blob:clip-${n}`;
        live.add(url);
        return url;
      },
      revoke: (url) => live.delete(url),
    },
  };
}

function fakeTransport(answer) {
  const calls = { request: 0, fetch: 0 };
  return {
    calls,
    transport: {
      request: async (body) => {
        calls.request += 1;
        return typeof answer === 'function' ? answer(body, calls) : answer;
      },
      fetchClip: async (clipId) => {
        calls.fetch += 1;
        return { clipId };
      },
    },
  };
}

const READY = { status: 'ready', clip_id: 'clip-1', content_type: 'audio/mpeg', voice: 'nova', cached: false };
const LINE = { key: 'c1r', text_fr: 'Un café, bien sûr.', character_id: 'margaux_barman' };

// ---------------------------------------------------------------------------
// 1. the resolver
// ---------------------------------------------------------------------------

test('disabled → null (the device voice), and the server is not asked again', async () => {
  const cache = lineAudio.createLineAudioCache();
  const { calls, transport } = fakeTransport({ status: 'disabled' });
  const { urls } = fakeUrls();
  const resolve = lineAudio.createLineAudioResolver(transport, { cache, urls });
  assert.equal(await resolve(LINE), null);
  assert.equal(await resolve({ ...LINE, text_fr: 'Autre chose ?' }), null);
  assert.equal(calls.request, 1, 'one request, then the session remembers «disabled»');
  assert.equal(calls.fetch, 0);
});

test('a second play is a cache hit: no request, no fetch, a fresh URL released after use', async () => {
  const cache = lineAudio.createLineAudioCache();
  const { calls, transport } = fakeTransport(READY);
  const { urls, live } = fakeUrls();
  const resolve = lineAudio.createLineAudioResolver(transport, { cache, urls });
  const first = await resolve(LINE);
  assert.equal(typeof first.url, 'string');
  first.release();
  first.release(); // idempotent
  assert.equal(live.size, 0, 'the URL is revoked once the line is said');
  const second = await resolve({ ...LINE, key: 'another-surface' });
  assert.equal(calls.request, 1, 'the same character and text: no second request');
  assert.equal(calls.fetch, 1, 'and no second download');
  assert.notEqual(second.url, first.url);
  second.release();
  assert.equal(live.size, 0);
});

test('concurrent asks for one line share one request; another voice is another clip', async () => {
  const cache = lineAudio.createLineAudioCache();
  const { calls, transport } = fakeTransport(READY);
  const { urls } = fakeUrls();
  const resolve = lineAudio.createLineAudioResolver(transport, { cache, urls });
  const [a, b] = await Promise.all([resolve(LINE), resolve(LINE)]);
  assert.ok(a && b);
  assert.equal(calls.request, 1);
  await resolve({ ...LINE, character_id: 'marin_leveque' });
  assert.equal(calls.request, 2, 'the same words in Marin’s voice are Marin’s clip');
});

test('an error or a 404 → null, and is not remembered (the next tap asks again)', async () => {
  const cache = lineAudio.createLineAudioCache();
  const { calls, transport } = fakeTransport((_body, seen) => {
    if (seen.request === 1) {
      const error = new Error('Not Found');
      error.response = { status: 404 };
      throw error;
    }
    return READY;
  });
  const { urls } = fakeUrls();
  const resolve = lineAudio.createLineAudioResolver(transport, { cache, urls });
  assert.equal(await resolve(LINE), null);
  assert.equal(cache.disabled, false, 'a 404 is not «the server speaks nothing»');
  const again = await resolve(LINE);
  assert.ok(again && again.url);
  assert.equal(calls.request, 2);
});

test('an empty line asks nothing; the cache is bounded', async () => {
  const cache = lineAudio.createLineAudioCache();
  const { calls, transport } = fakeTransport(READY);
  const { urls } = fakeUrls();
  const resolve = lineAudio.createLineAudioResolver(transport, { cache, urls });
  assert.equal(await resolve({ ...LINE, text_fr: '   ' }), null);
  assert.equal(calls.request, 0);
  for (let i = 0; i < lineAudio.LINE_AUDIO_CACHE_LIMIT + 5; i += 1) {
    await resolve({ ...LINE, text_fr: `Ligne ${i}` });
  }
  assert.equal(cache.blobs.size, lineAudio.LINE_AUDIO_CACHE_LIMIT);
});

test('recall clips: the id is read from the authenticated path, and fetched once', async () => {
  assert.equal(lineAudio.recallClipId('/api/v1/daily-journeys/line-audio/abc123'), 'abc123');
  assert.equal(lineAudio.recallClipId('https://x.test/api/v1/daily-journeys/line-audio/a%20b?x=1'), 'a b');
  assert.equal(lineAudio.recallClipId('/media/clip.mp3'), null);
  assert.equal(lineAudio.recallClipId(null), null);
  let fetches = 0;
  const load = lineAudio.createClipLoader(async (id) => {
    fetches += 1;
    return { id };
  });
  await load('abc');
  await load('abc');
  assert.equal(fetches, 1, 'a replay costs nothing');
  const failing = lineAudio.createClipLoader(async () => {
    throw new Error('offline');
  });
  assert.equal(await failing('x'), null);
});

// ---------------------------------------------------------------------------
// 2. the device voice
// ---------------------------------------------------------------------------

test('the device voice: fr-FR first, the same one per character, none without French', () => {
  const voices = [
    { name: 'Samantha', lang: 'en-US', default: true },
    { name: 'Amélie', lang: 'fr-CA' },
    { name: 'Thomas', lang: 'fr-FR' },
    { name: 'Audrey', lang: 'fr_FR' },
  ];
  const picked = lineAudio.pickFrenchVoice(voices, null);
  assert.ok(['Thomas', 'Audrey'].includes(picked.name), 'a France voice before Canada');
  const margaux = lineAudio.pickFrenchVoice(voices, 'margaux_barman');
  assert.equal(lineAudio.pickFrenchVoice(voices, 'margaux_barman').name, margaux.name, 'stable per character');
  assert.equal(lineAudio.pickFrenchVoice([{ name: 'Amélie', lang: 'fr-CA' }], 'x').name, 'Amélie');
  assert.equal(lineAudio.pickFrenchVoice([{ name: 'Samantha', lang: 'en-US' }], 'x'), null);
  assert.ok(lineAudio.speechSafetyMs('Un café, bien sûr.') > 2500);
});

// ---------------------------------------------------------------------------
// 3. autoplay once
// ---------------------------------------------------------------------------

test('autoplay: only when on, only once typed in, never twice for the same line', () => {
  const ledger = autoplay.createAutoplayLedger();
  const key = autoplay.autoplayKey('step-3', 'c1r', 'Un café, bien sûr.');
  assert.equal(autoplay.shouldAutoplay({ enabled: false, ready: true, key, ledger }), false);
  assert.equal(ledger.has(key), false, 'a line not played while off is not spent');
  assert.equal(autoplay.shouldAutoplay({ enabled: true, ready: false, key, ledger }), false);
  assert.equal(autoplay.shouldAutoplay({ enabled: true, ready: true, key, ledger }), true);
  assert.equal(autoplay.shouldAutoplay({ enabled: true, ready: true, key, ledger }), false, 'never twice');
  const nextStep = autoplay.autoplayKey('step-4', 'c1r', 'Un café, bien sûr.');
  assert.equal(autoplay.shouldAutoplay({ enabled: true, ready: true, key: nextStep, ledger }), true);
  assert.equal(autoplay.shouldAutoplay({ enabled: true, ready: true, key: null, ledger }), false);

  assert.equal(autoplay.replyFinishedTyping('Un café, bien sûr.', 'Un café,'), false);
  assert.equal(autoplay.replyFinishedTyping('Un café, bien sûr.', 'Un café, bien sûr.'), true);
  assert.equal(autoplay.replyFinishedTyping('  ', '  '), false);
});

// ---------------------------------------------------------------------------
// 4. the setting
// ---------------------------------------------------------------------------

test('«Les personnages parlent à voix haute»: on in the app, off on the web, stored like «Sons»', () => {
  assert.equal(preference.defaultVoicesAloud(true), true);
  assert.equal(preference.defaultVoicesAloud(false), false);
  const store = new Map();
  const previous = global.window;
  global.window = {
    localStorage: {
      getItem: (key) => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, String(value)),
    },
  };
  try {
    assert.equal(preference.readVoicesPreference(), null);
    preference.setVoicesAloud(true);
    assert.equal(store.get(preference.VOICES_PREFERENCE_KEY), 'on');
    assert.equal(preference.voicesAloud(), true);
    preference.setVoicesAloud(false);
    assert.equal(store.get('atelier.voices'), 'off');
    assert.equal(preference.voicesAloud(), false);
  } finally {
    global.window = previous;
  }
});

// ---------------------------------------------------------------------------
// 5. dictation and listen_tap
// ---------------------------------------------------------------------------

test('the heard source: the journey clip, a public file, or nothing', () => {
  assert.deepEqual(dictation.heardSource('/api/v1/daily-journeys/line-audio/k1'), { kind: 'clip', clipId: 'k1' });
  assert.deepEqual(dictation.heardSource('/media/clip.mp3'), { kind: 'url', url: '/media/clip.mp3' });
  assert.deepEqual(dictation.heardSource('/api/v1/story-engine/episodes/s/audio/c'), { kind: 'none' });
  assert.deepEqual(dictation.heardSource(null), { kind: 'none' });
  assert.equal(formats.listenTapHasAudio({ task_type: 'listen_tap', audio_url: '/api/v1/daily-journeys/line-audio/k1' }), true);
  assert.equal(formats.listenTapHasAudio({ task_type: 'listen_tap', audio_url: null }), false);
});

test('the play button: idle → loading → playing → played, a failure can be retried', () => {
  let state = 'idle';
  for (const [event, expected] of [
    ['play', 'loading'],
    ['loaded', 'playing'],
    ['ended', 'played'],
    ['play', 'loading'],
    ['failed', 'unavailable'],
    ['play', 'loading'],
    ['loaded', 'playing'],
    ['stop', 'played'],
  ]) {
    state = dictation.heardNext(state, event);
    assert.equal(state, expected, `${event} → ${expected}`);
  }
  const en = journeyCopy('en');
  assert.equal(dictation.heardActionLabel('idle', en), en.dictation_play);
  assert.equal(dictation.heardActionLabel('played', en), en.dictation_replay);
  assert.equal(dictation.heardActionLabel('playing', en), en.dictation_stop);
  assert.equal(dictation.heardActionLabel('loading', en), en.dictation_loading);
});

test('listen_tap reads again when the clip fails; dictation needs something typed', () => {
  const heard = { task_type: 'listen_tap', audio_url: '/api/v1/daily-journeys/line-audio/k1' };
  assert.equal(dictation.listenTapShowsPhrase(heard, { clipFailed: false, graded: false }), false);
  assert.equal(dictation.listenTapShowsPhrase(heard, { clipFailed: true, graded: false }), true);
  assert.equal(dictation.listenTapShowsPhrase(heard, { clipFailed: false, graded: true }), true);
  assert.equal(dictation.listenTapShowsPhrase({ ...heard, audio_url: null }, { clipFailed: false, graded: false }), true);
  assert.equal(dictation.isDictation({ task_type: 'dictation' }), true);
  assert.equal(dictation.promptIsHeard({ task_type: 'dictation', audio_url: heard.audio_url }), true);
  assert.equal(dictation.dictationReady('  '), false);
  assert.equal(dictation.dictationReady(' je voudrais '), true);
});

test('the dictation field: French, no autocorrect, no capitals, no spell-check, no second primary', () => {
  const html = renderToStaticMarkup(
    h(Dictation, {
      prompt: { audio_url: '/api/v1/daily-journeys/line-audio/k1', instruction_native: 'Write what you hear.' },
      copy: journeyCopy('de'),
      value: '',
      onChange: () => {},
    }),
  );
  assert.ok(html.includes('autoCorrect="off"') || html.includes('autocorrect="off"'));
  assert.ok(html.includes('autoCapitalize="off"') || html.includes('autocapitalize="off"'));
  assert.ok(html.includes('spellCheck="false"') || html.includes('spellcheck="false"'));
  assert.ok(html.includes('lang="fr"'));
  assert.ok(html.includes(`aria-label="${journeyCopy('de').dictation_play}"`), 'the play button speaks German');
  assert.ok(html.includes(journeyCopy('de').dictation_label));
  assert.ok(!html.includes('av2-action--primary'), 'the step keeps its one primary');
  assert.ok(!html.includes('<audio'), 'the clip is fetched with the session, never an <audio src>');
});

// ---------------------------------------------------------------------------
// 6. copy
// ---------------------------------------------------------------------------

const VOICE_KEYS = [
  'voice_listen_to',
  'voice_listen_line',
  'word_listen',
  'dictation_play',
  'dictation_replay',
  'dictation_stop',
  'dictation_loading',
  'dictation_unavailable',
  'dictation_label',
  'dictation_placeholder',
  'listen_unavailable_read',
];

test('every new string exists, and differs, in English, German and French', () => {
  for (const key of VOICE_KEYS) {
    const values = ['en', 'de', 'fr'].map((language) => journeyCopy(language)[key]);
    for (const value of values) assert.ok(typeof value === 'string' && value.trim(), `${key} is empty`);
    assert.equal(new Set(values).size, 3, `${key} is not translated`);
  }
  for (const language of ['en', 'de', 'fr']) {
    assert.ok(journeyCopy(language).voice_listen_to.includes('{name}'));
    const settings = settingsCopy(language);
    assert.ok(settings.row_voices_aloud.trim() && settings.row_voices_aloud_hint.trim());
  }
  assert.equal(settingsCopy('fr').row_voices_aloud, 'Les personnages parlent à voix haute');
  assert.equal(listenLabel(journeyCopy('fr'), 'Margaux'), 'Écouter Margaux');
  assert.equal(listenLabel(journeyCopy('de'), ''), journeyCopy('de').voice_listen_line);
});

// ---------------------------------------------------------------------------
// 7. the faces are play buttons
// ---------------------------------------------------------------------------

test('in the thread every character face is a play button, labelled in the learner’s language', () => {
  const copy = journeyCopy('en');
  const html = renderToStaticMarkup(
    h(RespondThread, {
      bubbles: [
        { kind: 'character', key: 'c0o', turn: 0, text: 'Bonjour ! Je vous sers quoi ?', reply: false, latest: false },
        { kind: 'learner', key: 'l0', turn: 0, text: 'Un café, s’il vous plaît.', correction: null, pending: false },
        { kind: 'character', key: 'c0r', turn: 0, text: 'Tout de suite.', reply: true, latest: true },
      ],
      speaker: { id: 'margaux_barman', name: 'Margaux' },
      mood: 'neutral',
      copy,
      typingKey: null,
      typedText: '',
      waiting: false,
      openNote: null,
      onToggleNote: () => {},
      journeyId: 'j1',
      stepId: 's3',
    }),
  );
  const faces = html.match(/class="av2-speaking-portrait"/g) || [];
  assert.equal(faces.length, 2, 'both character lines, and not the learner’s');
  assert.ok(html.includes('aria-label="Listen to Margaux"'));
  assert.ok(html.includes('data-size="xs"') && html.includes('data-size="md"'));
});

test('in the Courrier the sender’s face reads the letter; without French it stays a face', () => {
  const Cr = require('../../courrier/Courrier.tsx');
  const { AtelierV2Root } = require('../ui/AtelierV2Root.tsx');
  const withLetter = renderToStaticMarkup(
    h(AtelierV2Root, { language: 'de' },
      h(Cr.CrDesk, { name: 'Margaux', letterFr: 'Chère voisine, le chauffage est en panne.', senderId: 'margaux_barman' }),
    ),
  );
  assert.ok(withLetter.includes('class="av2-speaking-portrait"'));
  assert.ok(withLetter.includes('aria-label="Margaux anhören"'), 'labelled in the learner’s language');
  const without = renderToStaticMarkup(
    h(AtelierV2Root, { language: 'de' }, h(Cr.CrDesk, { name: 'Margaux' })),
  );
  assert.ok(!without.includes('av2-speaking-portrait'));
});
