/**
 * WP-119 phase 1 · La Revue de Romy — the typed client for every route of
 * docs/implementation/atelier-v2/WP-119-WIRE.md.
 *
 * `createRevueClient(transport)` is the whole client: it builds the URLs and the
 * snake_case bodies, parses every response through `lib/revue-types.ts` and turns
 * every failure into a `RevueError`. The transport is the only thing that knows
 * about the network: `httpRevueTransport()` uses the app's authenticated axios
 * client (`services/api.ts`, global toasts suppressed — the Revue says its own
 * failures), and `lib/revue-mock.ts` is a scripted, in-memory one for dev.
 *
 * `GET /revue/week` answering 404 (the flag is off) resolves to
 * `{ enabled: false }`: La Une then simply draws no Revue card or chip.
 */

import {
  RevueError,
  makeBodyWire,
  parseCloseResult,
  parseMakeOffer,
  parseMakeResult,
  parseMatch,
  parseOffer,
  parseRevueError,
  parseSessionView,
  parseTurnResult,
  startBodyWire,
  turnBodyWire,
  type RvCloseResult,
  type RvMakeBody,
  type RvMakeOffer,
  type RvMakeResult,
  type RvMatchResult,
  type RvSessionView,
  type RvStartBody,
  type RvTurnBody,
  type RvTurnResult,
  type RvWeekResult,
} from './revue-types';

export const REVUE_BASE = '/revue';

/** What a transport must do: answer JSON, or throw an axios-shaped error (`response.status`, `response.data`). */
export type RevueTransport = {
  get: (url: string) => Promise<unknown>;
  post: (url: string, body: unknown) => Promise<unknown>;
};

export type RevueClient = {
  /** The week's offer; `{ enabled: false }` when the Revue is switched off. */
  week: (week?: string) => Promise<RvWeekResult>;
  /** «Autre chose ?»: a free request against the week's dossiers. */
  match: (text: string, week?: string) => Promise<RvMatchResult>;
  start: (body?: RvStartBody) => Promise<RvSessionView>;
  /** Resume: a pure replay of the session's state. */
  session: (id: string) => Promise<RvSessionView>;
  turn: (id: string, body: RvTurnBody) => Promise<RvTurnResult>;
  makeOffer: (id: string) => Promise<RvMakeOffer>;
  make: (id: string, body: RvMakeBody) => Promise<RvMakeResult>;
  close: (id: string) => Promise<RvCloseResult>;
};

function toRevueError(error: unknown): RevueError {
  if (error instanceof RevueError) return error;
  const response = (error as { response?: { status?: number; data?: unknown } } | null)?.response;
  if (!response) return new RevueError(0, 'network');
  return parseRevueError(Number(response.status) || 0, response.data);
}

const asObject = (value: unknown): Record<string, any> =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : {};

const session = (id: string) => `${REVUE_BASE}/sessions/${encodeURIComponent(id)}`;

export function createRevueClient(transport: RevueTransport): RevueClient {
  async function get<T>(url: string, parse: (raw: Record<string, any>) => T): Promise<T> {
    try {
      return parse(asObject(await transport.get(url)));
    } catch (error) {
      throw toRevueError(error);
    }
  }
  async function post<T>(url: string, body: unknown, parse: (raw: Record<string, any>) => T): Promise<T> {
    try {
      return parse(asObject(await transport.post(url, body)));
    } catch (error) {
      throw toRevueError(error);
    }
  }

  return {
    async week(week) {
      const query = week ? `?week=${encodeURIComponent(week)}` : '';
      try {
        const offer = await get(`${REVUE_BASE}/week${query}`, parseOffer);
        return { enabled: true, offer };
      } catch (error) {
        // The flag is off: every route is a bare 404 «Not Found». The Revue is invisible.
        if (error instanceof RevueError && error.code === 'revue_disabled') return { enabled: false };
        throw error;
      }
    },
    match: (text, week) => post(`${REVUE_BASE}/match`, week ? { text, week } : { text }, parseMatch),
    start: (body = {}) => post(`${REVUE_BASE}/sessions`, startBodyWire(body), parseSessionView),
    session: (id) => get(session(id), parseSessionView),
    turn: (id, body) => post(`${session(id)}/turns`, turnBodyWire(body), parseTurnResult),
    makeOffer: (id) => get(`${session(id)}/make`, parseMakeOffer),
    make: (id, body) => post(`${session(id)}/make`, makeBodyWire(body), parseMakeResult),
    close: (id) => post(`${session(id)}/close`, {}, parseCloseResult),
  };
}

/** The app's authenticated client, with the global error toasts off. */
export function httpRevueTransport(): RevueTransport {
  // Required lazily so the pure client (and its node tests) never load axios.
  const { apiService } = require('@/services/api') as typeof import('@/services/api');
  const quiet = { suppressGlobalError: true } as Record<string, unknown>;
  return {
    get: (url) => apiService.get(url, quiet),
    post: (url, body) => apiService.post(url, body, quiet),
  };
}

let http: RevueClient | null = null;

/** The real client, one per page load. */
export function revueClient(): RevueClient {
  if (!http) http = createRevueClient(httpRevueTransport());
  return http;
}

/** A client turn id: makes a retried turn safe (WIRE §3.5). */
export function newClientTurnId(): string {
  const random = Math.random().toString(36).slice(2, 10);
  return `t-${Date.now().toString(36)}-${random}`;
}

export { RevueError };
