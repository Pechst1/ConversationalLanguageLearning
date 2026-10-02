/**
 * WP-120 phase C · La Carte — the client for `GET /revue/carte`.
 *
 * Same shape as `lib/revue-api.ts`: a transport-agnostic client (`createCarteClient`)
 * and the app's authenticated, quiet axios transport. A 404 means the Revue flag is
 * off: `{ enabled: false }`, and the page says so instead of failing.
 */

import { CarteError, parseCarteView, type CarteResult } from './carte-types';

export const CARTE_URL = '/revue/carte';

export type CarteTransport = { get: (url: string) => Promise<unknown> };

export type CarteClient = { carte: () => Promise<CarteResult> };

export function createCarteClient(transport: CarteTransport): CarteClient {
  return {
    async carte() {
      try {
        return { enabled: true, view: parseCarteView(await transport.get(CARTE_URL)) };
      } catch (error) {
        const status = Number((error as { response?: { status?: number } } | null)?.response?.status) || 0;
        if (status === 404) return { enabled: false };
        throw new CarteError(status);
      }
    },
  };
}

/** The app's authenticated client, with the global error toasts off. */
export function httpCarteTransport(): CarteTransport {
  // Required lazily so the pure client (and its node tests) never load axios.
  const { apiService } = require('@/services/api') as typeof import('@/services/api');
  const quiet = { suppressGlobalError: true } as Record<string, unknown>;
  return { get: (url) => apiService.get(url, quiet) };
}

let http: CarteClient | null = null;

export function carteClient(): CarteClient {
  if (!http) http = createCarteClient(httpCarteTransport());
  return http;
}
