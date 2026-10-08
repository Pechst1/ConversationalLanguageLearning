// node --test components/atelier-v2/journey/episode-audio.test.js
//
// WP-32 «Écouter d'abord» — the listening-first episode.
//
// What is pinned here is the part of the package that decides whether it helps
// or merely plays a sound:
//
//   1. the four-stage cycle cannot be short-circuited — no listening without a
//      prediction, no verifying without having listened;
//   2. the two guesses and the verification are deterministic and derived from
//      the episode the server already sent, so nothing here costs a model call;
//   3. an episode whose lines settle nothing comes back `unresolved` rather
//      than being scored either way;
//   4. the clip keys this side derives are byte-identical to the ones
//      `app/services/episode_audio.py` derives, which is what lets a manifest
//      and a line list meet without an index negotiation;
//   5. **with the mode off the text path is untouched** — no manifest read, no
//      synthesis, no request of any kind.
//
// Pure modules and one server render. No network, no audio device.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

/** Every transport call the render makes, so "nothing was called" is provable. */
const apiCalls = [];
const apiStub = new Proxy(
  {},
  {
    get(_target, method) {
      if (method === 'then') return undefined;
      return (...args) => {
        apiCalls.push({ method: String(method), args });
        return Promise.resolve({ status: 'disabled', revision: '', clips: [], truncated: false, reason: '' });
      };
    },
  },
);
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: apiStub, apiService: apiStub },
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const model = require('./story-episode-model.ts');
const { journeyCopy } = require('./journey-copy.ts');
const { StoryEpisodeStep } = require('./StoryEpisodeStep.tsx');

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** An exchange the counterpart agrees to. */
const agreeing = {
  id: 'scene-1',
  scene_id: 'scene-1',
  serial_thread_id: 't',
  serial_episode_id: null,
  journey_id: 'j',
  title_fr: 'Au marché, samedi matin.',
  status: 'available',
  chapter: { id: 'c1', title_fr: 'Chapitre 1' },
  panel_index: 0,
  panels: [
    {
      id: 'p1',
      index: 0,
      narration_fr: 'Le marché est presque vide.',
      dialogue: [
        { character_id: 'toi', text_fr: 'Bonjour, vous avez des tomates ?' },
        { character_id: '', text_fr: '' },
        { character_id: 'marchand', character_name: 'Monsieur Marchand', text_fr: 'Bien sûr, elles sont d’aujourd’hui.' },
      ],
      image_url: null,
      image_status: 'unavailable',
    },
  ],
  resolution: null,
};

/** The same shape, refused. */
const refusing = {
  ...agreeing,
  id: 'scene-2',
  scene_id: 'scene-2',
  panels: [
    {
      id: 'p9',
      index: 0,
      narration_fr: 'Romy hésite.',
      dialogue: [
        { character_id: 'toi', text_fr: 'Tu viens samedi ?' },
        { character_id: 'romy', character_name: 'Romy', text_fr: 'Désolée, je travaille samedi.' },
      ],
      image_url: null,
      image_status: 'unavailable',
    },
  ],
};

/** An exchange whose words settle nothing either way. */
const openEnded = {
  ...agreeing,
  id: 'scene-3',
  scene_id: 'scene-3',
  panels: [
    {
      id: 'p7',
      index: 0,
      narration_fr: 'La porte se referme.',
      dialogue: [
        { character_id: 'toi', text_fr: 'Je repasse demain ?' },
        { character_id: 'lila', character_name: 'Lila', text_fr: 'On verra bien.' },
      ],
      image_url: null,
      image_status: 'unavailable',
    },
  ],
};

// ---------------------------------------------------------------------------
// Lines and keys
// ---------------------------------------------------------------------------

test('the spoken lines keep panel order and skip what has nothing to say', () => {
  const lines = model.episodeListenLines(agreeing);
  assert.deepEqual(
    lines.map((line) => line.key),
    ['p1:n', 'p1:l0', 'p1:l2'],
    'an empty dialogue entry is dropped without shifting the keys after it',
  );
  assert.equal(lines[0].characterId, model.NARRATOR_ID);
  assert.equal(lines[0].who, '', 'narration has no speaker name');
  assert.equal(lines[2].who, 'Monsieur Marchand');
});

test('the clip key format is the one the backend writes', () => {
  // `app/services/episode_audio.py`: `f"{panel.id}:n"` and `f"{panel.id}:l{index}"`
  // over the *raw* dialogue array. Both sides must derive the same string from
  // the same episode, or a manifest cannot be matched to a line.
  const keys = model.episodeListenLines(refusing).map((line) => line.key);
  assert.deepEqual(keys, ['p9:n', 'p9:l0', 'p9:l1']);
});

// ---------------------------------------------------------------------------
// Predict
// ---------------------------------------------------------------------------

test('the two guesses are deterministic, French, and name the counterpart', () => {
  const first = model.buildEpisodeGuesses(agreeing);
  const second = model.buildEpisodeGuesses(agreeing);
  assert.deepEqual(first, second, 'no randomness: the same episode gives the same guesses');
  assert.deepEqual(
    first.map((guess) => guess.id),
    ['accord', 'resistance'],
  );
  assert.ok(first[0].fr.startsWith('Monsieur Marchand'), first[0].fr);
  assert.ok(first[1].fr.includes('refuse'));
});

test('the counterpart is never the learner, and never invented', () => {
  assert.equal(model.episodeCounterpart(refusing), 'Romy');
  const learnerOnly = {
    ...agreeing,
    panels: [
      {
        id: 'p0',
        index: 0,
        narration_fr: '',
        dialogue: [{ character_id: 'toi', text_fr: 'Bonjour.' }],
        image_url: null,
        image_status: 'unavailable',
      },
    ],
  };
  assert.equal(model.episodeCounterpart(learnerOnly), '');
  const guesses = model.buildEpisodeGuesses(learnerOnly);
  assert.ok(
    guesses[0].fr.startsWith('La personne en face'),
    'with no named counterpart the guess is impersonal rather than a made-up name',
  );
});

// ---------------------------------------------------------------------------
// Verify
// ---------------------------------------------------------------------------

test('a guess is checked against the scene’s own words, and the line is quoted', () => {
  const held = model.verifyEpisodeGuess(agreeing, 'accord');
  assert.equal(held.supported, 'accord');
  assert.equal(held.verdict, 'confirmed');
  assert.equal(held.quoteFr, 'Bien sûr, elles sont d’aujourd’hui.');

  const missed = model.verifyEpisodeGuess(agreeing, 'resistance');
  assert.equal(missed.verdict, 'other');
  assert.equal(missed.supported, 'accord', 'what the scene supports does not depend on the guess');

  const refused = model.verifyEpisodeGuess(refusing, 'resistance');
  assert.equal(refused.supported, 'resistance');
  assert.equal(refused.verdict, 'confirmed');
  assert.equal(refused.quoteFr, 'Désolée, je travaille samedi.');
});

test('a scene that settles nothing is unresolved, not a miss', () => {
  const verdict = model.verifyEpisodeGuess(openEnded, 'accord');
  assert.equal(verdict.supported, null);
  assert.equal(verdict.verdict, 'unresolved');
  assert.equal(verdict.quoteFr, '');
});

test('a line that says both things at once decides nothing on its own', () => {
  const hedged = {
    ...agreeing,
    panels: [
      {
        id: 'p5',
        index: 0,
        narration_fr: '',
        dialogue: [
          { character_id: 'romy', character_name: 'Romy', text_fr: 'Oui, mais malheureusement je ne peux pas.' },
        ],
        image_url: null,
        image_status: 'unavailable',
      },
    ],
  };
  assert.equal(model.verifyEpisodeGuess(hedged, 'accord').verdict, 'unresolved');
});

test('the published resolution outranks the dialogue when the server has one', () => {
  const completed = {
    ...refusing,
    status: 'completed',
    resolution: { text_fr: 'Finalement, elle dit oui.', summary_native: 'She agreed.' },
  };
  const verdict = model.verifyEpisodeGuess(completed, 'accord');
  assert.equal(verdict.supported, 'accord');
  assert.equal(verdict.quoteFr, 'Finalement, elle dit oui.');
});

test('accents and typographic apostrophes fold to one spelling', () => {
  assert.equal(model.foldFrench('Désolée'), 'desolee');
  assert.equal(model.foldFrench('D’accord'), "d'accord");
});

// ---------------------------------------------------------------------------
// Retain
// ---------------------------------------------------------------------------

test('the phrase to keep comes from the episode, never from a rule', () => {
  assert.equal(model.episodeRetainPhrase(refusing), 'Désolée, je travaille samedi.');
  // No decisive line: the shortest full character line, which is the one a
  // learner has a chance of catching next time.
  assert.equal(model.episodeRetainPhrase(openEnded), 'On verra bien.');
  assert.equal(model.episodeRetainPhrase(null), '');
});

// ---------------------------------------------------------------------------
// The cycle
// ---------------------------------------------------------------------------

test('there is no listening without a prediction', () => {
  const start = model.RADIO_INITIAL;
  assert.equal(start.stage, 'predire');
  assert.equal(model.radioReduce(start, { type: 'listen' }).stage, 'predire');

  const guessed = model.radioReduce(start, { type: 'guess', id: 'accord' });
  assert.equal(guessed.guess, 'accord');
  assert.equal(model.radioReduce(guessed, { type: 'listen' }).stage, 'ecouter');
});

test('there is no verifying without having listened', () => {
  let state = model.radioReduce(model.RADIO_INITIAL, { type: 'guess', id: 'resistance' });
  state = model.radioReduce(state, { type: 'listen' });
  assert.equal(model.radioReduce(state, { type: 'verify' }).stage, 'ecouter');

  state = model.radioReduce(state, { type: 'heard' });
  assert.equal(state.heard, true);
  state = model.radioReduce(state, { type: 'verify' });
  assert.equal(state.stage, 'verifier');
});

test('the guess is fixed once the learner has moved past prédire', () => {
  let state = model.radioReduce(model.RADIO_INITIAL, { type: 'guess', id: 'accord' });
  state = model.radioReduce(state, { type: 'listen' });
  state = model.radioReduce(state, { type: 'guess', id: 'resistance' });
  assert.equal(state.guess, 'accord', 'a prediction cannot be revised after the audio starts');
});

test('reveal only counts up, and only at vérifier', () => {
  let state = model.radioReduce(model.RADIO_INITIAL, { type: 'guess', id: 'accord' });
  state = model.radioReduce(state, { type: 'listen' });
  assert.equal(model.radioReduce(state, { type: 'reveal' }).revealed, 0);

  state = model.radioReduce(state, { type: 'heard' });
  state = model.radioReduce(state, { type: 'verify' });
  state = model.radioReduce(state, { type: 'reveal' });
  assert.equal(state.revealed, 1);
  state = model.radioReduce(state, { type: 'revealAll', count: 3 });
  assert.equal(state.revealed, 3);
  state = model.radioReduce(state, { type: 'revealAll', count: 1 });
  assert.equal(state.revealed, 3, 'showing everything is not undone by a smaller count');
});

test('the cycle ends at retenir, and restart is a real reset', () => {
  let state = model.RADIO_INITIAL;
  for (const event of [
    { type: 'guess', id: 'accord' },
    { type: 'listen' },
    { type: 'heard' },
    { type: 'verify' },
    { type: 'retain' },
  ]) {
    state = model.radioReduce(state, event);
  }
  assert.equal(state.stage, 'retenir');
  assert.deepEqual(model.radioReduce(state, { type: 'restart' }), model.RADIO_INITIAL);
  assert.deepEqual([...model.RADIO_STAGES], ['predire', 'ecouter', 'verifier', 'retenir']);
  assert.equal(model.radioStageOrdinal('verifier'), 3);
});

// ---------------------------------------------------------------------------
// The remembered preference
// ---------------------------------------------------------------------------

test('listening first is off unless the learner asked for it, and storage may refuse', () => {
  const store = new Map();
  const original = global.window;
  global.window = {
    localStorage: {
      getItem: (key) => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, String(value)),
    },
  };
  try {
    assert.equal(model.readListenFirst(), false);
    model.writeListenFirst(true);
    assert.equal(store.get(model.LISTEN_FIRST_KEY), '1');
    assert.equal(model.readListenFirst(), true);
    model.writeListenFirst(false);
    assert.equal(model.readListenFirst(), false, 'off is stored, not merely absent');

    global.window = {
      get localStorage() {
        throw new Error('site data blocked');
      },
    };
    assert.equal(model.readListenFirst(), false, 'a blocked store is the default, not a crash');
    model.writeListenFirst(true); // must not throw
  } finally {
    global.window = original;
  }
});

// ---------------------------------------------------------------------------
// The text path is unaffected when the mode is off
// ---------------------------------------------------------------------------

const SCENE_STEP = {
  id: 'step-1',
  kind: 'scene',
  state: 'active',
  prompt: {
    setup_fr: 'Vous entrez dans la boulangerie.',
    setup_native: 'You walk into the bakery.',
    objective_native: 'Ask for a baguette.',
    character_line_fr: '',
    image_url: null,
  },
};

test('with the mode off, the scene renders and nothing audio-shaped is called', () => {
  apiCalls.length = 0;
  const copy = journeyCopy('fr');
  const html = renderToStaticMarkup(
    React.createElement(StoryEpisodeStep, {
      journeyId: 'journey-1',
      step: SCENE_STEP,
      copy,
      busy: false,
      onContinue: () => {},
    }),
  );

  // Server render: no effects, so the plain scene prompt is what appears.
  assert.ok(html.includes('Vous entrez dans la boulangerie.'), html.slice(0, 400));
  assert.equal(
    apiCalls.length,
    0,
    `the text path must make no request: ${JSON.stringify(apiCalls)}`,
  );
  const audioShaped = apiCalls.filter((call) => /Episode(Audio|Prediction)/.test(call.method));
  assert.deepEqual(audioShaped, []);
});

test('every new copy key exists in all three control languages', () => {
  const keys = [
    'listen_first_label',
    'listen_first_hint',
    'listen_first_on',
    'listen_first_off',
    'radio_stage_predire',
    'radio_stage_ecouter',
    'radio_stage_verifier',
    'radio_stage_retenir',
    'radio_predire_body',
    'radio_guess_label',
    'radio_listen_action',
    'radio_ecouter_body',
    'radio_words_hidden',
    'radio_play',
    'radio_replay',
    'radio_verify_action',
    'radio_reveal',
    'radio_reveal_all',
    'radio_guess_confirmed',
    'radio_guess_other',
    'radio_guess_unresolved',
    'radio_retenir_body',
    'radio_audio_disabled',
    'radio_audio_failed',
    'radio_audio_offline',
    'radio_audio_unsupported',
    'radio_audio_empty',
    'radio_read_instead',
  ];
  for (const language of ['fr', 'en', 'de']) {
    const table = journeyCopy(language);
    for (const key of keys) {
      assert.equal(typeof table[key], 'string', `${language}.${key}`);
      assert.ok(table[key].trim().length > 0, `${language}.${key} is empty`);
    }
  }
  // The stage names are the French ones the learner is told the cycle by.
  const fr = journeyCopy('fr');
  assert.equal(fr.radio_stage_predire, 'Prédire');
  assert.equal(fr.radio_stage_retenir, 'Retenir');
});

test('no copy string in any language mentions pronunciation or accent', () => {
  // WP-27's owner decision is a product-wide WON'T-DO, and adding audio is
  // exactly the moment someone would be tempted to score a learner's accent.
  const forbidden = [
    'pronunciation',
    'pronounce',
    'accent',
    'aussprache',
    'prononciation',
    'prononcez',
  ];
  for (const language of ['fr', 'en', 'de']) {
    const table = journeyCopy(language);
    for (const [key, value] of Object.entries(table)) {
      if (!key.startsWith('radio_') && !key.startsWith('listen_first')) continue;
      const folded = String(value).toLowerCase();
      for (const word of forbidden) {
        assert.ok(!folded.includes(word), `${language}.${key} mentions "${word}"`);
      }
    }
  }
});
