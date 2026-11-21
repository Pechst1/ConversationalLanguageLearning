/**
 * «La carte de presse» (2026-11-21, inside `REVUE_UNE_ENABLED`): on the Relevé, which of the six
 * rubriques the learner has filed, how many pieces, since when — purely derived from their filed
 * Papiers. No points, no streak, no mascot. Draws NOTHING while the switch is off, the read
 * fails, or before the first piece. Its one door: «La une de la semaine».
 */

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import type { RvLanguage } from '@/lib/revue-types';
import { rdvClient as defaultClient, type RdvClient, type RvCarteDePresse as Card } from '@/lib/revue-rdv';

import { RDV_FR, countLine, dayLabel, fillRdv, rdvCopy } from './rdv-copy';

export const UNE_HREF = '/revue/une';

export function RvCarteDePresseCard({ card, language }: { card: Card; language: RvLanguage }) {
  const copy = rdvCopy(language);
  return (
    <section className="rv-carte-presse" aria-labelledby="rv-carte-presse" data-carte-presse="">
      <h3 id="rv-carte-presse" lang="fr">
        {RDV_FR.carte}
      </h3>
      <p className="rv-carte-presse__since">
        {card.since ? fillRdv(copy.carte_since, { date: dayLabel(card.since, language) }) : copy.carte_none}
        {' · '}
        {countLine(copy, 'carte_pieces', card.pieces)}
      </p>
      <dl className="rv-carte-presse__list">
        {card.rubriques.map((row) => (
          <div key={row.rubrique} data-filed={row.pieces > 0 ? '' : undefined}>
            <dt lang="fr">{RDV_FR.rubriques[row.rubrique]}</dt>
            <dd>{row.pieces > 0 ? countLine(copy, 'carte_filed', row.pieces) : copy.carte_not_yet}</dd>
          </div>
        ))}
      </dl>
      <Link href={UNE_HREF} className="nb-rv__door" data-une-door="">
        {copy.une_door}
      </Link>
    </section>
  );
}

/** The Relevé's slot: fetches the card, nothing before the first piece or while off. */
export function RvCarteDePresse({ language, client }: { language: RvLanguage; client?: RdvClient }) {
  const [card, setCard] = useState<Card | null>(null);
  useEffect(() => {
    let alive = true;
    (client ?? defaultClient())
      .carteDePresse()
      .then((next) => {
        if (alive) setCard(next);
      })
      .catch(() => {
        // The card is an extra on the Relevé.
      });
    return () => {
      alive = false;
    };
  }, [client]);
  if (!card || card.pieces === 0) return null;
  return <RvCarteDePresseCard card={card} language={language} />;
}
