// WP-99 — «Le facteur et les dépêches»: where a tapped push lands.
//
// A Dépêche opens today's scene, «Le facteur est passé» and a deadline open
// that letter in the Courrier, anything else keeps a safe in-app route, and a
// payload can never send the app to another origin. The service worker's
// copy of the table (`public/sw.js`) is run here against the same cases, so
// the web and native taps land in the same place.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

require('../node_modules/sucrase/register/ts');
const { TODAY_SCENE_ROUTE, pushDeepLink, pushImageOf, pushKindOf, safeInAppRoute } = require('./push-deep-link.ts');

const WEB_ROOT = path.resolve(__dirname, '..');

const CASES = [
  // The morning Dépêche → today's scene.
  [{ kind: 'morning_teaser', route: '/atelier?start=today' }, '/atelier?start=today'],
  [{ kind: 'depeche' }, TODAY_SCENE_ROUTE],
  [{ kind: 'morning_depeche', route: '/vocabulary' }, TODAY_SCENE_ROUTE],
  [{ kind: 'streak_reminder', route: '/atelier?start=today' }, '/atelier?start=today'],
  [{ kind: 'morning_edition', route: '/atelier' }, '/atelier'],
  // «Le facteur est passé» → that letter.
  [{ kind: 'letter_arrived', route: '/missions', mission_id: 'm 7' }, '/missions?mission=m%207'],
  [{ kind: 'letter_arrived', route: '/missions?mission=42' }, '/missions?mission=42'],
  [{ kind: 'facteur', mission_id: 42 }, '/missions?mission=42'],
  [{ kind: 'letter_arrived' }, '/missions'],
  // «Dernier jour pour répondre à Lila» → that letter.
  [{ kind: 'letter_deadline', letter_id: 'l-3' }, '/missions?mission=l-3'],
  [{ kind: 'deadline', route: '/missions?mission=9&from=push' }, '/missions?mission=9&from=push'],
  // Anything else keeps a safe route.
  [{ kind: 'review_reminder', route: '/vocabulary/review' }, '/vocabulary/review'],
  [{ kind: 'review_reminder', route: '//evil.example/x' }, null],
  [{ route: 'https://evil.example' }, null],
  [{ route: '/\\evil.example' }, null],
  [{ route: '/javascript:alert(1)' }, null],
  [{}, null],
];

test('a tapped push lands where its kind says', () => {
  for (const [data, expected] of CASES) {
    assert.equal(pushDeepLink(data), expected, JSON.stringify(data));
  }
  assert.equal(pushDeepLink(null), null);
  assert.equal(pushDeepLink({ kind: 'letter_deadline', route: 'https://evil.example', mission_id: 'm1' }), '/missions?mission=m1');
});

test('the three kinds, and nothing else', () => {
  assert.equal(pushKindOf('morning_teaser'), 'depeche');
  assert.equal(pushKindOf(' Letter_Arrived '), 'letter');
  assert.equal(pushKindOf('letter_deadline'), 'deadline');
  assert.equal(pushKindOf('review_reminder'), 'other');
  assert.equal(pushKindOf(undefined), 'other');
});

test('only in-app paths are trusted', () => {
  assert.equal(safeInAppRoute(' /atelier '), '/atelier');
  assert.equal(safeInAppRoute('atelier'), null);
  assert.equal(safeInAppRoute('//cdn.example'), null);
  assert.equal(safeInAppRoute(42), null);
});

test('the portrait: image_url first, then the older image; only in-app or https', () => {
  assert.equal(pushImageOf({ image_url: '/assets/serial/characters/romy_tremblay/portrait-happy.webp', image: '/old.webp' }),
    '/assets/serial/characters/romy_tremblay/portrait-happy.webp');
  assert.equal(pushImageOf({ image: '/old.webp' }), '/old.webp');
  assert.equal(pushImageOf({ image_url: 'https://cdn.example/p.webp' }), 'https://cdn.example/p.webp');
  assert.equal(pushImageOf({ image_url: 'http://cdn.example/p.webp' }), null);
  assert.equal(pushImageOf({ image_url: '//cdn.example/p.webp' }), null);
  assert.equal(pushImageOf(null), null);
});

function serviceWorker() {
  const listeners = {};
  const shown = [];
  const context = {
    self: {
      addEventListener: (name, fn) => {
        listeners[name] = fn;
      },
      registration: { showNotification: (title, options) => shown.push({ title, options }) },
    },
    clients: { matchAll: () => Promise.resolve([]), openWindow: () => Promise.resolve() },
    Date,
    encodeURIComponent,
    String,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(WEB_ROOT, 'public/sw.js'), 'utf8'), context);
  return { context, listeners, shown };
}

test('the service worker lands in the same place and shows the portrait', () => {
  const { context, listeners, shown } = serviceWorker();
  for (const [data, expected] of CASES) {
    // The worker has no "stay": an unsafe or missing route opens the app root.
    assert.equal(context.deepLink(data), expected ?? '/', `sw: ${JSON.stringify(data)}`);
  }
  listeners.push({
    data: {
      json: () => ({
        title: 'Romy',
        body: 'Le facteur est passé.',
        data: { kind: 'letter_arrived', mission_id: 'm7', image_url: '/assets/serial/characters/romy_tremblay/portrait-happy.webp' },
      }),
    },
    waitUntil: () => {},
  });
  assert.equal(shown.length, 1);
  assert.equal(shown[0].options.icon, '/assets/serial/characters/romy_tremblay/portrait-happy.webp');
  assert.equal(shown[0].options.data.route, '/missions?mission=m7');
});

test('the native listener routes through the table', () => {
  const source = fs.readFileSync(path.join(WEB_ROOT, 'lib/native-push.ts'), 'utf8');
  assert.match(source, /import \{ pushDeepLink \} from '\.\/push-deep-link'/);
  assert.match(source, /const route = pushDeepLink\(data\)/);
});
