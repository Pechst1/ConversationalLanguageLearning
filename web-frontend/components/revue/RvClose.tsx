/**
 * WP-119 · the close (design §3.6): RvDispatch, the clipping, and RvKept,
 * «Pour ton Relevé».
 *
 * The dispatch: a double rule, the kicker, a Garamond headline with the
 * learner's part marked (underline + «toi»), three lines, the byline with
 * Romy's face. RvKept: the plan's words as WordToken rows with their gloss,
 * then the claims shown with their source lines.
 */

import React from 'react';

import { CastPortrait, WordToken } from '@/components/atelier-v2/ui';
import type { RvClaim, RvKeptWord, RvLanguage, RvSource, RvSpan } from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';
import { ContributedText, RvSourceLine } from './RvThread';

export type RvDispatchProps = {
  kickerFr: string;
  headlineFr: string;
  bodyFr?: string[];
  contribution: RvSpan[];
  bylineFr: string;
  sources: RvSource[];
  readOnly?: boolean;
  copy: RevueCopy;
};

export function RvDispatch({ kickerFr, headlineFr, bodyFr = [], contribution, bylineFr, copy }: RvDispatchProps) {
  return (
    <article className="rv-dispatch" lang="fr" data-dispatch="">
      <div className="rv-dispatch__rule" aria-hidden="true" />
      <p className="rv-kicker">{kickerFr}</p>
      <h2 className="rv-dispatch__hl">
        <ContributedText text={headlineFr} spans={contribution} label={copy.contribution} />
      </h2>
      {bodyFr.length > 0 && <p className="rv-dispatch__body">{bodyFr.join(' ')}</p>}
      <p className="rv-dispatch__by">
        <CastPortrait characterId="romy_tremblay" name="Romy" size="xs" ring />
        <span>{bylineFr}</span>
      </p>
    </article>
  );
}

function wordGender(fr: string): string | null {
  const lead = fr.trim().toLowerCase();
  if (lead.startsWith('la ') || lead.startsWith('une ')) return 'f';
  if (lead.startsWith('le ') || lead.startsWith('un ')) return 'm';
  return null;
}

export function RvKept({
  words,
  claims,
  glossLanguage = 'en',
  copy,
  now,
}: {
  words: RvKeptWord[];
  claims: RvClaim[];
  glossLanguage?: RvLanguage;
  copy: RevueCopy;
  now?: Date;
}) {
  return (
    <section className="rv-kept" aria-label={copy.for_releve}>
      <div className="rv-kept__head">
        <h2 className="rv-kept__t">{copy.for_releve}</h2>
        <span className="rv-kept__n">{fill(copy.kept_count, { w: words.length, c: claims.length })}</span>
      </div>
      {words.length > 0 && (
        <ul className="rv-kept__rows">
          {words.map((word) => (
            <li key={`${word.claimId}-${word.fr}`} className="rv-kept__row">
              <WordToken word={word.fr} gender={wordGender(word.fr)} state={word.used ? 'learning' : 'new'} size="sm" />
              <span className="rv-kept__fr" lang="fr">
                {word.fr}
              </span>
              <span className="rv-kept__de" lang={glossLanguage}>
                {word.gloss}
              </span>
            </li>
          ))}
        </ul>
      )}
      {claims.length > 0 && (
        <ul className="rv-kept__rows">
          {claims.map((claim) => (
            <li key={claim.id} className="rv-kept__row" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 2 }}>
              <span className="rv-kept__fr" lang="fr">
                {claim.fr}
              </span>
              <RvSourceLine source={claim.source} copy={copy} now={now} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
