// node --test components/atelier-v2/journey/connection-banner.test.js
//
// #794: every sentence the journey says about the connection (an answer did not reach the
// server, is on its way, or is kept on this device) carries `data-connection-banner`, so the
// browser walk can tell a banner from the scene by the element and never by a word. On 14 Nov
// the walk read «Marin: « Tu aides le serveur ? »» (a waiter) as a server banner, because the
// screen's prose was the only thing it had to go on.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};
const stub = (request, exports) => {
  const p = Module._resolveFilename(request, module, false);
  require.cache[p] = { id: p, filename: p, loaded: true, exports: { __esModule: true, ...exports } };
};
stub('@/services/api', { default: {}, apiService: {} });
stub('@/lib/app-auth', {
  useAppSession: () => ({ data: { user: { id: 'learner-1' } }, status: 'authenticated', isNative: false }),
});

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { JourneyFeedbackView, stepKeepsAnswer } = require('./JourneySteps.tsx');
const { ConnectionNotice, JourneySession } = require('./JourneySession.tsx');
const { JourneyTodayCard } = require('./JourneyTodayCard.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const state = require('./journey-state.ts');

const h = React.createElement;
const ATTR = 'data-connection-banner';
const decode = (html) =>
  html.replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/ /g, ' ');

/**
 * The text inside each element that carries the marker, keyed by its value. A balanced walk
 * over the markup, enough for React's static output (no comments, no raw `<` in text).
 */
function banners(html) {
  const out = [];
  const opening = new RegExp(`<([a-z0-9]+)\\b[^>]*\\s${ATTR}="([^"]*)"[^>]*>`, 'g');
  let m;
  while ((m = opening.exec(html))) {
    const [tag, kind] = [m[1], m[2]];
    const tags = new RegExp(`<(/?)${tag}\\b[^>]*?(/?)>`, 'g');
    tags.lastIndex = m.index + m[0].length;
    let depth = 1;
    let end = html.length;
    let t;
    while ((t = tags.exec(html))) {
      if (t[2]) continue;
      depth += t[1] ? -1 : 1;
      if (depth === 0) { end = t.index; break; }
    }
    const text = decode(html.slice(m.index + m[0].length, end).replace(/<[^>]*>/g, '')).trim();
    out.push({ kind, text });
  }
  return out;
}

const controller = (overrides = {}) => ({
  phase: { kind: 'loading' },
  feedback: { kind: 'idle' },
  envelope: null,
  journey: null,
  step: null,
  respondPrompt: null,
  controlLanguage: 'en',
  legacyResume: null,
  progress: state.journeyProgress(null),
  busy: false,
  help: null,
  voice: { kind: 'idle' },
  actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  ...overrides,
});
const noop = () => {};

for (const lang of ['en', 'de', 'fr']) {
  const copy = journeyCopy(lang);

  test(`${lang}: a step's «did not reach the server» is marked as a connection banner`, () => {
    for (const [stepKind, key] of [['recall', 'transport_error'], ['read', 'transport_error_plain']]) {
      assert.equal(stepKeepsAnswer(stepKind) ? 'transport_error' : 'transport_error_plain', key);
      const html = renderToStaticMarkup(h(JourneyFeedbackView, {
        feedback: { kind: 'error', message: 'transport_error', retryable: true },
        copy, stepKind, onContinue: noop, onRetry: noop, onDismiss: noop,
      }));
      assert.ok(decode(html).includes(copy[key]), `${key} is said`);
      assert.deepEqual(banners(html), [{ kind: key, text: copy[key] }],
        `${lang} ${stepKind}: «${copy[key]}» must sit in a [${ATTR}] element`);
    }
  });

  test(`${lang}: the session header's connection notice is marked with its state`, () => {
    for (const kind of ['syncing', 'pending_sync', 'offline_cached', 'offline_empty']) {
      const html = renderToStaticMarkup(h(ConnectionNotice, {
        connection: { state: kind, online: true, readingCache: false, unsent: false, stale: false, lastSyncedAt: null },
        copy,
      }));
      assert.deepEqual(banners(html), [{ kind, text: copy[kind] }], `${lang} ${kind} must carry [${ATTR}="${kind}"]`);
    }
    const live = renderToStaticMarkup(h(ConnectionNotice, {
      connection: { state: 'live', online: true, readingCache: false, unsent: false, stale: false, lastSyncedAt: null },
      copy,
    }));
    assert.equal(live, '', 'a live session says nothing about the connection');
  });

  test(`${lang}: a day that could not load says so in a marked banner, in the session and on Home`, () => {
    const c = controller({ phase: { kind: 'load_failed', message: 'transport_error' }, controlLanguage: lang });
    const session = renderToStaticMarkup(h(JourneySession, { controller: c }));
    const today = renderToStaticMarkup(h(JourneyTodayCard, { controller: c, onOpen: noop }));
    for (const [where, html] of [['session', session], ['home', today]]) {
      const marked = banners(html).filter((b) => b.kind === 'transport_error');
      assert.ok(marked.length === 1 && marked[0].text === copy.transport_error,
        `${lang} ${where}: «${copy.transport_error}» must sit in a [${ATTR}="transport_error"] element, got ${JSON.stringify(banners(html))}`);
    }
  });
}

test('what is not about the connection carries no marker', () => {
  const copy = journeyCopy('en');
  const html = renderToStaticMarkup(h(JourneyFeedbackView, {
    feedback: { kind: 'error', message: 'session_expired', retryable: false },
    copy, stepKind: 'recall', onContinue: noop, onRetry: noop, onDismiss: noop,
  }));
  assert.deepEqual(banners(html), [], 'a sign-in prompt is not a connection banner');
  const session = renderToStaticMarkup(h(JourneySession, { controller: controller() }));
  assert.deepEqual(banners(session), [], 'a loading session has no banner');
});

test('the app and the walk name the same marker', () => {
  const { CONNECTION_BANNER_ATTR } = require('@/lib/connection-banner.ts');
  assert.equal(CONNECTION_BANNER_ATTR, ATTR);
  const driver = fs.readFileSync(path.join(WEB_ROOT, 'e2e/lib/driver.mjs'), 'utf8');
  assert.ok(driver.includes(`[${ATTR}]`), 'e2e/lib/driver.mjs reads the marker the app writes');
});
