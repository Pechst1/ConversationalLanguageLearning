// WP-72 — what the iPhone bundle may contain, and proof that it does.
//
// 1. Dev/QA pages never ship in the native export. `next export` has no
//    per-build page exclusion, so build-native.mjs prunes the exported HTML,
//    the page's own JS chunk and its data file right after `next build`, then
//    asserts nothing excluded is left. The list is route prefixes, so a new
//    `/dev/*` page is covered without touching this file.
// 2. Every native build writes `native-build.json` next to index.html: the API
//    host, the push flags and the legal version the bundle was built with.
//    `verify-native-bundle.mjs --release` (run by the fastlane archive lane on
//    ios/App/App/public) reads it back and refuses anything but an HTTPS,
//    non-local, non-placeholder API with production push.
import { existsSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { resolveNativeApiEnvironment } from './native-api-env.mjs';

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

export const NATIVE_BUILD_MANIFEST = 'native-build.json';

/** Always excluded from the native export. */
export const DEV_ONLY_ROUTE_PREFIXES = ['/mobile-visual-qa', '/atelier-v2-gallery', '/dev'];
/** Parked behind `launch-flags.json#storyFeatureVisible`; excluded while it is off. */
export const FLAGGED_ROUTE_PREFIXES = ['/bibliotheque'];

export function readLaunchFlags() {
  return JSON.parse(readFileSync(path.join(webRoot, 'launch-flags.json'), 'utf8'));
}

export function excludedRoutePrefixes(flags = readLaunchFlags()) {
  return [...DEV_ONLY_ROUTE_PREFIXES, ...(flags.storyFeatureVisible ? [] : FLAGGED_ROUTE_PREFIXES)];
}

export function isExcludedRoute(route, prefixes = excludedRoutePrefixes()) {
  const normalized = `/${String(route).replace(/^\/+/, '').replace(/\/+$/, '')}`;
  return prefixes.some((prefix) => normalized === prefix || normalized.startsWith(`${prefix}/`));
}

function walk(dir, visit, relative = '') {
  if (!existsSync(dir)) return;
  for (const name of readdirSync(dir)) {
    const absolute = path.join(dir, name);
    const rel = relative ? `${relative}/${name}` : name;
    const isDir = statSync(absolute).isDirectory();
    if (visit(absolute, rel, isDir) === 'skip') continue;
    if (isDir) walk(absolute, visit, rel);
  }
}

/** The route a file or directory in the export belongs to, or null for shared assets. */
export function routeForExportPath(rel, isDir) {
  const parts = rel.split('/');
  if (parts[0] === '_next') {
    // _next/static/chunks/pages/<route>-<hash>.js  (or a directory of them)
    const pagesAt = rel.indexOf('/chunks/pages/');
    if (parts[1] === 'static' && pagesAt !== -1) {
      const tail = rel.slice(pagesAt + '/chunks/pages/'.length);
      return isDir ? tail : tail.replace(/-[0-9a-f]{8,}\.js(\.map)?$/, '').replace(/\.js(\.map)?$/, '');
    }
    // _next/data/<buildId>/<route>.json  (or a directory of them)
    if (parts[1] === 'data' && parts.length > 3) {
      const tail = parts.slice(3).join('/');
      return isDir ? tail : tail.replace(/\.json$/, '');
    }
    return null;
  }
  if (isDir) return rel;
  if (rel.endsWith('/index.html')) return rel.slice(0, -'/index.html'.length);
  if (rel.endsWith('.html')) return rel.slice(0, -'.html'.length);
  return null;
}

/** Every path in `dir` that belongs to an excluded route (outermost only). */
export function findExcludedPaths(dir, prefixes = excludedRoutePrefixes()) {
  const found = [];
  walk(dir, (absolute, rel, isDir) => {
    const route = routeForExportPath(rel, isDir);
    if (route !== null && route !== '' && isExcludedRoute(route, prefixes)) {
      found.push(rel);
      return 'skip';
    }
    return undefined;
  });
  return found;
}

export function pruneNativeExport(dir, prefixes = excludedRoutePrefixes()) {
  const removed = findExcludedPaths(dir, prefixes);
  for (const rel of removed) rmSync(path.join(dir, rel), { recursive: true, force: true });
  const left = findExcludedPaths(dir, prefixes);
  if (left.length) throw new Error(`Native export still contains excluded pages: ${left.join(', ')}`);
  return removed;
}

function legalVersion() {
  try {
    return JSON.parse(readFileSync(path.join(webRoot, 'lib', 'legal-content.json'), 'utf8')).version;
  } catch {
    return null;
  }
}

export function nativeBuildManifest(env = process.env, prefixes = excludedRoutePrefixes()) {
  return {
    builtAt: new Date().toISOString(),
    apiBaseUrl: env.NEXT_PUBLIC_API_BASE_URL || env.NEXT_PUBLIC_API_URL || null,
    wsUrl: env.NEXT_PUBLIC_WS_URL || null,
    nativePushEnabled: env.NEXT_PUBLIC_NATIVE_PUSH_ENABLED === 'true',
    apnsEnvironment: env.NEXT_PUBLIC_APNS_ENVIRONMENT || null,
    allowLocalApi: env.ALLOW_LOCAL_NATIVE_API === 'true',
    allowPlaceholderApi: env.ALLOW_PLACEHOLDER_NATIVE_API === 'true',
    excludedRoutePrefixes: prefixes,
    legalVersion: legalVersion(),
  };
}

export function writeNativeBuildManifest(dir, env = process.env, prefixes = excludedRoutePrefixes()) {
  const manifest = nativeBuildManifest(env, prefixes);
  writeFileSync(path.join(dir, NATIVE_BUILD_MANIFEST), `${JSON.stringify(manifest, null, 2)}\n`);
  return manifest;
}

/**
 * The release contract for an App Store / TestFlight build, checked on the
 * environment before a build (fail fast) and on the manifest after it.
 */
export function releaseProblems(settings) {
  const problems = [];
  const apiBaseUrl = settings.apiBaseUrl;
  if (settings.allowLocalApi) problems.push('ALLOW_LOCAL_NATIVE_API is set.');
  if (settings.allowPlaceholderApi) problems.push('ALLOW_PLACEHOLDER_NATIVE_API is set.');
  if (!apiBaseUrl) {
    problems.push('No API URL (NEXT_PUBLIC_API_BASE_URL).');
  } else {
    try {
      // Without the ALLOW_* escape hatches this refuses http, localhost,
      // 127.0.0.1/::1 and example.com hosts, and a non-wss WebSocket.
      resolveNativeApiEnvironment({
        NEXT_PUBLIC_API_BASE_URL: apiBaseUrl,
        ...(settings.wsUrl ? { NEXT_PUBLIC_WS_URL: settings.wsUrl } : {}),
      });
    } catch (error) {
      problems.push(error instanceof Error ? error.message : String(error));
    }
  }
  if (settings.nativePushEnabled !== true) problems.push('NEXT_PUBLIC_NATIVE_PUSH_ENABLED is not "true".');
  if (settings.apnsEnvironment !== 'production') {
    problems.push(`NEXT_PUBLIC_APNS_ENVIRONMENT is "${settings.apnsEnvironment ?? ''}", not "production".`);
  }
  return problems;
}

function jsFilesUnder(dir) {
  const files = [];
  walk(path.join(dir, '_next', 'static'), (absolute, rel, isDir) => {
    if (!isDir && rel.endsWith('.js')) files.push(absolute);
  });
  return files;
}

/** Everything `verify-native-bundle.mjs` checks, returned rather than thrown. */
export function verifyNativeBundle(dir, { release = false } = {}) {
  const problems = [];
  const manifestPath = path.join(dir, NATIVE_BUILD_MANIFEST);
  if (!existsSync(path.join(dir, 'index.html'))) problems.push(`${dir} has no index.html — not a native export.`);
  if (!existsSync(manifestPath)) {
    problems.push(`${NATIVE_BUILD_MANIFEST} is missing — build with npm run build:native.`);
    return problems;
  }
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const excluded = findExcludedPaths(dir, manifest.excludedRoutePrefixes || excludedRoutePrefixes());
  if (excluded.length) problems.push(`Excluded pages are in the bundle: ${excluded.join(', ')}`);

  const scripts = jsFilesUnder(dir).map((file) => readFileSync(file, 'utf8'));
  if (manifest.apiBaseUrl && !scripts.some((source) => source.includes(manifest.apiBaseUrl))) {
    problems.push(`The API URL ${manifest.apiBaseUrl} is not inlined in any bundled script.`);
  }
  if (release) {
    problems.push(...releaseProblems(manifest));
    if (scripts.some((source) => /https?:\/\/api\.example\.com/.test(source))) {
      problems.push('A bundled script still names api.example.com.');
    }
  }
  return problems;
}
