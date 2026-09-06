import { resolveNativeApiEnvironment } from './native-api-env.mjs';

try {
  const resolved = resolveNativeApiEnvironment();
  Object.assign(process.env, resolved);
  if (process.env.ALLOW_LOCAL_NATIVE_API === 'true') {
    console.warn('Native API configuration warning: local device networking is explicitly enabled.');
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error('Set NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_URL to the hosted API URL before native builds.');
  console.error('For local simulator-only builds, set ALLOW_LOCAL_NATIVE_API=true explicitly.');
  process.exit(1);
}
