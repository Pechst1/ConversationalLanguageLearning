/**
 * «Le fil» · «La page»: Romy's thanks, then the wire as the paper prints it — «Le fil de
 * Romy · <dateline>», the headline, the four dispatches in order each under its sequence
 * word, the learner's telling under «Toi» with how it reached print, the words kept —
 * the vignette stamped in, the colophon. «Classer le Papier» and at most one quiet «Voir
 * dans le Relevé» (both fit at 375 px). Opened after the close: the page as filed.
 */

import React from 'react';

import { Action } from '@/components/atelier-v2/ui';
import type { RvFilPage as RvFilPageData } from '@/lib/revue-fil-types';

import type { ComptoirCopy } from '../comptoir/comptoir-copy';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { RvCloseVignette, RvDispatch } from '../RvClose';
import { bylineFr, editionOf, pagePicture } from '../papier/papier-model';
import { PpFigure, PpFrontCols, PpFrontPage, PpMine, type PpEdition, type PpPicture } from '../papier/PapierPrint';
import { PICTURE_CREDIT_FR } from '../RvPicture';
import { FIL_FR } from './fil-copy';
import type { FilStepProps } from './RvFilSteps';

export function FilClipping({
  page,
  ccopy,
  tiles = false,
  edition = null,
  picture = null,
  still = false,
}: {
  page: RvFilPageData;
  ccopy: ComptoirCopy;
  tiles?: boolean;
  /** «La belle édition»: the day and the number the page is printed with. */
  edition?: PpEdition | null;
  picture?: PpPicture | null;
  still?: boolean;
}) {
  // «La belle édition» (2026-11-21): a front page. The learner's telling is the article, set as
  // its lead with a drop cap and signed; the wire runs under it, its words printed between the
  // dispatches, beside the boxed Lexique.
  return (
    <PpFrontPage
      className="fl-clip"
      edition={edition}
      kicker={FIL_FR.page_kicker}
      deck={picture ? null : page.datelineFr || null}
      headline={page.titleFr}
      still={still}
    >
      <PpMine textFr={page.mineFr} byline={bylineFr(page.proof, tiles)} still={still} lead />
      {picture && <PpFigure picture={picture} ratio="page" />}
      <PpFrontCols words={page.words} wordsLabel={ccopy.page_words}>
        <p className="pp-front__section" lang="fr">
          {FIL_FR.name}
        </p>
        <ol className="fl-wire" lang="fr">
          {page.strips.map((strip, index) => (
            <li key={index} className="fl-wire__row">
              <span className="fl-wire__word">{strip.connectorFr}</span>
              <span className="fl-wire__fr">{strip.textFr}</span>
            </li>
          ))}
        </ol>
      </PpFrontCols>
    </PpFrontPage>
  );
}

export function RvFilPage({ props, ended, onExit, onReleve }: { props: FilStepProps; ended: boolean; onExit: () => void; onReleve?: () => void }) {
  const { session, copy, ccopy, readOnly, footRef, notice } = props;
  const closing = session.closing;
  const page = closing?.filPage ?? null;
  return (
    <>
      <div className="rv-body ct-body" data-step="page">
        {page ? (
          <FilClipping
            page={page}
            ccopy={ccopy}
            tiles={props.view.tell?.input === 'tiles'}
            edition={editionOf(session)}
            picture={pagePicture(session.stage, page.datelineFr || props.view.read.datelineFr, PICTURE_CREDIT_FR)}
            still={ended}
          />
        ) : (
          closing && <RvDispatch {...closing.dispatch} readOnly copy={copy} />
        )}
        {/* «La belle édition»: the front page opens the screen; Romy's thanks follow it. */}
        {closing && !ended && closing.romyLineFr && <RomyLine line={{ fr: closing.romyLineFr, tr: null }} props={props} />}
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

export default RvFilPage;
