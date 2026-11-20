/**
 * «Au comptoir» · step 5, «La page» (§3 step 5): Romy's thanks, then the vox pop
 * as the paper prints it — «Le micro-trottoir de Romy · <dateline>», the question,
 * one line from the lead, the three regulars and the learner (their «Ton
 * personnage» face, else «Toi») with their sides, the vote bar, «L'intox du jour»,
 * the words kept — the vignette stamped in, the colophon. «Classer le Papier» and
 * at most one quiet «Voir dans le Relevé» (both fit at 375 px).
 *
 * Opened after the close (`ended`): the page as filed, no thanks, no stamp, no foot.
 */

import React from 'react';

import { Action, CastPortrait } from '@/components/atelier-v2/ui';
import { AvatarDisc } from '@/components/avatar/Avatar';
import { frenchQuote } from '@/lib/french-typography';
import { useLearnerAvatar } from '@/lib/learner-avatar';
import type { RvComptoirPage as RvComptoirPageData, RvComptoirQuote, RvStance } from '@/lib/revue-types';

import { editionOf, pagePicture } from '../papier/papier-model';
import { PpByline, PpFigure, PpFrontCols, PpFrontPage, PpLead, type PpEdition, type PpPicture } from '../papier/PapierPrint';
import { fill, type RevueCopy } from '../revue-copy';
import { PICTURE_CREDIT_FR } from '../RvPicture';
import { RvCloseVignette, RvDispatch } from '../RvClose';
import { COMPTOIR_FR, type ComptoirCopy } from './comptoir-copy';
import { SIDE_LABELS_FR, voteTally } from './comptoir-model';
import { RomyLine, StanceTag, type ComptoirStepProps } from './RvComptoirParts';

function PageQuote({ quote, me = false, by = null, face, still = false }: { quote: RvComptoirQuote; me?: boolean; by?: string | null; face: React.ReactNode; still?: boolean }) {
  if (me) {
    // The learner's voice, the page's key element: set larger, signed in red small caps (stamped last).
    return (
      <div className="ct-quote" data-me="">
        <span className="ct-quote__face" aria-hidden="true">
          {face}
        </span>
        <div className="ct-quote__body pp-front__mine">
          <p className="ct-quote__fr pp-front__mine-fr" lang="fr" data-plain="">
            {frenchQuote(quote.quoteFr)}
          </p>
          <p className="ct-quote__by" lang="fr">
            <PpByline text={by ?? COMPTOIR_FR.you_by} still={still} />
            <StanceTag stance={quote.stance} />
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="ct-quote" data-me={me ? '' : undefined} data-char={me ? undefined : quote.castId}>
      <span className="ct-quote__face" aria-hidden="true">
        {face}
      </span>
      <div className="ct-quote__body">
        <p className="ct-quote__fr" lang="fr">
          {frenchQuote(quote.quoteFr)}
        </p>
        <p className="ct-quote__by" lang="fr">
          {me ? by ?? COMPTOIR_FR.you_by : `${quote.nameFr}, ${quote.roleFr}`}
          <StanceTag stance={quote.stance} />
        </p>
      </div>
    </div>
  );
}

/** The learner's face on the page: their «Ton personnage» character, else «Toi». */
function YouFace() {
  const { avatar } = useLearnerAvatar();
  if (avatar) return <AvatarDisc config={avatar} size={30} />;
  return (
    <span className="ct-toi" lang="fr">
      {COMPTOIR_FR.you}
    </span>
  );
}

export function ComptoirClipping({
  page,
  ccopy,
  edition = null,
  picture = null,
  still = false,
}: {
  page: RvComptoirPageData;
  ccopy: ComptoirCopy;
  /** «La belle édition»: the day and the number the page is printed with, and its picture. */
  edition?: PpEdition | null;
  picture?: PpPicture | null;
  still?: boolean;
}) {
  const tally = voteTally(page.votes);
  const counts: Record<RvStance, string> = { pour: String(page.votes.pour), nuance: String(page.votes.nuance), contre: String(page.votes.contre) };
  // «La belle édition» (2026-11-21): the vox pop as a front page — the question as the headline,
  // the standfirst with a drop cap, the picture, the learner's voice first and signed, then the
  // regulars, and the tally and «L'intox du jour» beside the boxed Lexique.
  return (
    <PpFrontPage
      edition={edition}
      kicker={COMPTOIR_FR.page_kicker}
      deck={picture ? null : page.datelineFr || null}
      headline={page.questionFr}
      still={still}
    >
      {page.standfirstFr && <PpLead text={page.standfirstFr} />}
      {picture && <PpFigure picture={picture} ratio="page" />}
      {/* The credit says when Romy corrected what the tries left (2026-10-23). */}
      <PageQuote quote={page.mine} me by={page.proof === 'corrected' ? COMPTOIR_FR.you_by_corrected : null} face={<YouFace />} still={still} />
      {page.quotes.map((quote) => (
        <PageQuote key={quote.castId} quote={quote} face={<CastPortrait characterId={quote.castId} name={quote.nameFr} size="xs" ring />} />
      ))}
      <PpFrontCols words={page.words} wordsLabel={ccopy.page_words}>
        <div className="ct-tally" role="img" aria-label={fill(ccopy.vote_aria, counts)}>
          <div className="ct-tally__bar" aria-hidden="true">
            {tally
              .filter((row) => row.count > 0)
              .map((row) => (
                <i key={row.stance} data-stance={row.stance} style={{ flexGrow: row.count }} />
              ))}
          </div>
          <p className="ct-tally__n" lang="fr" aria-hidden="true">
            {tally.map((row) => (
              <span key={row.stance}>
                {SIDE_LABELS_FR[row.stance]} {row.count}
              </span>
            ))}
          </p>
        </div>
        {page.intox && (
          <p className="ct-clip__intox" lang="fr">
            <b>{COMPTOIR_FR.page_intox}</b> {page.intox.nameFr}&nbsp;: {frenchQuote(page.intox.wrongFr)}&nbsp;? Non&nbsp;: {page.intox.rightFr}
            {page.intox.sourceName ? ` (${page.intox.sourceName})` : ''}.
          </p>
        )}
      </PpFrontCols>
    </PpFrontPage>
  );
}

export function RvComptoirPage({
  props,
  ended,
  onExit,
  onReleve,
}: {
  props: ComptoirStepProps;
  ended: boolean;
  onExit: () => void;
  onReleve?: () => void;
}) {
  const { session, copy, ccopy, readOnly, footRef, notice } = props;
  const closing = session.closing;
  const page = closing?.comptoirPage ?? null;
  return (
    <>
      <div className="rv-body ct-body" data-step="page">
        {closing && !ended && closing.romyLineFr && <RomyLine line={{ fr: closing.romyLineFr, tr: null }} props={props} />}
        {page ? (
          <ComptoirClipping
            page={page}
            ccopy={ccopy}
            edition={editionOf(session)}
            picture={pagePicture(session.stage, page.datelineFr || props.view.read?.datelineFr, PICTURE_CREDIT_FR)}
            still={ended}
          />
        ) : (
          closing && <RvDispatch {...closing.dispatch} readOnly copy={copy as RevueCopy} />
        )}
        {closing?.vignette && <RvCloseVignette vignette={closing.vignette} week={session.week.label} stamping={!ended} copy={copy} />}
        {closing && (
          <p className="rv-colophon" lang="fr">
            {closing.colophonFr}
          </p>
        )}
        {notice}
      </div>
      {!ended && !readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          <Action tone="done" onClick={onExit}>
            {copy.file_revue}
          </Action>
          {onReleve && (
            <Action tone="quiet" onClick={onReleve}>
              {copy.see_releve}
            </Action>
          )}
        </div>
      )}
    </>
  );
}

export default RvComptoirPage;
