import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { issuesFrom, LABELS, readReports, titleFor } from '../../../.github/scripts/walk-main-issue.mjs';
import { REPO_ROOT } from './stack.mjs';

const workflow = (name) => readFileSync(path.join(REPO_ROOT, '.github/workflows', name), 'utf8');

test('on a push to main CI skips the walk, so the deploy waits only for the fast checks', () => {
  const ci = workflow('ci.yml');
  const job = ci.slice(ci.indexOf('  browser-walk:'), ci.indexOf('  publish:'));
  assert.match(job, /if: github\.event_name != 'push' \|\| github\.ref != 'refs\/heads\/main'/);
  // CI publishes only a tag's image; main's is published after its walks (below).
  const publish = ci.slice(ci.indexOf('  publish:'), ci.indexOf('  generated-types:'));
  assert.match(publish, /startsWith\(github\.ref, 'refs\/tags\/'\)/);
});

test('the walks still run on main, after CI, on the commit CI checked', () => {
  const yml = workflow('walk-main.yml');
  assert.match(yml, /workflow_run:\s+workflows: \[CI\]\s+types: \[completed\]\s+branches: \[main\]/);
  assert.match(yml, /uses: \.\/\.github\/workflows\/walk\.yml/);
  assert.match(yml, /ref: \$\{\{ github\.event\.workflow_run\.head_sha \}\}/);
  assert.match(yml, /issues: write/);
  assert.match(yml, /needs\.walk\.result == 'success'\s+permissions:\s+contents: read\s+packages: write\s+uses: \.\/\.github\/workflows\/publish-image\.yml/);
  assert.match(yml, /walk-main-issue\.mjs/);
  // The artifacts the report job reads are the ones walk.yml uploads on this event.
  assert.match(workflow('walk.yml'), /github\.event_name == 'workflow_run' && 'main'/);
  assert.match(yml, /pattern: walk-main-\$\{\{ github\.run_number \}\}-\*/);
});

test('a failed walk on main is one issue per check, with its lines and the run', () => {
  const reports = [
    { shard: 'walk-main-9-season-a', report: { failures: [{ id: 'a-way-forward', detail: 'stuck for 10s on «Lexique»', where: { day: 3 } }] } },
    { shard: 'walk-main-9-de', report: { failures: [{ id: 'a-way-forward', detail: 'no change for 12s', where: {} }, { id: 'day-plays-its-plan', detail: 'day 4: words not played', where: {} }] } },
  ];
  const issues = issuesFrom(reports, { run: 'https://example.test/run/1', sha: 'abcdef1234567890', shards: ['walk-main-9-season-a', 'walk-main-9-de'] });
  assert.deepEqual(issues.map((i) => i.title), [titleFor('a-way-forward'), titleFor('day-plays-its-plan')]);
  assert.match(issues[0].body, /`walk-main-9-season-a`: stuck for 10s on «Lexique» \(\{"day":3\}\)/);
  assert.match(issues[0].body, /`walk-main-9-de`: no change for 12s$/m);
  assert.match(issues[0].body, /Run: https:\/\/example\.test\/run\/1/);
  assert.match(issues[0].body, /^Done when: /m);
  assert.match(issues[1].comment, /Failed again on main for abcdef123456/);
  assert.deepEqual(LABELS.slice(0, 2), ['walk-finding', 'queue:ready']);
});

test('a shard that left no report is still filed', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'walk-main-'));
  mkdirSync(path.join(root, 'walk-main-9-fr'), { recursive: true });
  mkdirSync(path.join(root, 'walk-main-9-de'), { recursive: true });
  writeFileSync(path.join(root, 'walk-main-9-de', 'report.json'), JSON.stringify({ failures: [] }));
  const reports = readReports(root);
  assert.deepEqual(reports.map((r) => r.shard), ['walk-main-9-de']);
  const issues = issuesFrom(reports, { run: 'r', sha: 's', shards: ['walk-main-9-de', 'walk-main-9-fr'] });
  assert.deepEqual(issues.map((i) => i.id), ['walk-harness']);
  assert.match(issues[0].body, /`walk-main-9-fr`/);
});
