// node --test e2e/lib/french-screen.test.mjs
//
// The B1 walk's `no-english-on-french-b1` (owner approval, 19 Nov 2026): from B1 the chrome
// is French, an explanation is in the learner's mother tongue and marked `lang`. Only text
// marked as the walker's own language is set aside; unmarked English still fails.
import assert from 'node:assert/strict';
import test from 'node:test';

import { englishOnFrenchScreen, unmarkedText } from './assertions.mjs';

const RULE_EN = 'After pour, sans and avant de, French uses the infinitive, never an -ing form.';
const screen = (marked) => ({
  nonFrText: `Règle Traduire ${RULE_EN} Pourquoi ? Essayer Je connais déjà — vérifier`,
  marked,
});

test('unmarked English on a French screen is a finding', () => {
  const result = englishOnFrenchScreen(screen([]), 'en');
  assert.equal(result.ok, false);
  assert.ok(result.words.includes('the') || result.words.includes('and'), result.words.join(','));
  assert.match(result.around, /infinitive/);
});

test('English marked lang="en" is set aside for an English learner', () => {
  const result = englishOnFrenchScreen(screen([{ lang: 'en', text: RULE_EN }]), 'en');
  assert.equal(result.ok, true, result.words.join(','));
});

test('English marked lang="en" still counts for a German learner', () => {
  const result = englishOnFrenchScreen(screen([{ lang: 'en', text: RULE_EN }]), 'de');
  assert.equal(result.ok, false);
});

test('a German explanation marked for a German learner is set aside; the rest stays', () => {
  const text = 'Pas encore Ce qui ne va pas Nach pour steht der Infinitiv. Réessayer';
  assert.equal(
    unmarkedText(text, [{ lang: 'de', text: 'Nach pour steht der Infinitiv.' }], 'de'),
    'Pas encore Ce qui ne va pas Réessayer',
  );
  // Regional codes are folded by the driver; another language's mark is never removed.
  assert.equal(unmarkedText(text, [{ lang: 'en', text: 'Nach pour steht der Infinitiv.' }], 'de'), text);
});

test('an old snapshot without marks reads as before', () => {
  assert.equal(englishOnFrenchScreen({ nonFrText: 'Bien joué ! Continuer' }, 'en').ok, true);
  assert.equal(englishOnFrenchScreen({ nonFrText: `${RULE_EN}` }, 'en').ok, false);
});
