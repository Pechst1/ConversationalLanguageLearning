/**
 * R2 item 3 · the scene's end does not stall.
 *
 * Real play (17 Nov): «Wie es weitergeht, wird gerade geschrieben…» held the last
 * panel with no button for 15–30 s (A1 days 3–6), 5–32 s at B1. The story lane
 * already starts at the last reply (tests/test_r2_ending_starts_at_last_reply.py);
 * now the learner reads the exchange's closing panels while it runs, and
 * «Continuer» with «the ending will be there next time» comes after 8 s, not 30.
 *
 * Run: `node --test components/atelier-v2/journey/r2-finale-closing.test.js`
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { FINALE_ESCAPE_MS, finaleNav } = require(path.join(WEB_ROOT, 'components/feuilleton/reader/finale-wait.ts'));
const { withClosingExchanges, storyStagesWithFinale } = require(path.join(HERE, 'story-episode-model.ts'));

const page = {
  id: 'ep-1', scene_id: 's', serial_thread_id: '', serial_episode_id: null, journey_id: 'j', title_fr: '',
  status: 'available', chapter: null, panel_index: 0, resolution: null, grammar_focus: null,
  panels: [1, 2, 3, 4, 5].map((n) => ({
    id: `p${n}`, index: n - 1, narration_fr: `Case ${n}.`, image_url: `/art/${n}.svg`, image_status: 'panel_art',
    dialogue: [{ character_id: 'lila', character_name: 'Lila', text_fr: `Ligne ${n}.` }],
  })),
};

const thread = [
  { learner_fr: 'Je pars mercredi.', character_fr: 'Tu pars mercredi ?', character_lines: [], correction: null, unchecked: false },
  {
    learner_fr: 'Oui, deux jours.',
    character_fr: '',
    character_lines: [{ speaker_id: 'lila', speaker_name: 'Lila', text_fr: 'Deux jours, alors.' }],
    correction: null,
    unchecked: false,
  },
];

test('«Continuer» comes after 8 seconds of waiting, not 30', () => {
  assert.equal(FINALE_ESCAPE_MS, 8_000);
  const waiting = { isLast: true, waiting: true, filed: false };
  assert.equal(finaleNav({ ...waiting, waitedMs: 8_000 }), 'continue_late');
  assert.equal(finaleNav({ ...waiting, waitedMs: 30_000 }), 'continue_late');
});

test('the exchange just had becomes the closing panels, before the finale', () => {
  const { episode, firstClosing } = withClosingExchanges(page, thread, { id: 'lila', name: 'Lila' });
  assert.equal(firstClosing, 5, 'the reader opens on the first closing panel');
  assert.equal(episode.panels.length, 7);
  const [first, second] = episode.panels.slice(5);
  assert.deepEqual(first.dialogue.map((line) => [line.character_id, line.text_fr]), [
    ['toi', 'Je pars mercredi.'],
    ['lila', 'Tu pars mercredi ?'],
  ]);
  assert.deepEqual(second.dialogue.map((line) => line.text_fr), ['Oui, deux jours.', 'Deux jours, alors.']);
  assert.equal(first.image_url, '/art/5.svg', 'on the page\'s last plate');
  const stages = storyStagesWithFinale(episode, { kind: 'resolution', key: 'fin', tasks: [] });
  assert.equal(stages[stages.length - 1].kind, 'resolution', 'the finale still closes the page');
  assert.equal(stages.length, 8);
});

test('no exchange, no change: the page and the finale as before', () => {
  assert.deepEqual(withClosingExchanges(page, [], null), { episode: page, firstClosing: null });
  assert.deepEqual(withClosingExchanges(page, null, null), { episode: page, firstClosing: null });
});

test('the resolution step opens the reader on the closing panels while the ending is written', () => {
  const steps = fs.readFileSync(path.join(HERE, 'JourneySteps.tsx'), 'utf8');
  assert.match(steps, /withClosingExchanges\(pageOrFrame, thread, speaker\)/);
  assert.match(steps, /openAt=\{closing\.firstClosing\}/);
  const reader = fs.readFileSync(path.join(HERE, 'StoryEpisodeReader.tsx'), 'utf8');
  assert.match(reader, /openAt !== null && openAt >= 0 && openAt < stages\.length/);
});
