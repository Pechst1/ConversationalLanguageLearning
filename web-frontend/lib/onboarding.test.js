// WP-75 — «A win before an account».
//
// Pins the pure halves of the signed-out flow: the taste grades locally and
// exactly, the language guess follows the browser, the sign-up payload is the
// backend contract (starting_point, no confirm field), and a new account lands
// in today's scene rather than on the placement. Also checks that every cast
// portrait the UI can ask for exists on disk.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const {
  TASTE_ITEMS,
  TASTE_COPY,
  gradeChoice,
  gradeTiles,
  moodForVerdict,
  tilesSentence,
} = require('./onboarding-taste.ts');
const { detectOnboardingLanguage, onboardingLanguageOf } = require('./onboarding-locale.ts');
const {
  AFTER_SIGNUP_DESTINATION,
  SIGNUP_COPY,
  afterSignUpDestination,
  buildRegisterPayload,
  validateSignUp,
} = require('./onboarding-signup.ts');
const { CAST_WITH_PORTRAITS, PORTRAIT_MOODS, portraitSrc, portraitInitial } = require('./onboarding-portraits.ts');

const LANGUAGES = ['en', 'de', 'fr'];
const choice = TASTE_ITEMS.find((item) => item.kind === 'choice');
const tiles = TASTE_ITEMS.find((item) => item.kind === 'tiles');

// --- taste grading ---------------------------------------------------------

test('the taste is two small items: one choice, one tile build', () => {
  assert.equal(TASTE_ITEMS.length, 2);
  assert.equal(TASTE_ITEMS[0].kind, 'choice');
  assert.equal(TASTE_ITEMS[1].kind, 'tiles');
});

test('the choice is right only for «Bonjour !»', () => {
  assert.equal(choice.options.length, 3);
  assert.equal(choice.options.find((o) => o.id === choice.answerId).fr, 'Bonjour !');
  assert.equal(gradeChoice(choice, null), 'pending');
  assert.equal(gradeChoice(choice, 'bonjour'), 'correct');
  assert.equal(gradeChoice(choice, 'merci'), 'wrong');
  assert.equal(gradeChoice(choice, 'au-revoir'), 'wrong');
  // The answer is not the first option, so tapping blindly is not a win.
  assert.notEqual(choice.options[0].id, choice.answerId);
});

test('tiles grade the moment the sentence is complete, in order', () => {
  assert.equal(gradeTiles(tiles, []), 'pending');
  assert.equal(gradeTiles(tiles, ['cafe']), 'pending');
  assert.equal(gradeTiles(tiles, ['cafe', 'svp']), 'correct');
  assert.equal(gradeTiles(tiles, ['svp', 'cafe']), 'wrong');
  assert.equal(gradeTiles(tiles, ['cafe', 'merci']), 'wrong');
  assert.equal(gradeTiles(tiles, ['cafe', 'svp', 'merci']), 'wrong');
  assert.equal(tilesSentence(tiles, ['cafe', 'svp']), 'Un café, s’il vous plaît');
});

test('the portrait follows the verdict', () => {
  assert.equal(moodForVerdict('pending'), 'neutral');
  assert.equal(moodForVerdict('correct'), 'happy');
  assert.equal(moodForVerdict('wrong'), 'cross');
});

test('every taste line and instruction exists in en/de/fr', () => {
  for (const item of TASTE_ITEMS) {
    for (const language of LANGUAGES) {
      assert.ok(item.task[language]?.trim(), `${item.id} task ${language}`);
      assert.ok(item.line.native[language]?.trim(), `${item.id} line ${language}`);
      assert.ok(item.reply.native[language]?.trim(), `${item.id} reply ${language}`);
    }
  }
  const keys = Object.keys(TASTE_COPY.en).sort();
  for (const language of LANGUAGES) assert.deepEqual(Object.keys(TASTE_COPY[language]).sort(), keys);
});

test('the promise is at most twelve words in every language', () => {
  for (const language of LANGUAGES) {
    const words = TASTE_COPY[language].promise.split(/\s+/).filter(Boolean);
    assert.ok(words.length <= 12, `${language}: ${words.length} words`);
  }
});

// --- locale detection ------------------------------------------------------

test('the first browser language we speak wins', () => {
  assert.equal(detectOnboardingLanguage(['de-AT', 'en-US']), 'de');
  assert.equal(detectOnboardingLanguage(['fr-CA']), 'fr');
  assert.equal(detectOnboardingLanguage(['es-ES', 'de-DE', 'en']), 'de');
  assert.equal(detectOnboardingLanguage(['en_GB']), 'en');
  assert.equal(detectOnboardingLanguage(['ja', 'pt-BR']), 'en');
  assert.equal(detectOnboardingLanguage([]), 'en');
  assert.equal(detectOnboardingLanguage(undefined), 'en');
  assert.equal(onboardingLanguageOf('DE'), 'de');
  assert.equal(onboardingLanguageOf(42), null);
});

// --- sign-up payload -------------------------------------------------------

test('the register payload is the contract: starting_point, language, no confirm', () => {
  const payload = buildRegisterPayload({
    email: '  Lea@Example.fr ',
    password: 'motdepasse',
    firstName: ' Léa ',
    startingPoint: 'some',
    language: 'de',
  });
  assert.deepEqual(payload, {
    email: 'lea@example.fr',
    password: 'motdepasse',
    full_name: 'Léa',
    native_language: 'de',
    starting_point: 'some',
  });
  for (const forbidden of ['confirmPassword', 'confirm_password', 'proficiency_level', 'daily_goal_minutes']) {
    assert.ok(!(forbidden in payload), `${forbidden} must not be sent`);
  }
});

test('an empty first name is left out, not sent blank', () => {
  const payload = buildRegisterPayload({
    email: 'a@b.fr',
    password: 'motdepasse',
    firstName: '   ',
    startingPoint: 'new',
    language: 'en',
  });
  assert.ok(!('full_name' in payload));
  assert.equal(payload.starting_point, 'new');
});

test('validation: email, 8 characters, 72 bytes, and the one question', () => {
  const base = { email: 'a@b.fr', password: 'motdepasse', firstName: '', startingPoint: 'new', language: 'fr' };
  assert.deepEqual(validateSignUp(base), {});
  assert.equal(validateSignUp({ ...base, email: '' }).email, 'email_required');
  assert.equal(validateSignUp({ ...base, email: 'nope' }).email, 'email_invalid');
  assert.equal(validateSignUp({ ...base, password: 'court' }).password, 'password_short');
  // 40 × «é» is 40 characters but 80 bytes: refused like the server refuses it.
  assert.equal(validateSignUp({ ...base, password: 'é'.repeat(40) }).password, 'password_long');
  assert.equal(validateSignUp({ ...base, password: 'a'.repeat(72) }).password, undefined);
  assert.equal(validateSignUp({ ...base, startingPoint: null }).startingPoint, 'starting_point_required');
  for (const language of LANGUAGES) {
    for (const code of ['email_required', 'email_invalid', 'password_short', 'password_long', 'starting_point_required']) {
      assert.ok(SIGNUP_COPY[language].errors[code], `${language}.${code}`);
    }
  }
});

test('the question is «Votre français ?» with three answers', () => {
  assert.equal(SIGNUP_COPY.fr.level_question, 'Votre français ?');
  assert.deepEqual(SIGNUP_COPY.fr.levels, { new: 'Nouveau', some: 'Quelques bases', comfortable: 'À l’aise' });
});

// --- redirect target -------------------------------------------------------

test('a new account lands in today’s scene, never on the placement', () => {
  assert.equal(AFTER_SIGNUP_DESTINATION, '/atelier?start=today');
  assert.equal(afterSignUpDestination('/atelier'), '/atelier?start=today');
  assert.equal(afterSignUpDestination(undefined), '/atelier?start=today');
  assert.equal(afterSignUpDestination('/placement'), '/atelier?start=today');
  // A deep link keeps its own destination.
  assert.equal(afterSignUpDestination('/vocabulary'), '/vocabulary');
});

test('the sign-up page sends the learner to that destination', () => {
  const page = fs.readFileSync(path.join(__dirname, '..', 'pages', 'auth', 'signup.tsx'), 'utf8');
  assert.ok(page.includes('afterSignUpDestination(destination)'));
  assert.ok(page.includes('router.replace(landing)'));
  assert.ok(!page.includes("'/placement'"));
  assert.ok(!/confirm/i.test(page.replace(/\/\*[\s\S]*?\*\//g, '')), 'no confirm-password field');
});

// --- portraits -------------------------------------------------------------

test('every portrait the UI can ask for exists', () => {
  const root = path.join(__dirname, '..', 'public');
  for (const id of CAST_WITH_PORTRAITS) {
    for (const mood of PORTRAIT_MOODS) {
      const src = portraitSrc(id, mood);
      assert.equal(src, `/assets/serial/characters/${id}/portrait-${mood}.webp`);
      assert.ok(fs.existsSync(path.join(root, src)), `${src} is missing`);
    }
  }
  assert.equal(portraitSrc('user', 'neutral'), null, 'the learner is never drawn');
  assert.equal(portraitSrc('../etc', 'neutral'), null);
  assert.equal(portraitInitial('Romy'), 'R');
  assert.equal(portraitInitial('', 'lila_bonnet'), 'L');
});
