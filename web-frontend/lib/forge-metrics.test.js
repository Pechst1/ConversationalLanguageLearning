// WP-S8 — «La Forge» on the pilot dashboard: window/band selection and labels.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const {
  ALL_BANDS,
  distributionLabel,
  forgeBands,
  forgeSectionFor,
  latencyOverTarget,
  rateLabel,
} = require('./forge-metrics.ts');

const section = (learners) => ({ learners, rules: {}, seances: {}, latency: { by_rung: [], local_p95_ms: null } });
const report = {
  generated_at: '2026-09-24T12:00:00Z',
  windows: [
    { days: 7, since: '', overall: section(3), by_band: [{ band: 'A1', ...section(2) }, { band: 'A2', ...section(1) }] },
    { days: 30, since: '', overall: section(9), by_band: [] },
  ],
};

test('a window and a band pick their section; unknown ones are null', () => {
  assert.equal(forgeSectionFor(report, 7, ALL_BANDS).learners, 3);
  assert.equal(forgeSectionFor(report, 7, 'A2').learners, 1);
  assert.equal(forgeSectionFor(report, 30).learners, 9);
  assert.equal(forgeSectionFor(report, 30, 'A1'), null);
  assert.equal(forgeSectionFor(report, 90), null);
  assert.equal(forgeSectionFor(null, 7), null);
  assert.deepEqual(forgeBands(report, 7), ['A1', 'A2']);
});

test('nothing measured reads n/a, never 0', () => {
  assert.equal(rateLabel(null), 'n/a');
  assert.equal(rateLabel(0), '0 %');
  assert.equal(rateLabel(0.456), '46 %');
  assert.equal(distributionLabel({ n: 0, median: null, p90: null }), 'n/a (n = 0)');
  assert.equal(distributionLabel({ n: 12, median: 23, p90: 41 }), '23 · p90 41 (n = 12)');
  assert.equal(distributionLabel({ n: 2, median: 5.25, p90: 6 }, ' min'), '5.3 min · p90 6 min (n = 2)');
});

test('the WP-S1 latency bar: 300 ms keyed, 500 ms free production', () => {
  const row = (rung, p95) => ({ rung, local_p95_ms: p95 });
  assert.equal(latencyOverTarget(row('transform', 320)), true);
  assert.equal(latencyOverTarget(row('transform', 280)), false);
  assert.equal(latencyOverTarget(row('free_use', 420)), false);
  assert.equal(latencyOverTarget(row('produce', 520)), true);
  assert.equal(latencyOverTarget(row('recognise', null)), false);
});

test('the section is on the pilot page and uses only the page tokens', () => {
  const page = fs.readFileSync(path.join(__dirname, '../pages/pilot-ops.tsx'), 'utf8');
  assert.match(page, /<ForgeMetricsSection /);
  assert.match(page, /\/analytics\/pilot-forge/);
  const component = fs.readFileSync(path.join(__dirname, '../components/pilot/ForgeMetricsSection.tsx'), 'utf8');
  assert.doesNotMatch(component, /#[0-9a-fA-F]{3,6}\b|rgb\(|font-family/);
  const colours = new Set(component.match(/var\(--[a-z0-9-]+\)/g));
  for (const colour of colours) {
    assert.ok(/--app-(ink|ink-3|paper|paper-3|sheet|red|blue)\)/.test(colour), colour);
  }
});
