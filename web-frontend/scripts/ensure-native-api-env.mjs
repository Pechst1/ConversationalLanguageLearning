const allowLocal = process.env.ALLOW_LOCAL_NATIVE_API === 'true';
const configured = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || '';

function fail(message) {
  console.error(`Native API configuration error: ${message}`);
  console.error('Set NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_URL to the hosted API URL before native builds.');
  console.error('For local simulator-only builds, set ALLOW_LOCAL_NATIVE_API=true explicitly.');
  process.exit(1);
}

if (!configured.trim()) {
  fail('missing NEXT_PUBLIC_API_BASE_URL/NEXT_PUBLIC_API_URL.');
}

let apiUrl;
try {
  apiUrl = new URL(configured);
} catch {
  fail(`"${configured}" is not an absolute URL.`);
}

const hostname = apiUrl.hostname.toLowerCase();
const isLocalHost =
  hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1' || hostname === '[::1]';

if (isLocalHost && allowLocal) {
  console.warn('Native API configuration warning: using a local API because ALLOW_LOCAL_NATIVE_API=true.');
  process.exit(0);
}

if (apiUrl.protocol !== 'https:') {
  fail(`"${configured}" must use HTTPS for native production builds.`);
}

if (isLocalHost) {
  fail(`"${configured}" points at localhost, which is the device itself in native builds.`);
}
