/**
 * WP-73 — see production, client side.
 *
 * Error tracking with `@sentry/browser`, loaded lazily and only when
 * `NEXT_PUBLIC_SENTRY_DSN` was baked into the build. Without a DSN (local dev,
 * tests, any build that did not opt in) nothing is imported and every function
 * here is a no-op apart from the first-party crash intake.
 *
 * Why `@sentry/browser` and not `@sentry/capacitor` + `@sentry/react`: the app is
 * a static Next export rendered in the Capacitor WKWebView, so every crash we
 * write is a JavaScript crash, which the browser SDK sees in both the web and
 * the native shell (tagged `platform=capacitor`). `@sentry/capacitor` adds a
 * native Cocoa SDK pod and must track the browser SDK's exact version on every
 * upgrade — worth it only once native Swift/ObjC crashes matter. The dynamic
 * import keeps the SDK out of the first-load bundle entirely.
 *
 * PII: learner French text travels in request bodies and form inputs, so no
 * event carries a body, a query string, cookies, input breadcrumbs or console
 * text; the learner is known by id only.
 */

type SentryLike = {
  init: (options: Record<string, unknown>) => void;
  captureException: (error: unknown, hint?: Record<string, unknown>) => unknown;
  setUser: (user: { id: string } | null) => void;
  setTag: (key: string, value: string) => void;
};

type AnyEvent = Record<string, any>;

const SAFE_HEADERS = new Set(['user-agent', 'content-type', 'x-request-id', 'accept']);

let sentry: SentryLike | null = null;
let loading: Promise<SentryLike | null> | null = null;
let currentUserId: string | null = null;

export function sentryDsn(): string {
  return (process.env.NEXT_PUBLIC_SENTRY_DSN || '').trim();
}

export function newRequestId(): string {
  const cryptoApi = typeof globalThis !== 'undefined' ? (globalThis as any).crypto : undefined;
  if (cryptoApi?.randomUUID) return String(cryptoApi.randomUUID()).replace(/-/g, '');
  let id = '';
  for (let i = 0; i < 32; i += 1) id += Math.floor(Math.random() * 16).toString(16);
  return id;
}

/** Path only: a query string or fragment can carry a token or a reset code. */
export function stripQuery(url: string | undefined | null): string | undefined {
  if (!url) return undefined;
  return String(url).split('#', 1)[0].split('?', 1)[0];
}

/** `beforeSend`: remove anything that could carry learner text or credentials. */
export function scrubClientEvent<T extends AnyEvent>(input: T): T {
  const event: AnyEvent = input;
  const request = event.request as AnyEvent | undefined;
  if (request) {
    delete request.data;
    delete request.cookies;
    delete request.query_string;
    if (request.url) request.url = stripQuery(request.url);
    if (request.headers && typeof request.headers === 'object') {
      const kept: Record<string, string> = {};
      for (const [key, value] of Object.entries(request.headers)) {
        if (SAFE_HEADERS.has(key.toLowerCase())) kept[key] = value as string;
      }
      request.headers = kept;
    }
  }
  if (event.user) event.user = event.user.id ? { id: String(event.user.id) } : {};
  if (Array.isArray(event.breadcrumbs)) {
    event.breadcrumbs = event.breadcrumbs.map((crumb: AnyEvent) => scrubBreadcrumb(crumb)).filter(Boolean);
  }
  return input;
}

export function scrubBreadcrumb<T extends AnyEvent>(crumb: T): T | null {
  if (!crumb) return null;
  const category = String(crumb.category || '');
  if (category === 'console' || category === 'ui.input') return null;
  if (category === 'ui.click') return { ...crumb, message: undefined };
  if (crumb.data && typeof crumb.data === 'object') {
    const data: AnyEvent = { ...crumb.data };
    if (data.url) data.url = stripQuery(data.url);
    if (data.from) data.from = stripQuery(data.from);
    if (data.to) data.to = stripQuery(data.to);
    delete data.body;
    delete data.request_body;
    return { ...crumb, data };
  }
  return crumb;
}

function platformTag(): string {
  const cap = typeof window !== 'undefined' ? (window as any).Capacitor : undefined;
  return cap?.isNativePlatform?.() ? 'capacitor' : 'web';
}

/** Start Sentry once, lazily. Resolves to `null` when no DSN was configured. */
export function initObservability(loader?: () => Promise<SentryLike>): Promise<SentryLike | null> {
  if (sentry) return Promise.resolve(sentry);
  if (loading) return loading;
  const dsn = sentryDsn();
  if (!dsn) return Promise.resolve(null);
  const load = loader || (() => import('@sentry/browser') as unknown as Promise<SentryLike>);
  loading = load()
    .then((sdk) => {
      sdk.init({
        dsn,
        environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV,
        release: process.env.NEXT_PUBLIC_APP_RELEASE || undefined,
        sendDefaultPii: false,
        tracesSampleRate: 0,
        beforeSend: (event: AnyEvent) => scrubClientEvent(event),
        beforeBreadcrumb: (crumb: AnyEvent) => scrubBreadcrumb(crumb),
      });
      sdk.setTag('platform', platformTag());
      if (currentUserId) sdk.setUser({ id: currentUserId });
      sentry = sdk;
      return sdk;
    })
    .catch(() => {
      loading = null;
      return null;
    });
  return loading;
}

/** Learner id only — never email or name. `null` when signed out. */
export function setObservabilityUser(userId: string | null | undefined): void {
  currentUserId = userId ? String(userId) : null;
  sentry?.setUser(currentUserId ? { id: currentUserId } : null);
}

export function isSignedInForObservability(): boolean {
  return Boolean(currentUserId);
}

/** Report a handled error; tagged with the request id that failed, when known. */
export function captureClientError(error: unknown, context: { requestId?: string; route?: string } = {}): void {
  if (!sentry) return;
  const tags: Record<string, string> = {};
  if (context.requestId) tags.request_id = context.requestId;
  const route = stripQuery(context.route);
  if (route) tags.route = route;
  // An AxiosError carries its request config — body included. Send a bare
  // Error with the status and path instead, never the learner's text.
  const axiosLike = error as { isAxiosError?: boolean; response?: { status?: number } } | null;
  const reported = axiosLike?.isAxiosError
    ? new Error(`API ${axiosLike.response?.status ?? 'error'} ${route || ''}`.trim())
    : error;
  sentry.captureException(reported, { tags });
}

/** Test seam: install a fake SDK (or `null` to reset). */
export function __setSentryForTests(fake: SentryLike | null): void {
  sentry = fake;
  loading = null;
  currentUserId = null;
}
