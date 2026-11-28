/**
 * «Le bilan» — the typed client for `/bilan` (the Correcteur's shape, `lib/correcteur-api.ts`).
 *
 * The transport is the only part that knows the network; `httpBilanTransport()` uses the
 * app's authenticated axios client with the global toasts off. A bare 404 means the
 * switch (`BILAN_ENABLED`) is off and resolves to `{ enabled: false }`: nothing is drawn.
 */

import {
  BilanError,
  parseBilan,
  parseBilanCard,
  parseBilanError,
  type BilanCardResult,
  type BilanResult,
} from './bilan-types';

export const BILAN_BASE = '/bilan';
export const BILAN_HREF = '/bilan';

export type BilanTransport = { get: (url: string) => Promise<unknown> };

export type BilanClient = {
  week: (weekStart?: string | null) => Promise<BilanResult>;
  card: () => Promise<BilanCardResult>;
};

function toError(error: unknown): BilanError {
  if (error instanceof BilanError) return error;
  const response = (error as { response?: { status?: number } } | null)?.response;
  if (!response) return new BilanError(0, 'network');
  return parseBilanError(Number(response.status) || 0);
}

/** `/bilan?week=2026-11-16`, or `/bilan` for this week. */
export function bilanHref(weekStart?: string | null): string {
  return weekStart ? `${BILAN_HREF}?week=${encodeURIComponent(weekStart)}` : BILAN_HREF;
}

export function createBilanClient(transport: BilanTransport): BilanClient {
  return {
    async week(weekStart) {
      try {
        const url = weekStart ? `${BILAN_BASE}?week=${encodeURIComponent(weekStart)}` : BILAN_BASE;
        return { enabled: true, bilan: parseBilan(await transport.get(url)) };
      } catch (error) {
        const failure = toError(error);
        if (failure.code === 'bilan_disabled') return { enabled: false };
        throw failure;
      }
    },
    async card() {
      try {
        return { enabled: true, card: parseBilanCard(await transport.get(`${BILAN_BASE}/card`)) };
      } catch (error) {
        const failure = toError(error);
        if (failure.code === 'bilan_disabled') return { enabled: false };
        throw failure;
      }
    },
  };
}

export function httpBilanTransport(): BilanTransport {
  // Required lazily so the pure client (and its node tests) never load axios.
  const { apiService } = require('@/services/api') as typeof import('@/services/api');
  const quiet = { suppressGlobalError: true } as Record<string, unknown>;
  return { get: (url) => apiService.get(url, quiet) };
}

let shared: BilanClient | null = null;

export function bilanClient(): BilanClient {
  if (!shared) shared = createBilanClient(httpBilanTransport());
  return shared;
}
