// node --test components/atelier-v2/journey/story-art-poll.test.js
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { shouldPollStoryArtLate, STORY_ART_LATE_POLLS } = require('./story-art-poll.ts');
const { STORY_ART_POLL_LIMIT } = require('./story-episode-model.ts');

const page = (...statuses) => ({ panels: statuses.map((image_status) => ({ image_status })) });

test('a drawing page keeps polling for the normal window plus five minutes', () => {
  assert.equal(shouldPollStoryArtLate(page('rendering', 'panel_art'), 0, true), true);
  assert.equal(shouldPollStoryArtLate(page('rendering'), STORY_ART_POLL_LIMIT, true), true);
  assert.equal(shouldPollStoryArtLate(page('rendering'), STORY_ART_POLL_LIMIT + STORY_ART_LATE_POLLS, true), false);
});

test('a healed page seen drawing is re-read while it shows plates', () => {
  const healed = page('setting_reference', 'panel_art');
  assert.equal(shouldPollStoryArtLate(healed, STORY_ART_POLL_LIMIT, true), true);
  assert.equal(shouldPollStoryArtLate(healed, STORY_ART_POLL_LIMIT + STORY_ART_LATE_POLLS, true), false);
});

test('a page never seen drawing, or fully drawn, is not polled', () => {
  assert.equal(shouldPollStoryArtLate(page('setting_reference'), 0, false), false);
  assert.equal(shouldPollStoryArtLate(page('panel_art', 'panel_art'), 3, true), false);
  assert.equal(shouldPollStoryArtLate(null, 0, true), false);
});
