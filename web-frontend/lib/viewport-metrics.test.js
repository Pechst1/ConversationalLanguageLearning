// iOS pans the visual viewport when the keyboard opens; sticky headers must
// follow it (issue #89) instead of sliding under the Dynamic Island.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const { visualViewportOffsetTop } = require('./viewport-metrics.ts');

test('offset is the visual viewport pan, never negative or NaN', () => {
  assert.equal(visualViewportOffsetTop({ offsetTop: 47.4 }), 47);
  assert.equal(visualViewportOffsetTop({ offsetTop: -12 }), 0);
  assert.equal(visualViewportOffsetTop({ offsetTop: NaN }), 0);
  assert.equal(visualViewportOffsetTop(null), 0);
  assert.equal(visualViewportOffsetTop(undefined), 0);
});

test('sticky app headers follow the visual viewport top', () => {
  for (const f of ['../components/epreuve/Epreuve.tsx', '../components/layout/EditorialMasthead.tsx']) {
    const src = fs.readFileSync(path.join(__dirname, f), 'utf8');
    assert.match(src, /top:\s*var\(--app-viewport-offset-top, 0px\)/, f);
  }
});
