/* WP-116 phase 4 · French text → mouth shapes. node --test lib/visemes-fr.test.js */
const test = require('node:test');
const assert = require('node:assert/strict');
require('../node_modules/sucrase/register/ts');
const { mouthSteps, visemeAt } = require('./visemes-fr.ts');

test('vowels open the mouth, m/b/p close it, f/v bite, pauses rest', () => {
  const shapes = mouthSteps('Bonjour, Marin. Un café ?').map((step) => step.viseme);
  assert.equal(shapes[0], 'm', 'B closes the lips');
  assert.ok(shapes.includes('o'), 'on / ou');
  assert.ok(shapes.includes('a'), 'a');
  assert.ok(shapes.includes('e'), 'é');
  assert.ok(shapes.includes('f'), 'f');
  assert.ok(shapes.includes('rest'));
});

test('the line plays from its first shape to rest', () => {
  const steps = mouthSteps('Elle prenait ça.');
  assert.equal(visemeAt(steps, 0), 'e');
  assert.equal(visemeAt(steps, 1), 'rest', 'over at the end');
  assert.equal(visemeAt(steps, -0.1), 'rest');
  assert.equal(visemeAt([], 0.5), 'rest');
  const seen = new Set();
  for (let at = 0; at < 1; at += 0.02) seen.add(visemeAt(steps, at));
  assert.ok(seen.size >= 4, `a spoken line moves through several shapes: ${[...seen]}`);
});

test('a held vowel does not flicker', () => {
  const steps = mouthSteps('aaa');
  assert.equal(steps.length, 1);
  assert.equal(steps[0].viseme, 'a');
});
