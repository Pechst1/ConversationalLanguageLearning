/**
 * P11 · «Passer à la scène»: before the day's unplayed scene the session's quiet
 * control skips to it (one `advance` with `skip_to_scene`); it never ends the day.
 *
 * Run: `node --test components/atelier-v2/journey/p11-skip-to-scene.test.js`
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

const { sessionStopControl } = require(path.join(HERE, 'journey-state.ts'));
const { journeyCopy } = require(path.join(HERE, 'journey-copy.ts'));

function day(statuses) {
  const kinds = ['rule', 'recall', 'scene', 'respond', 'resolution'];
  return {
    id: 'j1',
    status: 'active',
    steps: kinds.map((kind, ordinal) => ({ id: `s${ordinal}`, kind, ordinal, status: statuses[ordinal] || 'pending' })),
  };
}

test('every step before the unplayed scene skips to it, the rule card and the drill alike', () => {
  const opening = day(['active']);
  assert.equal(sessionStopControl(opening, opening.steps[0]), 'skip');
  const drill = day(['completed', 'active']);
  assert.equal(sessionStopControl(drill, drill.steps[1]), 'skip');
});

test('from the scene on, the control ends the day as before', () => {
  const onScene = day(['completed', 'completed', 'active']);
  assert.equal(sessionStopControl(onScene, onScene.steps[2]), 'end');
  const ending = day(['completed', 'completed', 'completed', 'completed', 'active']);
  assert.equal(sessionStopControl(ending, ending.steps[4]), 'end');
  assert.equal(sessionStopControl(null, null), 'end');
});

test('the control is named in the three languages', () => {
  assert.equal(journeyCopy('fr').skip_to_scene, 'Passer à la scène');
  assert.equal(journeyCopy('de').skip_to_scene, 'Weiter zur Szene');
  assert.equal(journeyCopy('en').skip_to_scene, 'Skip to the scene');
});

test('the skip is one advance with skip_to_scene, never a finish', () => {
  const hook = fs.readFileSync(path.join(HERE, 'useDailyJourney.ts'), 'utf8');
  const start = hook.indexOf('const skipToScene = useCallback');
  const skip = hook.slice(start, hook.indexOf('}, [advance]);', start));
  assert.match(skip, /advance\(\{ skipToScene: true \}\)/);
  assert.doesNotMatch(skip, /finish/);
  const service = fs.readFileSync(path.join(WEB_ROOT, 'services/daily-journey.ts'), 'utf8');
  assert.match(service, /skip_to_scene: true/);
});
