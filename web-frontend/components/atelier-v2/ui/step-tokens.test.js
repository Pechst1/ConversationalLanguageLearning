// node --test components/atelier-v2/ui/step-tokens.test.js
//
// WP-L6: a longer rhythm's day (~30 steps) still fits one phone row — runs of
// one shape collapse into one token, the active run shows «4/14».

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

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { StepProgress, groupStepTokens, STEP_TOKENS_MAX } = require('./Surface');

const day = (activeAt) => {
  const shapes = [
    ...Array(14).fill('reward'),
    'story',
    ...Array(10).fill('reward'),
    'action',
    ...Array(2).fill('reward'),
    'done',
  ];
  return shapes.map((shape, index) => ({
    id: `s${index}`,
    shape,
    state: index < activeAt ? 'done' : index === activeAt ? 'active' : 'pending',
  }));
};

test('a short day keeps one token per step', () => {
  const steps = day(0).slice(0, STEP_TOKENS_MAX);
  assert.equal(groupStepTokens(steps).length, STEP_TOKENS_MAX);
});

test('a long day collapses into its movements, the active run counts', () => {
  const groups = groupStepTokens(day(3));
  assert.deepEqual(groups.map((g) => g.step.shape), ['reward', 'story', 'reward', 'action', 'reward', 'done']);
  assert.equal(groups[0].step.state, 'active');
  assert.equal(groups[0].position, 4);
  assert.equal(groups[0].count, 14);
  const later = groupStepTokens(day(20));
  assert.equal(later[0].step.state, 'done');
  assert.equal(later[1].step.state, 'done');
  assert.equal(later[2].step.state, 'active');
  assert.equal(later[2].position, 6);
});

test('the rendered rail stays short and shows the count', () => {
  const html = renderToStaticMarkup(React.createElement(StepProgress, { steps: day(3), label: 'Progress' }));
  assert.equal((html.match(/class="av2-token"/g) || []).length, 6);
  assert.match(html, /4\/14/);
  assert.match(html, /aria-valuemax="29"/);
});
