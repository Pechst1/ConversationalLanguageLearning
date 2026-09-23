/**
 * WP-87 «La réplique d'abord» — the client half.
 *
 * The reply arrives with the verdict in ~max(tutor, voice) seconds, so the typed
 * reveal is a beat (≤ 0.8 s), not a wait. The resolution's ending is written by
 * the story lane after the response: while `story_pending` is true the step is a
 * short "…" state, continue does not skip it, and the journey is polled.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');

const WEB_ROOT = path.resolve(__dirname, '../../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const {
  REPLY_REVEAL_MAX_MS,
  VERDICT_BEAT_MS,
  replyRevealMs,
  verdictDelayMs,
} = require('../../../lib/journey-reply-reveal');
const {
  STORY_POLL_LIMIT,
  STORY_POLL_MS,
  resolutionAwaitsStory,
  storyPollTarget,
} = require('./journey-state');

function resolution(prompt) {
  return {
    id: 'res', ordinal: 4, status: 'active', estimated_seconds: 20, assistance_used: [],
    kind: 'resolution',
    prompt: { outcome_key: 'open', character_line_fr: '', summary_native: '', ...prompt },
  };
}

function journey(step, status = 'active') {
  return { id: 'j1', status, current_step_id: step ? step.id : null, steps: step ? [step] : [] };
}

test('the typed reply never holds the verdict for more than 0.8 s', () => {
  assert.ok(REPLY_REVEAL_MAX_MS <= 800);
  const long = 'Merci ! '.repeat(60);
  assert.equal(replyRevealMs(long), REPLY_REVEAL_MAX_MS);
  assert.ok(verdictDelayMs(long) <= 800 + VERDICT_BEAT_MS);
  assert.equal(replyRevealMs(long, { reducedMotion: true }), 0);
});

test('a resolution whose ending is still being written waits and is polled', () => {
  const pending = resolution({ story_pending: true });
  assert.equal(resolutionAwaitsStory(pending), true);
  assert.equal(storyPollTarget(journey(pending)), 'j1');
  assert.equal(storyPollTarget(journey(pending, 'paused')), 'j1');
  assert.ok(STORY_POLL_MS >= 500 && STORY_POLL_LIMIT * STORY_POLL_MS >= 90_000,
    'the polls outlast the server-side heal of a dead lane');
});

test('a settled or legacy resolution is shown at once and never polled', () => {
  for (const step of [resolution({ story_pending: false }), resolution({})]) {
    assert.equal(resolutionAwaitsStory(step), false);
    assert.equal(storyPollTarget(journey(step)), null);
  }
  assert.equal(storyPollTarget(journey(resolution({ story_pending: true }), 'completed')), null);
  assert.equal(storyPollTarget(null), null);
});
