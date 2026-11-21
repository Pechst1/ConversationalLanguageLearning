/**
 * «Papier · les rendez-vous»: the page's client for the routes of the regulars' memory and
 * «Trois mots», handed to the players' slots without threading it through their props. No
 * provider (a test, a preview, an older page): the slots draw nothing.
 */

import React, { createContext, useContext } from 'react';

import type { RdvClient } from '@/lib/revue-rdv';

const RdvContext = createContext<RdvClient | null>(null);

export function RdvProvider({ client, children }: { client: RdvClient | null; children: React.ReactNode }) {
  return <RdvContext.Provider value={client}>{children}</RdvContext.Provider>;
}

export function useRdv(): RdvClient | null {
  return useContext(RdvContext);
}
