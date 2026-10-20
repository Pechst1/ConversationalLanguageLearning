// node --test lib/reward-moment-copy.test.js
// Live walk #118: the reward moment speaks the learner's chrome language.
const assert = require('node:assert/strict');
const { test } = require('node:test');
require('sucrase/register/ts');
const { rewardMomentCopy } = require('./reward-moment-copy.ts');

test('English and German sessions get their own words, not French', () => {
  const en = rewardMomentCopy('en');
  assert.equal(en.seal.title, 'Gold seal earned');
  assert.equal(en.continue, 'Continue');
  const de = rewardMomentCopy('de');
  assert.equal(de.seal.title, 'Goldsiegel verdient');
  assert.equal(de.continue, 'Weiter');
  for (const copy of [en, de]) {
    assert.doesNotMatch(Object.values(copy.seal).join(' '), /Jeton|crédit|Vous|vous/);
  }
  // German says du, never Sie.
  assert.doesNotMatch(Object.values(de.seal).join(' '), /\b(Sie|Ihr|Ihre|Ihnen)\b/);
});

test('French says tu, and an unknown language falls back to English', () => {
  const fr = rewardMomentCopy('fr');
  assert.equal(fr.seal.title, 'Sceau doré gagné');
  assert.doesNotMatch(Object.values(fr.seal).join(' '), /\b(vous|Vous|votre|vos)\b/);
  assert.equal(rewardMomentCopy(undefined).continue, 'Continue');
});

test('Owner, 2026-10-19: the bonus token pop-up is gone', () => {
  for (const language of ['en', 'de', 'fr']) {
    const copy = rewardMomentCopy(language);
    assert.equal(copy.drafting, undefined);
    assert.equal(copy.logo, undefined);
  }
});
