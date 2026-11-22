/**
 * Le Quartier · today's Papier for the Morris column, from the week's offer (`GET /revue/week`).
 * Apart from `affiche-model.ts` so the street (`quai.ts`, the engine) never loads the Revue's
 * client code: the page reads the offer, the street only prints what it is handed.
 */
import type { RvOffer } from '@/lib/revue-types';
import { revueOpenHref } from '@/lib/revue-une';

import { frenchDate, wrapHeadline } from './affiche-model';
import type { Affiche } from './affiche-model';

/** Today's poster from the week's offer, or `null`: the switch is off or there is no edition today. */
export function afficheOf(offer: RvOffer | null | undefined, today: Date): Affiche | null {
  const poster = offer?.affiche;
  const headline = poster?.headlineFr?.trim();
  if (!offer || !poster || !headline) return null;
  return { date: frenchDate(today), headline, lines: wrapHeadline(headline), done: poster.done, route: revueOpenHref(offer) };
}
