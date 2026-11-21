/**
 * «La carte de presse» (2026-11-21, inside `REVUE_UNE_ENABLED`): on the Relevé, which of the six
 * rubriques the learner has filed, how many pieces, since when — purely derived from their filed
 * Papiers. No points, no streak, no mascot. Draws NOTHING while the switch is off, the read
 * fails, or before the first piece. Its one door: «La une de la semaine».
 */

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import { useAppSession } from '@/lib/app-auth';
import type { RvLanguage } from '@/lib/revue-types';
import { rdvClient as defaultClient, type RdvClient, type RvCarteDePresse as Card } from '@/lib/revue-rdv';

import { PAPIER_FR } from '../papier/papier-copy';
import { stampTilt } from '../papier/papier-model';
import { PpInkDefs } from '../papier/PapierPrint';
import { RDV_FR, countLine, dayLabel, fillRdv, rdvCopy } from './rdv-copy';

export const UNE_HREF = '/revue/une';

/** The learner's first name as the card prints it ('' when the session has none, or only an e-mail). */
export function cardName(raw: string | null | undefined): string {
  const name = (raw ?? '').trim();
  if (!name || name.includes('@')) return '';
  return name.split(/\s+/)[0].slice(0, 24);
}

/** The session's name, when there is a signed-in session (never thrown outside the app's provider). */
function useCardName(): string {
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks -- always called, in the same order; it throws only outside the provider
    return cardName(useAppSession().data?.user?.name);
  } catch {
    return '';
  }
}

/**
 * «La belle édition»: a press card — «Carte de presse» over its rule, the learner's initial
 * in the photo box, their first name, «Stagiaire · Le Papier», since when and how many pieces;
 * the six rubriques as stamped boxes (stamped in the editor's red once filed, an empty outline
 * until then). No points, no streak.
 */
export function RvCarteDePresseCard({ card, language, name = '' }: { card: Card; language: RvLanguage; name?: string }) {
  const copy = rdvCopy(language);
  const first = cardName(name);
  return (
    <section className="rv-carte-presse pp-carte" aria-labelledby="rv-carte-presse" data-carte-presse="">
      <div className="pp-carte__head">
        <h3 id="rv-carte-presse" className="pp-carte__title" lang="fr">
          {RDV_FR.carte}
        </h3>
        <span className="pp-carte__paper" lang="fr" aria-hidden="true">
          {PAPIER_FR.masthead}
        </span>
      </div>
      <div className="pp-carte__id">
        {first && (
          <span className="pp-carte__photo" aria-hidden="true">
            {first.charAt(0).toUpperCase()}
          </span>
        )}
        <div className="pp-carte__who">
          {first && (
            <p className="pp-carte__name" lang="fr">
              {first}
            </p>
          )}
          <p className="pp-carte__role" lang="fr">
            {PAPIER_FR.stagiaire}
          </p>
          <p className="rv-carte-presse__since">
            <span>{card.since ? fillRdv(copy.carte_since, { date: dayLabel(card.since, language) }) : copy.carte_none}</span>
            {' · '}
            <span>{countLine(copy, 'carte_pieces', card.pieces)}</span>
          </p>
        </div>
      </div>
      <dl className="rv-carte-presse__list pp-carte__stamps">
        {card.rubriques.map((row) => {
          const filed = row.pieces > 0;
          const nameFr = RDV_FR.rubriques[row.rubrique];
          const style = { '--pp-tilt': `${stampTilt(`carte:${row.rubrique}`) / 2}deg` } as React.CSSProperties;
          return (
            <div
              key={row.rubrique}
              className="pp-carte__box"
              data-filed={filed ? '' : undefined}
              style={filed ? style : undefined}
            >
              <dt lang="fr">{nameFr}</dt>
              <dd>{filed ? countLine(copy, 'carte_filed', row.pieces) : copy.carte_not_yet}</dd>
            </div>
          );
        })}
      </dl>
      <PpInkDefs />
      <Link href={UNE_HREF} className="nb-rv__door pp-carte__door" data-une-door="">
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
  const name = useCardName();
  if (!card || card.pieces === 0) return null;
  return <RvCarteDePresseCard card={card} language={language} name={name} />;
}
