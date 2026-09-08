import { spawnSync } from 'node:child_process';

import { resolveNativeApiEnvironment } from './native-api-env.mjs';

let resolved;
try {
  resolved = resolveNativeApiEnvironment();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error('Set NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_URL to the hosted API URL before native builds.');
  console.error('For local simulator-only builds, set ALLOW_LOCAL_NATIVE_API=true explicitly.');
  process.exit(1);
}

const result = spawnSync('npx', ['next', 'build'], {
  stdio: 'inherit',
  env: {
    ...process.env,
    ...resolved,
    NATIVE_STATIC_EXPORT: 'true',
  },
});

process.exit(result.status ?? 1);
