// S4 stage 1 — the register of places (lib/places.ts) is the one list of what a
// learner can open and from where. This fails when:
//   · a file in pages/ is not in the register (or the register names a page that is gone);
//   · a learner place has no entry point, or an entry file no longer holds the route;
//   · a dev place could reach a release build (not `notFound` in production, not
//     pruned from the native export, or linked from a file that ships);
//   · next.config.js's legacy redirects, the native prune list, RouteAuthGate or the
//     tab bar disagree with the register.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const { PLACES, LEGACY_PATHS, placeFor, publicRoutes, guestOnlyRoutes } = require('./places.ts');
const { PHONE_PRODUCT_TABS, routeUsesOwnProductShell, isSettingsRoute } = require('./product-shell.ts');

const WEB = path.join(__dirname, '..');
const REPO = path.join(WEB, '..');
const read = (relative) => fs.readFileSync(path.join(REPO, relative), 'utf8');

/** Next's own files and the API routes are not places. */
const FRAMEWORK = /^(_app|_document|_error|api\/.*)$/;

function pageRoutes() {
  const routes = [];
  const walk = (dir, rel = '') => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const childRel = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) walk(path.join(dir, entry.name), childRel);
      else if (/\.(tsx|ts|jsx|js)$/.test(entry.name)) {
        const stem = childRel.replace(/\.(tsx|ts|jsx|js)$/, '');
        if (FRAMEWORK.test(stem)) continue;
        routes.push(`/${stem.replace(/(^|\/)index$/, '')}`.replace(/\/$/, '') || '/');
      }
    }
  };
  walk(path.join(WEB, 'pages'));
  return routes.sort();
}

function pageFile(route) {
  const base = path.join(WEB, 'pages', route === '/' ? 'index' : route.slice(1));
  for (const candidate of [`${base}.tsx`, `${base}/index.tsx`]) if (fs.existsSync(candidate)) return candidate;
  return null;
}

/** The part of a route a link can spell out: up to the first dynamic segment. */
const staticPrefix = (route) => route.split('[')[0];
const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function holdsRoute(source, route) {
  const prefix = staticPrefix(route);
  if (prefix !== route) return source.includes(prefix);
  // A quoted literal or the start of a template: '/mur', "/mur?x", `/mur/${id}`.
  return new RegExp(`['"\`]${escape(route)}(?=['"\`?#/$])`).test(source);
}

test('every page file is in the register, and every place is a page file', () => {
  const pages = pageRoutes();
  const registered = PLACES.map((place) => place.route).sort();
  const missing = pages.filter((route) => !placeFor(route));
  const stale = registered.filter((route) => !pages.includes(route));
  assert.deepEqual(missing, [], `pages without a row in lib/places.ts: ${missing.join(', ')}`);
  assert.deepEqual(stale, [], `rows in lib/places.ts without a page: ${stale.join(', ')}`);
  assert.equal(new Set(registered).size, registered.length, 'a route is registered twice');
});

test('every place has a name in each language, a kind and a parent that exists', () => {
  for (const place of PLACES) {
    for (const language of ['en', 'de', 'fr']) assert.ok(String(place.name[language] || '').trim(), `${place.route} has no ${language} name`);
    if (place.parent) assert.ok(placeFor(place.parent), `${place.route}'s parent ${place.parent} is not a place`);
    if (place.kind === 'child' || place.kind === 'step' || place.kind === 'alias') {
      assert.ok(place.parent, `${place.route} is a ${place.kind} with no parent`);
    }
    if (place.kind === 'alias') assert.ok(placeFor(place.forwardsTo || ''), `${place.route} forwards to nothing registered`);
    else assert.equal(place.forwardsTo, undefined, `${place.route} forwards but is not an alias`);
  }
});

test('every learner place has an entry point, and every entry file still holds the route', () => {
  const problems = [];
  for (const place of PLACES) {
    if (place.kind === 'dev') continue;
    if (place.kind !== 'alias' && !place.entries.length) problems.push(`${place.route} has no entry point`);
    for (const entry of place.entries) {
      if (!('file' in entry)) continue;
      const absolute = path.join(REPO, entry.file);
      if (!fs.existsSync(absolute)) {
        problems.push(`${place.route}: entry ${entry.file} does not exist`);
        continue;
      }
      const source = fs.readFileSync(absolute, 'utf8');
      const found = entry.needle ? source.includes(entry.needle) : holdsRoute(source, place.route);
      if (!found) problems.push(`${place.route}: ${entry.file} no longer links to it`);
    }
  }
  assert.deepEqual(problems, []);
});

test('a dev place cannot reach a release build', async () => {
  const { DEV_ONLY_ROUTE_PREFIXES, isExcludedRoute } = await import('../scripts/native-export-policy.mjs');
  const dev = PLACES.filter((place) => place.kind === 'dev');
  const problems = [];
  for (const place of dev) {
    if (place.gate.kind !== 'dev_build') problems.push(`${place.route} is dev but its gate is ${place.gate.kind}`);
    const source = fs.readFileSync(pageFile(place.route), 'utf8');
    if (!/NODE_ENV === 'production'\)\s*{\s*return { notFound: true }/.test(source)) {
      problems.push(`${place.route} is built in production (getStaticProps must return notFound)`);
    }
    if (!isExcludedRoute(place.route, DEV_ONLY_ROUTE_PREFIXES)) {
      problems.push(`${place.route} is not pruned from the native export (scripts/native-export-policy.mjs)`);
    }
  }
  // The prune list names only dev places, and none of them a learner place.
  for (const prefix of DEV_ONLY_ROUTE_PREFIXES) {
    if (!dev.some((place) => isExcludedRoute(place.route, [prefix]))) problems.push(`prune prefix ${prefix} names no dev place`);
    for (const place of PLACES) {
      if (place.kind !== 'dev' && isExcludedRoute(place.route, [prefix])) problems.push(`prune prefix ${prefix} removes ${place.route}`);
    }
  }
  // No file that ships links to a dev place: dev pages and gallery fixtures may.
  const devFiles = new Set(dev.map((place) => pageFile(place.route)));
  const shipping = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== '__fixtures__' && entry.name !== 'node_modules') walk(full);
      } else if (/\.(tsx?|jsx?)$/.test(entry.name) && !/\.test\./.test(entry.name) && !devFiles.has(full)) {
        shipping.push(full);
      }
    }
  };
  for (const dir of ['pages', 'components', 'lib', 'hooks', 'services']) walk(path.join(WEB, dir));
  for (const full of shipping) {
    const source = fs.readFileSync(full, 'utf8');
    for (const place of dev) {
      if (new RegExp(`(href=|push\\(|replace\\()\\s*\\{?\\s*['"\`]${escape(place.route)}(?=['"\`?#/])`).test(source)) {
        problems.push(`${path.relative(WEB, full)} links to dev place ${place.route}`);
      }
    }
  }
  assert.deepEqual(problems, []);
});

test('the native prune list parks exactly the story places behind their flag', async () => {
  const { FLAGGED_ROUTE_PREFIXES, isExcludedRoute } = await import('../scripts/native-export-policy.mjs');
  const story = PLACES.filter((place) => place.gate.kind === 'launch_flag' && place.gate.flag === 'storyFeatureVisible');
  for (const place of PLACES) {
    assert.equal(isExcludedRoute(place.route, FLAGGED_ROUTE_PREFIXES), story.includes(place), place.route);
  }
});

test("next.config.js's legacy redirects are the register's, and each lands on a place", async () => {
  const previous = process.env.NATIVE_STATIC_EXPORT;
  delete process.env.NATIVE_STATIC_EXPORT;
  const warn = console.warn;
  console.warn = () => {};
  let redirects;
  try {
    const configPath = path.join(WEB, 'next.config.js');
    delete require.cache[configPath];
    redirects = await require(configPath).redirects();
  } finally {
    console.warn = warn;
    if (previous !== undefined) process.env.NATIVE_STATIC_EXPORT = previous;
  }
  const flags = JSON.parse(read('web-frontend/launch-flags.json'));
  const sources = redirects.map((redirect) => redirect.source);
  // Pages parked behind a flag that is off are redirected too; they are places, not legacy paths.
  const legacy = sources.filter((source) => !placeFor(source.replace(/\/:path\*$/, '')));
  assert.deepEqual([...new Set(legacy)].sort(), [...LEGACY_PATHS].sort());
  for (const { source, destination } of redirects) {
    const target = destination.split('?')[0].replace(/\/:[^/]+\*?$/, '').replace(/\/:[^/]+/g, '/[x]');
    const landed = PLACES.some((place) => place.route.replace(/\[[^\]]+\]/g, '[x]') === target);
    assert.ok(landed, `${source} → ${destination} lands on no place`);
    const page = placeFor(source);
    if (page) {
      assert.ok(page.gate.kind === 'launch_flag' && !flags[page.gate.flag], `${source} is a page and is redirected away`);
    }
  }
});

test('RouteAuthGate, the tab bar and the shells read the register', () => {
  const pub = new Set(publicRoutes());
  for (const route of guestOnlyRoutes()) assert.ok(pub.has(route), `${route} is guest-only but not public`);
  for (const place of PLACES) {
    if (place.kind === 'legal') assert.equal(place.access, 'public', place.route);
    if (['tab', 'child', 'step'].includes(place.kind)) assert.equal(place.access, 'signed_in', place.route);
  }
  const gate = read('web-frontend/components/auth/RouteAuthGate.tsx');
  assert.match(gate, /new Set\(publicRoutes\(\)\)/);
  assert.match(gate, /new Set\(guestOnlyRoutes\(\)\)/);
  assert.doesNotMatch(gate, /'\/(privacy|terms|cameo-gallery|mobile-visual-qa)'/, 'RouteAuthGate lists routes by hand again');

  const tabs = PLACES.filter((place) => place.kind === 'tab');
  assert.deepEqual(PHONE_PRODUCT_TABS.map((tab) => tab.href).sort(), tabs.map((place) => place.route).sort());
  for (const tab of PHONE_PRODUCT_TABS) {
    assert.equal(tab.label, placeFor(tab.href).name.fr);
    for (const route of tab.activeRoutes) assert.equal(placeFor(route).section, tab.id, route);
  }
  for (const place of PLACES.filter((p) => p.kind !== 'dev')) {
    assert.equal(routeUsesOwnProductShell(place.route), Boolean(place.ownShell) && (place.gate.kind !== 'launch_flag' || place.gate.flag !== 'storyFeatureVisible' || JSON.parse(read('web-frontend/launch-flags.json')).storyFeatureVisible), place.route);
  }
  for (const route of ['/settings', '/dossier', '/repetition']) assert.ok(isSettingsRoute(route), route);
  assert.equal(isSettingsRoute('/pilot-ops'), false);
});

test('/pilot-ops checks the role on the client before it asks for the reports', () => {
  const page = read('web-frontend/pages/pilot-ops.tsx');
  assert.equal(placeFor('/pilot-ops').gate.kind, 'role');
  assert.match(page, /role === 'admin'/);
  assert.ok(page.indexOf("role === 'admin'") < page.indexOf('getPilotOperations('), 'the guard must run before the reports load');
});
