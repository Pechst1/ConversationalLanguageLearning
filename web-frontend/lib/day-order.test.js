// node --test lib/day-order.test.js
//
// The day's order (owner, 1 Nov 2026: the scene, then La Forge, then the words,
// then the seal) is written once. The server's `DaySessionStepKind` literal is
// the source; the generated `api.ts` union keeps its order (the generated-types
// check holds api.ts to the server, `test_round3_daily_session.py` holds the
// server's plan to the literal). Here: `lib/day-order.ts` must match that union,
// everything on this side must derive from it, and no file may write the order
// out a second time.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const order = require('./day-order.ts');
const dayPlan = require('./day-plan.ts');
const firstSteps = require('./first-steps.ts');

/** The `DaySessionStep.kind` union of the generated types, in its written order. */
function serverOrder() {
  const api = fs.readFileSync(path.join(WEB_ROOT, 'types/generated/api.ts'), 'utf8');
  const block = api.match(/\n\s+DaySessionStep: \{([\s\S]*?)\n\s+\};/);
  assert.ok(block, 'DaySessionStep is in types/generated/api.ts');
  const kind = block[1].match(/\n\s+kind: ([^;]+);/);
  assert.ok(kind, 'DaySessionStep.kind is in types/generated/api.ts');
  return kind[1].split('|').map((part) => part.trim().replace(/^"|"$/g, ''));
}

test('the day is the scene, then La Forge, then the words, then the seal (owner, 1 Nov)', () => {
  assert.deepEqual(serverOrder(), ['scene', 'grammar', 'words', 'finish']);
});

test('WORK_STEPS is the server’s order, the seal left out', () => {
  assert.deepEqual([...order.WORK_STEPS, 'finish'], serverOrder());
  // day-plan re-exports the one constant; it does not keep a copy.
  assert.equal(dayPlan.WORK_STEPS, order.WORK_STEPS);
});

test('the onboarding route is WORK_STEPS in its own names', () => {
  assert.deepEqual(
    [...firstSteps.ROUTE_STAGES],
    order.WORK_STEPS.map((kind) => order.ROUTE_STAGE_OF[kind]),
  );
  assert.deepEqual([...firstSteps.ROUTE_STAGES], ['story', 'forge', 'words']);
});

test('no other source writes the day’s order out again', () => {
  // Any array literal naming all three working steps (in either vocabulary, in
  // any order) is a second copy of the order. Tests build fixtures and are left
  // out; generated files carry the server's union, not an array.
  const names = [
    ['scene', 'words', 'grammar'],
    ['story', 'words', 'forge'],
  ];
  const offenders = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === 'node_modules' || entry.name.startsWith('.') || entry.name === 'generated') continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
        continue;
      }
      if (!/\.(ts|tsx)$/.test(entry.name) || /\.d\.ts$/.test(entry.name)) continue;
      const rel = path.relative(WEB_ROOT, full);
      if (rel === path.join('lib', 'day-order.ts')) continue;
      const source = fs.readFileSync(full, 'utf8');
      for (const match of source.matchAll(/\[([^\[\]]{0,80})\]/g)) {
        const items = [...match[1].matchAll(/['"]([a-z]+)['"]/g)].map((item) => item[1]);
        if (names.some((set) => items.length === 3 && set.every((name) => items.includes(name)))) {
          offenders.push(`${rel}: [${match[1]}]`);
        }
      }
    }
  };
  for (const dir of ['lib', 'components', 'pages', 'hooks', 'services', 'contexts']) {
    const full = path.join(WEB_ROOT, dir);
    if (fs.existsSync(full)) walk(full);
  }
  assert.deepEqual(offenders, [], 'write the order once, in lib/day-order.ts, and derive from it');
});
