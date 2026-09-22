import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { resolveNativeApiEnvironment } from './native-api-env.mjs';
import {
  excludedRoutePrefixes,
  pruneNativeExport,
  releaseProblems,
  writeNativeBuildManifest,
} from './native-export-policy.mjs';

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const outDir = path.join(webRoot, 'out');

let resolved;
try {
  resolved = resolveNativeApiEnvironment();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error('Set NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_URL to the hosted API URL before native builds.');
  console.error('For local simulator-only builds, set ALLOW_LOCAL_NATIVE_API=true explicitly.');
  process.exit(1);
}

const buildEnv = {
  ...process.env,
  ...resolved,
  NATIVE_STATIC_EXPORT: 'true',
};

// WP-72: an App Store / TestFlight build (the fastlane archive lane sets
// NATIVE_RELEASE=true) fails here, before a multi-minute build, when the API or
// push settings are not production ones.
if (process.env.NATIVE_RELEASE === 'true') {
  const problems = releaseProblems({
    apiBaseUrl: buildEnv.NEXT_PUBLIC_API_BASE_URL,
    wsUrl: buildEnv.NEXT_PUBLIC_WS_URL,
    nativePushEnabled: buildEnv.NEXT_PUBLIC_NATIVE_PUSH_ENABLED === 'true',
    apnsEnvironment: buildEnv.NEXT_PUBLIC_APNS_ENVIRONMENT,
    allowLocalApi: buildEnv.ALLOW_LOCAL_NATIVE_API === 'true',
    allowPlaceholderApi: buildEnv.ALLOW_PLACEHOLDER_NATIVE_API === 'true',
  });
  if (problems.length) {
    console.error('Release build refused:');
    for (const problem of problems) console.error(`  - ${problem}`);
    process.exit(1);
  }
}

const result = spawnSync('npx', ['next', 'build'], {
  stdio: 'inherit',
  env: buildEnv,
});

if (result.status !== 0) process.exit(result.status ?? 1);

// WP-72: dev/QA pages (and the flag-off Bibliothèque) never ship on the phone.
const prefixes = excludedRoutePrefixes();
try {
  const removed = pruneNativeExport(outDir, prefixes);
  console.log(`Native export: pruned ${removed.length} dev/QA path(s) for ${prefixes.join(', ')}.`);
  writeNativeBuildManifest(outDir, buildEnv, prefixes);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
