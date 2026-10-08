// node --test lib/auth-copy.test.js
//
// 2026-09-24 — sign-in and password reset follow the one-language rule. Before
// an account exists they read the onboarding language (en/de/fr), like sign-up.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { AUTH_COPY, authCopy, authFill, signInErrorText } = require('./auth-copy.ts');

const flat = (value, prefix = '') =>
  typeof value === 'string'
    ? [[prefix, value]]
    : Object.entries(value).flatMap(([k, v]) => flat(v, prefix ? `${prefix}.${k}` : k));

test('en, de and fr tables are complete and fill the same holes', () => {
  const fr = Object.fromEntries(flat(AUTH_COPY.fr));
  const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
  for (const language of ['en', 'de']) {
    const table = Object.fromEntries(flat(AUTH_COPY[language]));
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
    }
  }
});

test('a newcomer reads the chrome in their language', () => {
  assert.equal(authCopy('en').signin.submit, 'Sign in');
  assert.equal(authCopy('de').reset.send, 'Code anfordern');
  assert.equal(authCopy('fr').reset.back_to_sign_in, 'Retour à la connexion');
  assert.equal(authCopy('xx').signin.submit, 'Sign in');
  assert.equal(
    authFill(authCopy('en').reset.code_lead, { email: 'a@b.c' }),
    'If a@b.c has an account, the code is on its way. Valid for 15 minutes.',
  );
  assert.equal(signInErrorText(authCopy('de').signin, 'email_invalid'), 'Diese E-Mail scheint falsch.');
  assert.equal(signInErrorText(authCopy('en').signin, undefined), undefined);
});

test('the pages read the table and carry no inline French chrome', () => {
  for (const name of ['signin.tsx', 'forgot-password.tsx']) {
    const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/auth', name), 'utf8');
    assert.ok(page.includes("from '@/lib/auth-copy'"), `${name} imports the copy module`);
    assert.ok(page.includes('useOnboardingLanguage()'), `${name} reads the onboarding language`);
    const code = page.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    for (const [key, phrase] of flat(AUTH_COPY.fr)) {
      if (phrase.length < 5) continue;
      for (const quoted of [`'${phrase}'`, `"${phrase}"`, `>${phrase}<`]) {
        assert.ok(!code.includes(quoted), `${name}: inline French ${key}`);
      }
    }
    assert.ok(page.includes('{AUTH_EYEBROW}'), `${name}: the nameplate line is shared, not inline`);
    for (const phrase of ['Se connecter', 'Mot de passe', 'Réessayez', 'Adresse e-mail', 'Quotidien de français']) {
      assert.ok(!code.includes(phrase), `${name}: inline French «${phrase}»`);
    }
  }
});
