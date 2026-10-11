/**
 * WP-122 A · La Radio — the client for `/revue/radio/*`.
 *
 * Same shape as `lib/carte-api.ts`: a transport-agnostic client (`createRadioClient`)
 * and the app's authenticated, quiet axios transport. A 404 on the week means the
 * Radio (or the Revue) is off: `{ enabled: false }`, and La Une simply has no chip.
 * The page's mock (`components/radio/radio-mock.ts`) implements the same client.
 */

import {
  RadioError,
  parseBulletin,
  parseDicteeResult,
  parseRadioWeek,
  type RadioBulletin,
  type RadioDicteeOutcome,
  type RadioDicteeResult,
  type RadioWeek,
  type RadioWeekResult,
} from './radio-types';

export const RADIO_URL = '/revue/radio';

export type RadioTransport = {
  get: (url: string) => Promise<unknown>;
  post: (url: string, body: unknown) => Promise<unknown>;
};

export type RadioClient = {
  week: () => Promise<RadioWeekResult>;
  bulletin: (dossierId: string, band?: string | null) => Promise<RadioBulletin>;
  dictee: (dossierId: string, text: string, band?: string | null) => Promise<RadioDicteeResult>;
  heard: (dossierId: string, options?: { band?: string | null; dictee?: RadioDicteeOutcome | null }) => Promise<RadioWeek>;
};

const statusOf = (error: unknown): number => Number((error as { response?: { status?: number } } | null)?.response?.status) || 0;

export function createRadioClient(transport: RadioTransport): RadioClient {
  const call = async <T>(run: () => Promise<unknown>, parse: (raw: unknown) => T): Promise<T> => {
    try {
      return parse(await run());
    } catch (error) {
      if (error instanceof RadioError) throw error;
      throw new RadioError(statusOf(error));
    }
  };
  const path = (dossierId: string) => `${RADIO_URL}/${encodeURIComponent(dossierId)}`;
  return {
    async week() {
      try {
        return { enabled: true, week: parseRadioWeek(await transport.get(`${RADIO_URL}/week`)) };
      } catch (error) {
        const status = statusOf(error);
        if (status === 404) return { enabled: false };
        throw new RadioError(status);
      }
    },
    bulletin: (dossierId, band) =>
      call(() => transport.get(path(dossierId) + (band ? `?band=${encodeURIComponent(band)}` : '')), parseBulletin),
    dictee: (dossierId, text, band) =>
      call(() => transport.post(`${path(dossierId)}/dictee`, { text, band: band ?? null }), parseDicteeResult),
    heard: (dossierId, options = {}) =>
      call(
        () => transport.post(`${path(dossierId)}/heard`, { band: options.band ?? null, dictee: options.dictee ?? null }),
        parseRadioWeek,
      ),
  };
}

/** The app's authenticated client, with the global error toasts off. */
export function httpRadioTransport(): RadioTransport {
  // Required lazily so the pure client (and its node tests) never load axios.
  const { apiService } = require('@/services/api') as typeof import('@/services/api');
  const quiet = { suppressGlobalError: true } as Record<string, unknown>;
  return {
    get: (url) => apiService.get(url, quiet),
    post: (url, body) => apiService.post(url, body, quiet),
  };
}

let http: RadioClient | null = null;

export function radioClient(): RadioClient {
  if (!http) http = createRadioClient(httpRadioTransport());
  return http;
}
