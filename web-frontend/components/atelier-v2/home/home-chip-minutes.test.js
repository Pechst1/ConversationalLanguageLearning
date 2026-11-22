// node --test components/atelier-v2/home/home-chip-minutes.test.js
//
// #998 (walk 22 Nov 2026): Home's chips print their minutes through one
// formatter, in the chrome's language. The retell chip read «Gestern erzählen ·
// ≈ 2 min» beside «Neuer Brief · ≈ 6 Min.»: it wrote its minutes as an English
// literal instead of going through the minutes copy the letter chip uses
// (`extensionMinutes` → `formatPlannedDuration`). The forge chip's accessible
// name had the same literal.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const { extensionMinutes } = require('../journey/time-estimate.ts');
const { journalHomeChip } = require('@/lib/journal-home.ts');

test('the retell chip says its minutes the way the letter chip does, in en/de/fr', () => {
  const expected = { en: '≈ 2 min', de: '≈ 2 Min.', fr: '≈ 2 min' };
  for (const [language, meta] of Object.entries(expected)) {
    const chip = journalHomeChip({ daysAgo: 1 }, language);
    assert.equal(chip.meta, meta, `${language}: the retell chip's minutes`);
    // The same words as a letter chip of the same length.
    const letter = extensionMinutes({ extensions: [{ kind: 'letter', seconds: 120 }] }, 'letter', language);
    assert.equal(chip.meta, letter, `${language}: same minutes copy as the letter chip`);
    // The accessible name carries the same minutes as the visible chip.
    assert.ok(
      chip.ariaLabel.endsWith(` · ${meta.replace(/^≈ /, '')}`),
      `${language}: aria label «${chip.ariaLabel}» says «${meta}»`,
    );
  }
  // A language Home does not speak falls back to the English chrome.
  assert.equal(journalHomeChip({ daysAgo: 3 }, 'it').meta, '≈ 2 min');
});

test('no Home chip writes its minutes as a hand-typed «min» literal', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  const chips = page.slice(page.indexOf('const dayChips: HomeChip[]'), page.indexOf('const radioWeek = useRadioWeek()'));
  assert.ok(chips.length > 0, 'the day chips are found');
  assert.doesNotMatch(chips, /\} min`/, 'the forge chip names its minutes through formatPlannedDuration');
  const journal = fs.readFileSync(path.join(WEB_ROOT, 'lib/journal-home.ts'), 'utf8');
  assert.doesNotMatch(journal, /['`][^'`\n]*\d min['`]/, 'the retell chip names its minutes through the shared copy');
});
