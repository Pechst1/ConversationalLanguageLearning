const allowLocal = process.env.ALLOW_LOCAL_NATIVE_API === 'true';
const configured = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || '';
const configuredWs = process.env.NEXT_PUBLIC_WS_URL || '';

function fail(message) {
  console.error(`Native API configuration error: ${message}`);
  console.error('Set NEXT_PUBLIC_API_BASE_URL or NEXT_PUBLIC_API_URL to the hosted API URL before native builds.');
  console.error('For local simulator-only builds, set ALLOW_LOCAL_NATIVE_API=true explicitly.');
  process.exit(1);
}

if (!configured.trim()) {
  fail('missing NEXT_PUBLIC_API_BASE_URL/NEXT_PUBLIC_API_URL.');
}

function isLocalHostname(hostname) {
  const normalized = hostname.toLowerCase();
  return normalized === 'localhost' || normalized === '127.0.0.1' || normalized === '::1' || normalized === '[::1]';
}

let apiUrl;
try {
  apiUrl = new URL(configured);
} catch {
  fail(`"${configured}" is not an absolute URL.`);
}

const isLocalHost = isLocalHostname(apiUrl.hostname);

if (isLocalHost && allowLocal) {
  console.warn('Native API configuration warning: using a local API because ALLOW_LOCAL_NATIVE_API=true.');
} else {
  if (apiUrl.protocol !== 'https:') {
    fail(`"${configured}" must use HTTPS for native production builds.`);
  }

  if (isLocalHost) {
    fail(`"${configured}" points at localhost, which is the device itself in native builds.`);
  }
}

if (configuredWs.trim()) {
  let wsUrl;
  try {
    wsUrl = new URL(configuredWs);
  } catch {
    fail(`NEXT_PUBLIC_WS_URL "${configuredWs}" is not an absolute URL.`);
  }

  const isLocalWsHost = isLocalHostname(wsUrl.hostname);
  if (isLocalWsHost && allowLocal) {
    console.warn('Native API configuration warning: using a local WebSocket because ALLOW_LOCAL_NATIVE_API=true.');
    process.exit(0);
  }

  if (wsUrl.protocol !== 'wss:') {
    fail(`NEXT_PUBLIC_WS_URL "${configuredWs}" must use WSS for native production builds.`);
  }

  if (isLocalWsHost) {
    fail(`NEXT_PUBLIC_WS_URL "${configuredWs}" points at localhost, which is the device itself in native builds.`);
  }
}
