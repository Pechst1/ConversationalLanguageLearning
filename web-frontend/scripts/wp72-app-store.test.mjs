// WP-72 «App Store–ready» — the static contract of the iOS shell, the legal
// pages and the native export. Run: npm run test:app-store
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, existsSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  excludedRoutePrefixes,
  findExcludedPaths,
  isExcludedRoute,
  pruneNativeExport,
  releaseProblems,
  verifyNativeBundle,
  writeNativeBuildManifest,
} from './native-export-policy.mjs';

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const appDir = path.join(webRoot, 'ios', 'App', 'App');
const read = (...parts) => readFileSync(path.join(webRoot, ...parts), 'utf8');

/** Top-level keys of an XML plist → raw value XML (enough for these checks). */
function plistKeys(xml) {
  const body = xml.slice(xml.indexOf('<dict>') + '<dict>'.length);
  const keys = new Map();
  const pattern = /<key>([^<]+)<\/key>\s*(<string>[^<]*<\/string>|<true\/>|<false\/>|<array>[\s\S]*?<\/array>)/g;
  let match;
  while ((match = pattern.exec(body))) keys.set(match[1], match[2]);
  return keys;
}

const stringValue = (raw) => raw?.replace(/^<string>|<\/string>$/g, '');

test('Info.plist: one name, camera/photo/mic strings, no unused speech string, export compliance', () => {
  const keys = plistKeys(read('ios', 'App', 'App', 'Info.plist'));
  assert.equal(stringValue(keys.get('CFBundleDisplayName')), 'L’Atelier');
  assert.equal(keys.get('ITSAppUsesNonExemptEncryption'), '<false/>');
  for (const key of ['NSCameraUsageDescription', 'NSMicrophoneUsageDescription', 'NSPhotoLibraryUsageDescription']) {
    assert.ok(stringValue(keys.get(key))?.startsWith('L’Atelier'), key);
  }
  // Nothing in the app uses on-device speech recognition: voice goes to the
  // API's /audio/transcribe. An unused permission string is a review flag.
  assert.equal(keys.has('NSSpeechRecognitionUsageDescription'), false);
  assert.ok(!read('ios', 'App', 'App', 'Info.plist').includes('Feuilleton'));
});

test('iPhone only, portrait only', () => {
  const keys = plistKeys(read('ios', 'App', 'App', 'Info.plist'));
  const orientations = keys.get('UISupportedInterfaceOrientations').match(/UIInterfaceOrientation\w+/g);
  assert.deepEqual(orientations, ['UIInterfaceOrientationPortrait']);
  assert.equal(keys.has('UISupportedInterfaceOrientations~ipad'), false);
  const pbxproj = read('ios', 'App', 'App.xcodeproj', 'project.pbxproj');
  assert.equal((pbxproj.match(/TARGETED_DEVICE_FAMILY = 1;/g) || []).length, 2);
  assert.ok(!pbxproj.includes('TARGETED_DEVICE_FAMILY = "1,2"'));
});

test('permission strings are localized in en/de/fr and bundled', () => {
  const pbxproj = read('ios', 'App', 'App.xcodeproj', 'project.pbxproj');
  const expected = ['CFBundleDisplayName', 'NSCameraUsageDescription', 'NSMicrophoneUsageDescription', 'NSPhotoLibraryUsageDescription'];
  for (const lang of ['en', 'de', 'fr']) {
    const strings = read('ios', 'App', 'App', `${lang}.lproj`, 'InfoPlist.strings');
    const keys = [...strings.matchAll(/^"(\w+)"\s*=/gm)].map((m) => m[1]).sort();
    assert.deepEqual(keys, [...expected].sort(), lang);
    assert.ok(pbxproj.includes(`path = ${lang}.lproj/InfoPlist.strings;`), `${lang} not in the project`);
  }
  assert.match(pbxproj, /InfoPlist\.strings in Resources \*\/,\n\t\t\t\);/);
});

test('privacy manifest declares what the app collects', () => {
  const manifest = read('ios', 'App', 'App', 'PrivacyInfo.xcprivacy');
  for (const type of [
    'NSPrivacyCollectedDataTypeEmailAddress',
    'NSPrivacyCollectedDataTypeName',
    'NSPrivacyCollectedDataTypePhotosorVideos',
    'NSPrivacyCollectedDataTypeAudioData',
    'NSPrivacyCollectedDataTypeOtherUserContent',
    'NSPrivacyCollectedDataTypeCrashData',
  ]) {
    assert.ok(manifest.includes(`<string>${type}</string>`), type);
  }
  assert.match(manifest, /<key>NSPrivacyTracking<\/key>\s*<false\/>/);
});

function pngHeader(file) {
  const bytes = readFileSync(file);
  assert.equal(bytes.toString('ascii', 1, 4), 'PNG', file);
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20), colorType: bytes[25] };
}

test('app icon: every listed file exists at its size; the 1024 icon is opaque', () => {
  const dir = path.join(appDir, 'Assets.xcassets', 'AppIcon.appiconset');
  const { images } = JSON.parse(readFileSync(path.join(dir, 'Contents.json'), 'utf8'));
  assert.ok(images.some((image) => image.idiom === 'ios-marketing' && image.size === '1024x1024'));
  assert.ok(images.every((image) => image.idiom !== 'ipad'), 'iPhone-only: no iPad slots');
  for (const image of images) {
    const file = path.join(dir, image.filename);
    assert.ok(existsSync(file), image.filename);
    const expected = Math.round(parseFloat(image.size) * parseInt(image.scale, 10));
    const header = pngHeader(file);
    assert.equal(header.width, expected, image.filename);
    assert.equal(header.colorType, 2, `${image.filename} must be RGB without alpha`);
  }
  assert.ok(existsSync(path.join(webRoot, 'ios', 'branding', 'atelier-mark.svg')));
});

test('launch screen: paper ground, the mark centred from Splash', () => {
  const storyboard = read('ios', 'App', 'App', 'Base.lproj', 'LaunchScreen.storyboard');
  assert.match(storyboard, /image="Splash"/);
  assert.match(storyboard, /red="0\.945\d*" green="0\.925\d*" blue="0\.882\d*"/);
  assert.match(storyboard, /firstAttribute="centerX"/);
  assert.match(storyboard, /firstAttribute="centerY"/);
  const dir = path.join(appDir, 'Assets.xcassets', 'Splash.imageset');
  const { images } = JSON.parse(readFileSync(path.join(dir, 'Contents.json'), 'utf8'));
  assert.equal(images.length, 3);
  for (const image of images) assert.ok(existsSync(path.join(dir, image.filename)), image.filename);
});

test('one name: Capacitor config and web manifest', () => {
  assert.match(read('capacitor.config.ts'), /appName: 'L’Atelier'/);
  const manifest = JSON.parse(read('public', 'manifest.webmanifest'));
  assert.equal(manifest.name, 'L’Atelier');
  assert.equal(manifest.theme_color, '#f1ece1');
  for (const icon of manifest.icons) assert.ok(existsSync(path.join(webRoot, 'public', icon.src)), icon.src);
});

test('legal pages are public, in the app, and in sync with the API text', () => {
  const gate = read('components', 'auth', 'RouteAuthGate.tsx');
  const publicBlock = gate.slice(gate.indexOf('PUBLIC_PATHNAMES'), gate.indexOf('GUEST_ONLY_PATHNAMES'));
  assert.ok(publicBlock.includes("'/privacy'"));
  assert.ok(publicBlock.includes("'/terms'"));
  assert.ok(existsSync(path.join(webRoot, 'pages', 'privacy.tsx')));
  assert.ok(existsSync(path.join(webRoot, 'pages', 'terms.tsx')));
  assert.equal(
    read('lib', 'legal-content.json'),
    readFileSync(path.join(webRoot, '..', 'app', 'data', 'legal', 'legal_content.json'), 'utf8'),
    'Run node scripts/sync-legal-content.mjs',
  );
  assert.equal(isExcludedRoute('/privacy'), false);
  assert.equal(isExcludedRoute('/terms'), false);
});

test('sign-up shows the AI consent line with both documents and records it', () => {
  const require = createRequire(import.meta.url);
  require(path.join(webRoot, 'node_modules/sucrase/register/ts'));
  const legal = require(path.join(webRoot, 'lib', 'legal.ts'));
  for (const lang of ['en', 'de', 'fr']) {
    const line = legal.SIGNUP_CONSENT[lang];
    assert.match(line.ai, /OpenAI/, lang);
    assert.ok(line.terms && line.privacy, lang);
  }
  assert.equal(legal.resolveLegalLanguage('de-AT'), 'de');
  assert.equal(legal.resolveLegalLanguage('es', 'fr-FR'), 'fr');
  assert.equal(legal.resolveLegalLanguage(null), 'en');

  const signup = read('pages', 'auth', 'signup.tsx');
  assert.ok(signup.includes('data-signup-consent'));
  assert.ok(signup.includes("setLegalSheet('terms')"));
  assert.ok(signup.includes("setLegalSheet('privacy')"));
  assert.ok(signup.includes("'/legal/consent'"));
  assert.ok(signup.includes('LEGAL_VERSION'));

  const settings = read('pages', 'settings.tsx');
  assert.ok(settings.includes('data-legal-link="privacy"'));
  assert.ok(settings.includes('data-legal-link="terms"'));
});

function fakeExport(root) {
  const files = [
    'index.html',
    '404.html',
    'atelier/index.html',
    'privacy/index.html',
    'terms/index.html',
    'mobile-visual-qa/index.html',
    'atelier-v2-gallery/index.html',
    'dev/styleguide/index.html',
    'bibliotheque/index.html',
    'bibliotheque/[storyId]/index.html',
    'developer-notes/index.html',
    '_next/static/chunks/pages/atelier-0123456789abcdef.js',
    '_next/static/chunks/pages/privacy-0123456789abcdef.js',
    '_next/static/chunks/pages/mobile-visual-qa-0123456789abcdef.js',
    '_next/static/chunks/pages/atelier-v2-gallery-0123456789abcdef.js',
    '_next/static/chunks/pages/dev/styleguide-0123456789abcdef.js',
    '_next/static/chunks/pages/bibliotheque-0123456789abcdef.js',
    '_next/static/chunks/pages/bibliotheque/[storyId]-0123456789abcdef.js',
    '_next/static/chunks/main-0123456789abcdef.js',
    '_next/data/build-1/dev/styleguide.json',
    '_next/data/build-1/atelier.json',
  ];
  for (const rel of files) {
    const file = path.join(root, rel);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, rel.endsWith('.js') ? 'const api="https://atelier.onrender.com/api/v1";' : 'x');
  }
}

test('native export: dev/QA pages and the flag-off Bibliothèque are pruned, nothing else', () => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'wp72-export-'));
  fakeExport(root);
  const prefixes = excludedRoutePrefixes({ storyFeatureVisible: false });
  assert.deepEqual(prefixes, ['/mobile-visual-qa', '/atelier-v2-gallery', '/dev', '/bibliotheque']);
  const removed = pruneNativeExport(root, prefixes);
  assert.equal(removed.length, 10, removed.join('\n'));
  assert.deepEqual(findExcludedPaths(root, prefixes), []);
  for (const kept of [
    'index.html',
    'atelier/index.html',
    'privacy/index.html',
    'terms/index.html',
    'developer-notes/index.html',
    '_next/static/chunks/pages/atelier-0123456789abcdef.js',
    '_next/static/chunks/main-0123456789abcdef.js',
    '_next/data/build-1/atelier.json',
  ]) {
    assert.ok(existsSync(path.join(root, kept)), kept);
  }

  const flagged = mkdtempSync(path.join(os.tmpdir(), 'wp72-export-flag-'));
  fakeExport(flagged);
  pruneNativeExport(flagged, excludedRoutePrefixes({ storyFeatureVisible: true }));
  assert.ok(existsSync(path.join(flagged, 'bibliotheque', 'index.html')));
  assert.ok(!existsSync(path.join(flagged, 'dev')));
});

test('the real launch flags exclude every WP-72 route', () => {
  for (const route of ['/mobile-visual-qa', '/atelier-v2-gallery', '/dev/styleguide']) {
    assert.ok(isExcludedRoute(route), route);
  }
  const flags = JSON.parse(read('launch-flags.json'));
  assert.equal(isExcludedRoute('/bibliotheque/abc', excludedRoutePrefixes(flags)), !flags.storyFeatureVisible);
});

test('release verification refuses local, placeholder, http and sandbox builds', () => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'wp72-bundle-'));
  fakeExport(root);
  pruneNativeExport(root);
  const production = {
    NEXT_PUBLIC_API_BASE_URL: 'https://atelier.onrender.com/api/v1',
    NEXT_PUBLIC_WS_URL: 'wss://atelier.onrender.com',
    NEXT_PUBLIC_NATIVE_PUSH_ENABLED: 'true',
    NEXT_PUBLIC_APNS_ENVIRONMENT: 'production',
  };
  writeNativeBuildManifest(root, production);
  assert.deepEqual(verifyNativeBundle(root, { release: true }), []);

  writeNativeBuildManifest(root, { ...production, NEXT_PUBLIC_APNS_ENVIRONMENT: 'sandbox' });
  assert.match(verifyNativeBundle(root, { release: true }).join('\n'), /not "production"/);

  const base = { nativePushEnabled: true, apnsEnvironment: 'production' };
  assert.match(releaseProblems({ ...base, apiBaseUrl: 'http://localhost:8010/api/v1' }).join('\n'), /HTTPS|localhost/);
  assert.match(releaseProblems({ ...base, apiBaseUrl: 'https://127.0.0.1/api/v1' }).join('\n'), /localhost/);
  assert.match(releaseProblems({ ...base, apiBaseUrl: 'https://api.example.com/api/v1' }).join('\n'), /placeholder/);
  assert.match(releaseProblems({ ...base, apiBaseUrl: 'http://atelier.onrender.com/api/v1' }).join('\n'), /HTTPS/);
  assert.match(releaseProblems({ apiBaseUrl: production.NEXT_PUBLIC_API_BASE_URL, nativePushEnabled: false, apnsEnvironment: 'production' }).join('\n'), /PUSH_ENABLED/);
  assert.match(releaseProblems({ ...base, apiBaseUrl: production.NEXT_PUBLIC_API_BASE_URL, allowLocalApi: true }).join('\n'), /ALLOW_LOCAL/);

  writeNativeBuildManifest(root, { ...production, NEXT_PUBLIC_API_BASE_URL: 'https://other-host.onrender.com/api/v1' });
  assert.match(verifyNativeBundle(root).join('\n'), /not inlined/);
});

test('the archive lane builds and verifies the production bundle itself', () => {
  const fastfile = read('fastlane', 'Fastfile');
  const lane = fastfile.slice(fastfile.indexOf('lane :archive do'), fastfile.indexOf('lane :beta do'));
  assert.ok(lane.indexOf('build_release_web_bundle') < lane.indexOf('build_app('), 'web bundle before build_app');
  assert.match(lane, /-allowProvisioningUpdates/);
  assert.match(fastfile, /"NEXT_PUBLIC_APNS_ENVIRONMENT" => "production"/);
  assert.match(fastfile, /"NEXT_PUBLIC_NATIVE_PUSH_ENABLED" => "true"/);
  assert.match(fastfile, /sh\("npm", "run", "cap:sync:ios"\)/);
  assert.match(fastfile, /verify-native-bundle\.mjs", "--release"/);
  const build = read('scripts', 'build-native.mjs');
  assert.match(build, /pruneNativeExport\(/);
  assert.match(build, /writeNativeBuildManifest\(/);
});
