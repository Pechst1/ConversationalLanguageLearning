function configurationError(message) {
  return new Error(`Native API configuration error: ${message}`);
}

function isLocalHostname(hostname) {
  const normalized = hostname.toLowerCase();
  return normalized === 'localhost' || normalized === '127.0.0.1' || normalized === '::1' || normalized === '[::1]';
}

function isPlaceholderHostname(hostname) {
  const normalized = hostname.toLowerCase();
  return normalized === 'example.com' || normalized.endsWith('.example.com');
}

function parseAbsoluteUrl(value, label) {
  try {
    return new URL(value);
  } catch {
    throw configurationError(`${label} "${value}" is not an absolute URL.`);
  }
}

function deriveWebSocketUrl(apiUrl) {
  const websocketUrl = new URL(apiUrl.toString());
  websocketUrl.protocol = websocketUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  websocketUrl.pathname = websocketUrl.pathname.replace(/\/api\/v1\/?$/, '').replace(/\/+$/, '');
  websocketUrl.search = '';
  websocketUrl.hash = '';
  return websocketUrl.toString().replace(/\/+$/, '');
}

export function resolveNativeApiEnvironment(environment = process.env) {
  const allowLocal = environment.ALLOW_LOCAL_NATIVE_API === 'true';
  const allowPlaceholder = environment.ALLOW_PLACEHOLDER_NATIVE_API === 'true';
  const configuredApi = (environment.NEXT_PUBLIC_API_BASE_URL || environment.NEXT_PUBLIC_API_URL || '').trim();

  if (!configuredApi) {
    throw configurationError('missing NEXT_PUBLIC_API_BASE_URL/NEXT_PUBLIC_API_URL.');
  }

  const apiUrl = parseAbsoluteUrl(configuredApi, 'API URL');
  const isLocalApi = isLocalHostname(apiUrl.hostname);
  if (isPlaceholderHostname(apiUrl.hostname) && !allowPlaceholder) {
    throw configurationError(`API URL "${configuredApi}" is a placeholder, not a deployable host.`);
  }
  if (!(isLocalApi && allowLocal)) {
    if (apiUrl.protocol !== 'https:') {
      throw configurationError(`API URL "${configuredApi}" must use HTTPS for native production builds.`);
    }
    if (isLocalApi) {
      throw configurationError(`API URL "${configuredApi}" points at localhost, which is the device itself in native builds.`);
    }
  }

  const configuredWs = (environment.NEXT_PUBLIC_WS_URL || '').trim();
  const wsValue = configuredWs || deriveWebSocketUrl(apiUrl);
  const wsUrl = parseAbsoluteUrl(wsValue, 'WebSocket URL');
  const isLocalWs = isLocalHostname(wsUrl.hostname);
  if (isPlaceholderHostname(wsUrl.hostname) && !allowPlaceholder) {
    throw configurationError(`WebSocket URL "${wsValue}" is a placeholder, not a deployable host.`);
  }
  if (!(isLocalWs && allowLocal)) {
    if (wsUrl.protocol !== 'wss:') {
      throw configurationError(`WebSocket URL "${wsValue}" must use WSS for native production builds.`);
    }
    if (isLocalWs) {
      throw configurationError(`WebSocket URL "${wsValue}" points at localhost, which is the device itself in native builds.`);
    }
  }

  return {
    NEXT_PUBLIC_API_BASE_URL: configuredApi,
    NEXT_PUBLIC_API_URL: configuredApi,
    NEXT_PUBLIC_WS_URL: wsValue,
  };
}
