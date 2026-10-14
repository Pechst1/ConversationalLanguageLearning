// node --test lib/reward-moment-copy.test.js
// Live walk #118: the reward moment speaks the learner's chrome language.
const assert = require('node:assert/strict');
const { test } = require('node:test');
require('sucrase/register/ts');
const { rewardMomentCopy } = require('./reward-moment-copy.ts');

test('English and German sessions get their own words, not French', () => {
  const en = rewardMomentCopy('en');
  assert.equal(en.drafting.title, 'Bonus token earned');
  assert.equal(en.continue, 'Continue');
  assert.equal(en.credit(2), '+2 credit');
  const de = rewardMomentCopy('de');
  assert.equal(de.drafting.title, 'Bonus-Token verdient');
  assert.equal(de.continue, 'Weiter');
  for (const kind of ['drafting', 'logo', 'seal']) {
    for (const copy of [en, de]) {
      const text = Object.values(copy[kind]).join(' ');
      assert.doesNotMatch(text, /Jeton|crédit|Vous|vous/, `${kind}: ${text}`);
    }
    // German says du, never Sie.
    assert.doesNotMatch(Object.values(de[kind]).join(' '), /\b(Sie|Ihr|Ihre|Ihnen)\b/);
  }
});

test('French keeps its text, and an unknown language falls back to English', () => {
  assert.equal(rewardMomentCopy('fr').drafting.title, 'Jeton bonus gagné');
  assert.equal(rewardMomentCopy(undefined).continue, 'Continue');
});
