// S4 stage 2 — one error path.
//
// `errorToState` turns any failure into {kind, title, body, action} in en, de or
// fr. The axios interceptor in services/api.ts writes no words of its own: the
// guard below fails on any phrase literal in its error handling (main had six
// English toasts and a 429 that said «vous»). The error boundary, 404 and 500
// draw the same StateBlock, and the boundary shows the event id the silent
// reporter sends.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const { errorKind, errorToState, errorToastText, appErrorCopy, newErrorEventId } = require('./app-errors.ts');

const WEB = path.join(__dirname, '..');
const read = (relative) => fs.readFileSync(path.join(WEB, relative), 'utf8');

const axiosError = (status, extra = {}) => ({ isAxiosError: true, response: { status, data: extra.data || {}, headers: extra.headers || {} } });

test('a status, a code or a thrown value maps to one of eight kinds', () => {
  assert.equal(errorKind(axiosError(401)), 'session_expired');
  assert.equal(errorKind(axiosError(403)), 'forbidden');
  assert.equal(errorKind(axiosError(404)), 'not_found');
  assert.equal(errorKind(axiosError(429)), 'rate_limited');
  assert.equal(errorKind(axiosError(500)), 'down');
  assert.equal(errorKind(axiosError(503)), 'down');
  assert.equal(errorKind(axiosError(422)), 'unknown');
  assert.equal(errorKind({ code: 'ECONNABORTED' }), 'slow');
  assert.equal(errorKind({ code: 'ERR_NETWORK' }), 'down');
  assert.equal(errorKind(new Error('boom')), 'unknown');
  assert.equal(errorKind('offline'), 'offline');
  assert.equal(errorKind(404), 'not_found');
});

test('every kind has a title, a sentence and one action in each language', () => {
  const kinds = ['offline', 'slow', 'down', 'not_found', 'forbidden', 'rate_limited', 'session_expired', 'unknown'];
  for (const language of ['en', 'de', 'fr']) {
    for (const kind of kinds) {
      const state = errorToState(kind, language);
      assert.equal(state.kind, kind);
      assert.ok(state.title.trim() && state.body.trim() && state.action.label.trim(), `${language}/${kind}`);
      assert.doesNotMatch(state.body, /\{seconds\}/);
    }
  }
  assert.equal(errorToState('not_found', 'de').action.kind, 'home');
  assert.equal(errorToState('session_expired', 'fr').action.kind, 'sign_in');
  assert.equal(errorToState('down', 'xx').title, appErrorCopy('en').down.title, 'an unknown language falls back to English');
});

test('a 429 says how long to wait, or that the day is spent, with tu and du', () => {
  const wait = errorToState(axiosError(429, { headers: { 'retry-after': '7' }, data: { detail: { code: 'rate_limited' } } }), 'fr');
  assert.equal(wait.body, 'Réessaie dans 7 s.');
  const spent = errorToState(axiosError(429, { data: { detail: { code: 'daily_budget_reached' } } }), 'de');
  assert.equal(spent.title, 'Das war’s für heute');
  for (const language of ['fr', 'de', 'en']) {
    const copy = JSON.stringify(appErrorCopy(language));
    assert.doesNotMatch(copy, /\b(vous|votre|vos|réessayez|Sie|Ihr|Ihre)\b/, language);
  }
});

test('a toast is the title, then the sentence', () => {
  assert.equal(errorToastText(errorToState('offline', 'fr')), 'Hors ligne · Vérifie la connexion, puis réessaie.');
});

test('an event id is short hex, new each time', () => {
  const a = newErrorEventId();
  assert.match(a, /^[0-9a-f]{12}$/);
  assert.notEqual(a, newErrorEventId());
});

/** The response interceptor's error handler in services/api.ts, comments removed. */
function interceptorErrorHandling() {
  const api = read('services/api.ts');
  const start = api.indexOf('this.api.interceptors.response.use(');
  const end = api.indexOf('// Generic HTTP methods', start);
  assert.ok(start > 0 && end > start, 'the response interceptor moved; point this guard at it');
  return api.slice(start, end).replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

test('guard: the interceptor writes no words of its own', () => {
  const handler = interceptorErrorHandling();
  const literals = [...handler.matchAll(/'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`/g)]
    .map((match) => match[1] ?? match[2] ?? match[3]);
  // A phrase is two words with a space between them; codes, paths and headers are not.
  const phrases = literals.filter((literal) => /\p{L}+\s+\p{L}/u.test(literal.replace(/\$\{[^}]*\}/g, '')));
  assert.deepEqual(phrases, [], 'say it through lib/app-errors.ts (errorToState)');
  assert.doesNotMatch(handler, /toast(\.\w+)?\(\s*['"`]/, 'a toast with a literal string');
  assert.match(handler, /errorToState\(error, chromeLanguage\(readLearnerLanguage\(\), readLearnerLevel\(\)\)\)/);
});

test('guard: no toast with a literal string anywhere in services/api.ts', () => {
  assert.doesNotMatch(read('services/api.ts'), /toast(\.\w+)?\(\s*['"`]/);
});

test('the boundary, 404 and 500 draw the one error screen with a way back to La Une', () => {
  const app = read('pages/_app.tsx');
  assert.match(app, /<AppErrorBoundary report=\{reportClientCrash\}/);
  // The id on the screen is the id in the report.
  assert.match(app, /event_id: eventId/);
  assert.match(app, /return eventId;/);
  const boundary = read('components/layout/AppErrorBoundary.tsx');
  assert.match(boundary, /const eventId = this\.props\.report\(/);
  assert.match(boundary, /<ErrorScreen kind="crashed" eventId=\{this\.state\.eventId\}/);
  const screen = read('components/layout/ErrorScreen.tsx');
  assert.match(screen, /<StateBlock/);
  assert.match(screen, /label: copy\.actions\.home/);
  assert.match(read('pages/404.tsx'), /<ErrorScreen kind="not_found" \/>/);
  assert.match(read('pages/500.tsx'), /<ErrorScreen kind="down" \/>/);
  for (const file of ['components/layout/ErrorScreen.tsx', 'pages/404.tsx', 'pages/500.tsx']) {
    const source = read(file).replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    // JSX text between tags would be untranslated words.
    assert.doesNotMatch(source, />\s*[A-Za-z][a-z]+\s+[a-z]+[^<{]*</, `${file} prints words of its own`);
  }
});
