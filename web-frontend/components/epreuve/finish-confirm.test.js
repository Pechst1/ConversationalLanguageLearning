// node --test components/epreuve/finish-confirm.test.js
//
// #88 — «Stop here?» stays open until it is answered. It used to revert by
// itself after 4 s, so the second tap landed on the reverted button.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, 'Epreuve.tsx'), 'utf8');
const topBar = source.slice(source.indexOf('const [confirming, setConfirming]'), source.indexOf('const runCount'));

test('the finish confirmation has no timer that closes it', () => {
  assert.doesNotMatch(topBar, /setTimeout/);
  assert.match(topBar, /Escape/);
});

test('the confirmation closes only when answered, cancelled, or the séance is no longer partial', () => {
  assert.match(topBar, /if \(partial && !confirming\) \{\s*setConfirming\(true\);\s*return;\s*\}/);
  assert.match(topBar, /setConfirming\(false\);\s*onFinish\?\.\(\);/);
});
