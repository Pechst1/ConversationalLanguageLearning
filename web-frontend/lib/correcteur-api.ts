/**
 * WP-122 B · Le Correcteur — the typed client for `/revue/correcteur/*`.
 *
 * Same shape as `lib/revue-api.ts`: the transport is the only thing that knows the
 * network (`httpCorrecteurTransport()` uses the app's authenticated axios client with
 * the global toasts off); `components/correcteur/correcteur-mock.ts` is an in-memory
 * one for `?mock=1`. `week()` answering a bare 404 (the flag is off) resolves to
 * `{ enabled: false }`.
 */

import {
  CorrecteurError,
  marksWire,
  parseCorrecteurError,
  parseDraft,
  parseResult,
  parseWeek,
  type CrDraft,
  type CrMark,
  type CrResult,
  type CrWeekResult,
} from './correcteur-types';

export const CORRECTEUR_BASE = '/revue/correcteur';

export type CorrecteurTransport = {
  get: (url: string) => Promise<unknown>;
  post: (url: string, body: unknown) => Promise<unknown>;
};

export type CorrecteurClient = {
  week: () => Promise<CrWeekResult>;
  draft: (dossierId: string) => Promise<CrDraft>;
  marks: (correctionId: string, marks: CrMark[]) => Promise<CrResult>;
};

const asObject = (value: unknown): Record<string, any> =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : {};

function toError(error: unknown): CorrecteurError {
  if (error instanceof CorrecteurError) return error;
  const response = (error as { response?: { status?: number; data?: unknown } } | null)?.response;
  if (!response) return new CorrecteurError(0, 'network');
  return parseCorrecteurError(Number(response.status) || 0, response.data);
}

export function createCorrecteurClient(transport: CorrecteurTransport): CorrecteurClient {
  async function call<T>(run: () => Promise<unknown>, parse: (raw: Record<string, any>) => T): Promise<T> {
    try {
      return parse(asObject(await run()));
    } catch (error) {
      throw toError(error);
    }
  }
  return {
    async week() {
      try {
        const week = await call(() => transport.get(`${CORRECTEUR_BASE}/week`), parseWeek);
        return { enabled: true, week };
      } catch (error) {
        if (error instanceof CorrecteurError && error.code === 'correcteur_disabled') return { enabled: false };
        throw error;
      }
    },
    draft: (dossierId) => call(() => transport.post(`${CORRECTEUR_BASE}/${encodeURIComponent(dossierId)}`, {}), parseDraft),
    marks: (correctionId, marks) =>
      call(() => transport.post(`${CORRECTEUR_BASE}/${encodeURIComponent(correctionId)}/marks`, marksWire(marks)), parseResult),
  };
}

export function httpCorrecteurTransport(): CorrecteurTransport {
  // Required lazily so the pure client (and its node tests) never load axios.
  const { apiService } = require('@/services/api') as typeof import('@/services/api');
  const quiet = { suppressGlobalError: true } as Record<string, unknown>;
  return {
    get: (url) => apiService.get(url, quiet),
    post: (url, body) => apiService.post(url, body, quiet),
  };
}

let http: CorrecteurClient | null = null;

export function correcteurClient(): CorrecteurClient {
  if (!http) http = createCorrecteurClient(httpCorrecteurTransport());
  return http;
}

export { CorrecteurError };
