import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';

import { REPO_ROOT } from './stack.mjs';
import { needsFullWalk, walkMatrix } from './walk-scope.mjs';

test('a pull request that touches what the walk walks plays all four shards at full length', () => {
  for (const file of [
    'web-frontend/e2e/lib/learner-walk.mjs',
    'web-frontend/components/atelier-v2/journey/JourneyRecap.tsx',
    'web-frontend/pages/atelier.tsx',
    'app/services/daily_journey.py',
    'app/services/living_story.py',
    'app/services/season/runtime.py',
    'app/services/judge.py',
    '.github/workflows/walk.yml',
  ]) {
    const m = walkMatrix('pull_request', ['README.md', file]);
    assert.equal(m.full, true, file);
    assert.deepEqual(m.include.map((row) => `${row.shard}×${row.days}`), ['en + B1×7', 'de×7', 'fr×7', 'season×10']);
    assert.ok(m.include.every((row) => row.pr_args === ''), 'no shortening flag on a full walk');
  }
});

test('any other pull request keeps the one short shard', () => {
  const m = walkMatrix('pull_request', ['app/services/daily_journey_helpers.py', 'web-frontend/pages/atelier-old.tsx', 'docs/x.md']);
  assert.equal(m.full, false);
  assert.deepEqual(m.include, [{ shard: 'en + B1', days: 3, key: 'en-b1', args: '--langs en --b1-days 3 --season-days 0', pr_args: '--days 3' }]);
  assert.equal(needsFullWalk([]), false);
});

test('main, the nightly run and a manual run always play the full set', () => {
  for (const event of ['push', 'schedule', 'workflow_dispatch']) assert.equal(walkMatrix(event, []).full, true, event);
});

test('the workflow names the jobs from the matrix, so main keeps its check names', () => {
  const yml = readFileSync(path.join(REPO_ROOT, '.github/workflows/walk.yml'), 'utf8');
  assert.match(yml, /name: Walk · \$\{\{ matrix\.shard \}\} × \$\{\{ matrix\.days \}\} days/);
  assert.match(yml, /node web-frontend\/e2e\/lib\/walk-scope\.mjs/);
});
