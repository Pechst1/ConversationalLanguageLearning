// node --test lib/motion.test.js
//
// The grammar pilot's motion: every animation can be skipped, and reduced motion moves nothing.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.join(path.resolve(__dirname, '..'), 'node_modules/sucrase/register/ts'));
const { createScene, motionIsStill } = require('./motion.ts');
const { readFileSync } = require('node:fs');

/** An element whose animation stays open until it is finished or cancelled. */
function fakeElement() {
  const started = [];
  return {
    started,
    animate() {
      let settle;
      let fail;
      const finished = new Promise((resolve, reject) => {
        settle = resolve;
        fail = reject;
      });
      const animation = {
        finished,
        finish: () => settle(),
        cancel: () => fail(new Error('AbortError')),
      };
      started.push(animation);
      return animation;
    },
  };
}

test('reduced motion starts nothing but still holds a line long enough to read', async () => {
  const scene = createScene(() => true);
  const element = fakeElement();
  await scene.animate(element, []);
  assert.equal(element.started.length, 0);
  const before = Date.now();
  await scene.wait(30);
  assert.ok(Date.now() - before >= 25);
});

test('a finish ends what runs and what holds, and later steps run instantly', async () => {
  const scene = createScene(() => false);
  const element = fakeElement();
  const animated = scene.animate(element, []);
  const held = scene.wait(60000);
  scene.finish();
  await Promise.all([animated, held]);
  await scene.animate(element, []);
  assert.equal(element.started.length, 1);
  await scene.wait(60000);
});

test('resume plays normally again after a skip', () => {
  const scene = createScene(() => false);
  const element = fakeElement();
  scene.finish();
  scene.resume();
  scene.animate(element, []);
  assert.equal(element.started.length, 1);
  scene.dispose();
});

test('dispose cancels without an unhandled rejection and starts nothing more', async () => {
  const scene = createScene(() => false);
  const element = fakeElement();
  const animated = scene.animate(element, []);
  const held = scene.wait(60000);
  scene.dispose();
  await Promise.all([animated, held]);
  await scene.animate(element, []);
  assert.equal(element.started.length, 1);
});

test('a revived scene moves and holds again: strict mode remounts with the same ref', async () => {
  const scene = createScene(() => false);
  const element = fakeElement();
  scene.dispose();
  scene.revive();
  scene.animate(element, []);
  assert.equal(element.started.length, 1);
  let held = false;
  const hold = scene.wait(20).then(() => {
    held = true;
  });
  await Promise.resolve();
  assert.equal(held, false);
  await hold;
  scene.dispose();
});

test('the pilot takes its scene from the hook, which revives it on every mount', () => {
  const read = (file) => readFileSync(path.join(path.resolve(__dirname, '..'), file), 'utf8');
  ['components/atelier-v2/rule/RuleMontage.tsx', 'components/epreuve/Declic.tsx'].forEach((file) => {
    const source = read(file);
    assert.match(source, /= useScene\(\)/, file);
    assert.doesNotMatch(source, /createScene\(|scene\.dispose\(/, file);
  });
  assert.match(read('lib/motion.ts'), /useEffect\(\(\) => \{\s*scene\.revive\(\);\s*return \(\) => scene\.dispose\(\);/);
});

test('no element or no way to animate is simply nothing to wait for', async () => {
  const scene = createScene(() => false);
  await scene.animate(null, []);
  await scene.animate({}, []);
});

test('with no window there is no motion', () => {
  assert.equal(motionIsStill(), true);
});
