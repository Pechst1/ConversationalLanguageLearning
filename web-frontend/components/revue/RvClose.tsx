/**
 * WP-119 · the close (design §3.6): RvDispatch, the clipping, and RvKept,
 * «Pour ton Relevé».
 *
 * The dispatch: a double rule, the kicker, a Garamond headline with the
 * learner's part marked (underline + «toi»), three lines, the byline with
 * Romy's face. RvKept: the plan's words as WordToken rows with their gloss,
 * then the claims shown with their source lines. Phase 2: a word the rubric
 * found used correctly (WIRE §6.3 `words[].outcome`) wears the Relevé's mark for
 * a learned word (the ink «known» token) and says so in words.
 *
 * WP-120: `RvCloseVignette` — the vignette the close minted, stamped in (300 ms,
 * none under reduced motion) before «Classer».
 */

import React from 'react';

import { CastPortrait, WordToken } from '@/components/atelier-v2/ui';
import type { RvClaim, RvKeptWord, RvLanguage, RvSource, RvSpan } from '@/lib/revue-types';

import type { RvVignetteView } from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';
import { wordOutcome, type WordOutcomes } from './revue-model';
import { ContributedText, RvSourceLine } from './RvThread';
import { RvVignette } from './RvVignette';

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
  outcomes = {},
}: {
  words: RvKeptWord[];
  claims: RvClaim[];
  glossLanguage?: RvLanguage;
  copy: RevueCopy;
  now?: Date;
  /** Phase 2: the rubric's outcome per word, merged over the session (correct wins). */
  outcomes?: WordOutcomes;
}) {
  return (
    <section className="rv-kept" aria-label={copy.for_releve}>
      <div className="rv-kept__head">
        <h2 className="rv-kept__t">{copy.for_releve}</h2>
        <span className="rv-kept__n">{fill(copy.kept_count, { w: words.length, c: claims.length })}</span>
      </div>
      {words.length > 0 && (
        <ul className="rv-kept__rows">
          {words.map((word) => {
            const right = wordOutcome(outcomes, word.fr) === 'correct';
            return (
              <li key={`${word.claimId}-${word.fr}`} className="rv-kept__row" data-outcome={right ? 'correct' : undefined}>
                <WordToken word={word.fr} gender={wordGender(word.fr)} state={right ? 'mastered' : word.used ? 'learning' : 'new'} size="sm" />
                <span className="rv-kept__fr" lang="fr">
                  {word.fr}
                  {right && <span className="rv-kept__right">{copy.kept_word_right}</span>}
                </span>
                <span className="rv-kept__de" lang={glossLanguage}>
                  {word.gloss}
                </span>
              </li>
            );
          })}
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

/** WP-120 §4.3 · the vignette the close minted, stamped in before «Classer». */
export function RvCloseVignette({ vignette, week, stamping = true, copy }: { vignette: RvVignetteView; week: string; stamping?: boolean; copy: RevueCopy }) {
  return (
    <section className="rv-close-vignette" aria-label={fill(copy.vignette_label, { week })}>
      <p className="av2-label">{fill(copy.vignette_label, { week })}</p>
      <RvVignette
        week={vignette.week}
        placeLabelFr={vignette.placeLabelFr}
        ring={vignette.ring}
        keptContribution={vignette.keptContribution}
        pictogramSvg={vignette.pictogramSvg}
        size="large"
        stamping={stamping}
      />
    </section>
  );
}
