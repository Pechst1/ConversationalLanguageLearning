// node --test scripts/forge-miss-settle.test.mjs
//
// #319: the walk measured «the correction sits above the verdict sheet» 900 ms after a
// miss, whatever the scroll was doing. A smooth scroll takes as long as the distance and
// the machine make it, so a long French card was caught on its way and reported as under
// the sheet. The walk now measures once the card has stopped moving, and still fails a
// card that has stopped in the wrong place.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Findings } from '../e2e/lib/assertions.mjs';
import { LearnerWalk } from '../e2e/lib/learner-walk.mjs';

const SHEET_TOP = 550;
const HEADER_BOTTOM = 70;

/** A page whose card scrolls from `from` to `to` over `ms`, then stays. */
function scrollingPage({ from, to, ms, height = 235 }) {
  const t0 = Date.now();
  return {
    async evaluate() {
      const k = Math.min(1, (Date.now() - t0) / ms);
      const cardTop = Math.round(from + (to - from) * k);
      return { cardTop, cardBottom: cardTop + height, sheetTop: SHEET_TOP, headerBottom: HEADER_BOTTOM, text: 'Nous sommes contents ici.' };
    },
  };
}

function walkOn(page) {
  const findings = new Findings();
  const walk = new LearnerWalk({ page, findings, outDir: '/tmp/forge-miss-settle', lang: 'fr', level: 'A1.1', stack: {}, shots: { root: '/tmp', list: [] }, scale: 1 });
  return { walk, findings };
}

const verdictOf = (findings) => findings.results.filter((r) => r.id === 'forge-miss-correction-above-the-sheet');

test('a card still scrolling into place when the old fixed wait ended passes once it has arrived', async () => {
  // Starts under the sheet (bottom 610 > 550), arrives above it at 1.6 s.
  const { walk, findings } = walkOn(scrollingPage({ from: 375, to: 303, ms: 1600 }));
  await walk.forgeMissInView('typing');
  const [verdict] = verdictOf(findings);
  assert.ok(verdict, 'the check ran');
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a card that stops under the sheet still fails', async () => {
  const { walk, findings } = walkOn(scrollingPage({ from: 375, to: 375, ms: 1 }));
  await walk.forgeMissInView('typing');
  const [verdict] = verdictOf(findings);
  assert.ok(verdict, 'the check ran');
  assert.equal(verdict.ok, false, 'a card from 375 to 610 runs under the sheet that starts at 550');
  assert.match(verdict.detail, /runs under the verdict sheet/);
});

test('nothing to measure is not a failure', async () => {
  const { walk, findings } = walkOn({ evaluate: async () => null });
  await walk.forgeMissInView('typing');
  assert.equal(verdictOf(findings).length, 0);
});
