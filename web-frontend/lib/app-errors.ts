/**
 * S4 stage 2 — one error path.
 *
 * Every failure the app shows goes through `errorToState`: the axios
 * interceptor's toasts, the error boundary in `_app.tsx`, the 404 and 500
 * pages, and any page's inline state. It records *what* went wrong (`kind`)
 * and says it in the screen's chrome language (en, de, fr; the learner is
 * addressed with tu/du). Grown from Home's `lib/atelier-errors.ts`, which
 * keeps its finer load/session kinds for the day's page.
 */

import type { ControlLanguage } from '@/types/daily-journey';

/* Kept dependency-free (no `@/` imports) so the node tests can load it; the
   same rule as `normalizeControlLanguage` in lib/atelier-v2-copy.ts. */
function normalizeControlLanguage(value: unknown): ControlLanguage {
  const base = typeof value === 'string' ? value.trim().toLowerCase().replace('_', '-').split('-')[0] : '';
  return base === 'de' || base === 'fr' ? base : 'en';
}

export type AppErrorKind =
  | 'offline'
  | 'slow'
  | 'down'
  | 'not_found'
  | 'forbidden'
  | 'rate_limited'
  | 'session_expired'
  | 'unknown';

/** The one way forward a state offers. */
export type AppErrorAction = 'retry' | 'home' | 'sign_in';

export type AppErrorState = {
  kind: AppErrorKind;
  title: string;
  body: string;
  action: { kind: AppErrorAction; label: string };
};

/** Where «home» leads: La Une. A signed-out visitor is sent on to sign-in by the route gate. */
export const HOME_HREF = '/atelier';

type Text = { title: string; body: string };
type Table = Record<AppErrorKind, Text> & {
  budget: Text;
  crashed: Text;
  actions: Record<AppErrorAction, string>;
  reference: string;
};

const EN: Table = {
  offline: { title: 'You are offline', body: 'Check your connection, then try again.' },
  slow: { title: 'One moment', body: 'The Atelier is answering slowly. Try again.' },
  down: { title: 'Unavailable', body: 'The Atelier is not answering. Try again in a moment.' },
  not_found: { title: 'Nothing here', body: 'This page does not exist, or no longer does.' },
  forbidden: { title: 'Not for this account', body: 'Your account cannot open this.' },
  rate_limited: { title: 'Slow down', body: 'Try again in {seconds} s.' },
  session_expired: { title: 'Signed out', body: 'Your session has ended. Sign in again to carry on.' },
  unknown: { title: 'Something went wrong', body: 'That did not work. Try again.' },
  budget: { title: 'That’s all for today', body: 'See you tomorrow!' },
  crashed: { title: 'This page stopped', body: 'Something broke while it was drawn. Go back to La Une and open it again.' },
  actions: { retry: 'Try again', home: 'Back to La Une', sign_in: 'Sign in again' },
  reference: 'Reference',
};

const DE: Table = {
  offline: { title: 'Du bist offline', body: 'Prüfe die Verbindung und versuch es erneut.' },
  slow: { title: 'Einen Moment', body: 'Das Atelier antwortet langsam. Versuch es erneut.' },
  down: { title: 'Nicht verfügbar', body: 'Das Atelier antwortet nicht. Versuch es gleich noch einmal.' },
  not_found: { title: 'Hier ist nichts', body: 'Diese Seite gibt es nicht, oder nicht mehr.' },
  forbidden: { title: 'Nicht für dieses Konto', body: 'Dein Konto kann das nicht öffnen.' },
  rate_limited: { title: 'Langsam', body: 'Versuch es in {seconds} s erneut.' },
  session_expired: { title: 'Abgemeldet', body: 'Deine Sitzung ist abgelaufen. Melde dich erneut an, um weiterzumachen.' },
  unknown: { title: 'Etwas ist schiefgelaufen', body: 'Das hat nicht geklappt. Versuch es erneut.' },
  budget: { title: 'Das war’s für heute', body: 'Bis morgen!' },
  crashed: { title: 'Diese Seite ist stehen geblieben', body: 'Beim Aufbau ist etwas kaputtgegangen. Geh zurück zu La Une und öffne sie noch einmal.' },
  actions: { retry: 'Erneut versuchen', home: 'Zurück zu La Une', sign_in: 'Erneut anmelden' },
  reference: 'Referenz',
};

const FR: Table = {
  offline: { title: 'Hors ligne', body: 'Vérifie la connexion, puis réessaie.' },
  slow: { title: 'Encore un instant', body: 'L’Atelier répond lentement. Réessaie.' },
  down: { title: 'Indisponible', body: 'L’Atelier ne répond pas. Réessaie dans un instant.' },
  not_found: { title: 'Rien ici', body: 'Cette page n’existe pas, ou plus.' },
  forbidden: { title: 'Pas pour ce compte', body: 'Ton compte ne peut pas ouvrir ceci.' },
  rate_limited: { title: 'Doucement', body: 'Réessaie dans {seconds} s.' },
  session_expired: { title: 'Session terminée', body: 'Ta session a pris fin. Reconnecte-toi pour continuer.' },
  unknown: { title: 'Un problème est survenu', body: 'Ça n’a pas marché. Réessaie.' },
  budget: { title: 'C’est tout pour aujourd’hui', body: 'À demain !' },
  crashed: { title: 'Cette page s’est arrêtée', body: 'Quelque chose a cassé pendant l’affichage. Reviens à La Une et rouvre-la.' },
  actions: { retry: 'Réessayer', home: 'Retour à La Une', sign_in: 'Se reconnecter' },
  reference: 'Référence',
};

const TABLES: Record<ControlLanguage, Table> = { en: EN, de: DE, fr: FR };

export function appErrorCopy(language: unknown): Table {
  return TABLES[normalizeControlLanguage(language)];
}

const ACTION_FOR: Record<AppErrorKind, AppErrorAction> = {
  offline: 'retry',
  slow: 'retry',
  down: 'retry',
  not_found: 'home',
  forbidden: 'home',
  rate_limited: 'retry',
  session_expired: 'sign_in',
  unknown: 'retry',
};

type ErrorLike = {
  code?: unknown;
  message?: unknown;
  response?: { status?: unknown; data?: unknown; headers?: Record<string, unknown> };
  kind?: unknown;
};

const KINDS = new Set<AppErrorKind>(['offline', 'slow', 'down', 'not_found', 'forbidden', 'rate_limited', 'session_expired', 'unknown']);

function browserOffline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false;
}

/** What went wrong, from an axios error, an HTTP status, a kind, or anything thrown. */
export function errorKind(error: unknown): AppErrorKind {
  if (typeof error === 'string' && KINDS.has(error as AppErrorKind)) return error as AppErrorKind;
  if (typeof error === 'number') return kindForStatus(error);
  const value = (error || {}) as ErrorLike;
  if (typeof value.kind === 'string' && KINDS.has(value.kind as AppErrorKind)) return value.kind as AppErrorKind;
  const status = Number(value.response?.status);
  if (Number.isFinite(status) && status > 0) return kindForStatus(status);
  const code = String(value.code || '');
  if (code === 'ECONNABORTED' || code === 'ETIMEDOUT') return 'slow';
  if (browserOffline()) return 'offline';
  if (code === 'ERR_NETWORK') return 'down';
  return 'unknown';
}

function kindForStatus(status: number): AppErrorKind {
  if (status === 401 || status === 419) return 'session_expired';
  if (status === 403) return 'forbidden';
  if (status === 404 || status === 410) return 'not_found';
  if (status === 408) return 'slow';
  if (status === 429) return 'rate_limited';
  if (status === 502 || status === 503 || status === 504) return 'down';
  if (status >= 500) return 'down';
  return 'unknown';
}

function detailCode(error: unknown): string | undefined {
  const data = (error as ErrorLike | null)?.response?.data as { detail?: { code?: unknown }; code?: unknown } | undefined;
  const code = data?.detail?.code ?? data?.code;
  return typeof code === 'string' ? code : undefined;
}

/** Seconds a 429 asks to wait (`Retry-After`), at least one. */
export function retryAfterSeconds(error: unknown): number {
  const header = (error as ErrorLike | null)?.response?.headers?.['retry-after'];
  return Math.max(1, Number(header) || 5);
}

/**
 * The state to draw for a failure: a title, one sentence and one way forward,
 * in the screen's chrome language. `error` may be an axios error, a status, a
 * kind, or anything thrown.
 */
export function errorToState(error: unknown, language: unknown): AppErrorState {
  const kind = errorKind(error);
  const copy = appErrorCopy(language);
  let text: Text = copy[kind];
  if (kind === 'rate_limited') {
    text = detailCode(error) === 'daily_budget_reached'
      ? copy.budget
      : { ...text, body: text.body.replace('{seconds}', String(retryAfterSeconds(error))) };
  }
  const action = ACTION_FOR[kind];
  return { kind, title: text.title, body: text.body, action: { kind: action, label: copy.actions[action] } };
}

/** One line for a toast: the title, then the sentence. */
export function errorToastText(state: AppErrorState): string {
  return `${state.title} · ${state.body}`;
}

/** A toast id, so the same failure on several requests shows once. */
export function errorToastId(error: unknown, state: AppErrorState): string {
  return state.kind === 'rate_limited' ? detailCode(error) || 'rate_limited' : `app-error:${state.kind}`;
}

/** The short id one crash carries on the screen and in its report. */
export function newErrorEventId(): string {
  const cryptoApi = typeof globalThis !== 'undefined' ? (globalThis as { crypto?: Crypto }).crypto : undefined;
  if (cryptoApi?.getRandomValues) {
    return Array.from(cryptoApi.getRandomValues(new Uint8Array(6)), (byte) => byte.toString(16).padStart(2, '0')).join('');
  }
  let id = '';
  for (let i = 0; i < 12; i += 1) id += Math.floor(Math.random() * 16).toString(16);
  return id;
}
