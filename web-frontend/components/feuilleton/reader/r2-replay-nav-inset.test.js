/**
 * R2 item 5 · the archive reader's «Weiter» is not under the tab bar.
 *
 * Real play (17 Nov, 375×812, a1-d2-replay-nav-overlap.png): in the archive's replay
 * the reader's pinned navigation sat under the fixed tab bar. The geometry is
 * measured in a browser by `e2e/replay-nav-layout.mjs` (no server); this pins the
 * rules it measures, so a refactor of the reader's styles cannot drop them silently.
 *
 * Run: `node --test components/feuilleton/reader/r2-replay-nav-inset.test.js`
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const css = fs.readFileSync(path.join(__dirname, 'reader-styles.tsx'), 'utf8');

test('under the fixed tab bar, the reader navigation stands on the bar token', () => {
  const block = css.slice(css.indexOf('@media (max-width: 760px)'));
  assert.ok(block.length > 0, 'the phone-width block exists');
  assert.match(
    block,
    /\.app-root:has\(\.phone-product-nav\.fixed\) \.av2 \.fr-nav \{\s*bottom: calc\(var\(--phone-bottom-nav-space\) \+ 10px\);/,
  );
  assert.match(block, /\.fr-reader\[data-story\] \{\s*padding-bottom: calc\(138px \+ var\(--phone-bottom-nav-space\)\);/);
  assert.match(block, /\.fr-over-nav:not\(:empty\) \{\s*bottom: calc\(138px \+ var\(--phone-bottom-nav-space\)\);/);
});

test('the bar is drawn below 761px, the width the rule is scoped to', () => {
  const tokens = fs.readFileSync(path.join(__dirname, '../../../styles/atelier-v2.css'), 'utf8');
  assert.match(tokens, /@media \(max-width: 760px\) \{\s*\.av2\.av2-tabbar\.fixed \{ display: grid; \}/);
});
