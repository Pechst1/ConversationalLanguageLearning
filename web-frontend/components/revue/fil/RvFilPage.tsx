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

import { inPaperLabel, type ComptoirCopy } from '../comptoir/comptoir-copy';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { RvTroisMotsSlot } from '../rdv/RvTroisMots';
import { RvCloseVignette, RvDispatch } from '../RvClose';
import { FIL_FR } from './fil-copy';
import type { FilStepProps } from './RvFilSteps';

export function FilClipping({ page, ccopy, tiles = false }: { page: RvFilPageData; ccopy: ComptoirCopy; tiles?: boolean }) {
  return (
    <article className="ct-clip fl-clip" data-ct-anchor="start">
      <p className="ct-clip__k" lang="fr">
        {FIL_FR.page_kicker}
        {page.datelineFr ? ` · ${page.datelineFr}` : ''}
      </p>
      <h2 className="ct-clip__hl" lang="fr">
        {page.titleFr}
      </h2>
      <ol className="fl-wire" lang="fr">
        {page.strips.map((strip, index) => (
          <li key={index} className="fl-wire__row">
            <span className="fl-wire__word">{strip.connectorFr}</span>
            <span className="fl-wire__fr">{strip.textFr}</span>
          </li>
        ))}
      </ol>
      <div className="ct-quote" data-me="">
        <span className="ct-quote__face">
          <span className="ct-toi" aria-hidden="true" lang="fr">
            {FIL_FR.you}
          </span>
        </span>
        <div className="ct-quote__body">
          <p className="ct-quote__fr" lang="fr">
            {page.mineFr}
          </p>
          <p className="ct-quote__by" lang="fr">
            {FIL_FR.you} · {inPaperLabel(page.proof ?? 'as_written', tiles)}
          </p>
        </div>
      </div>
      {page.words.length > 0 && (
        <div className="ct-words" aria-label={ccopy.page_words}>
          {page.words.map((word) => (
            <span key={word} lang="fr">
              {word}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

export function RvFilPage({ props, ended, onExit, onReleve }: { props: FilStepProps; ended: boolean; onExit: () => void; onReleve?: () => void }) {
  const { session, copy, ccopy, readOnly, footRef, notice } = props;
  const closing = session.closing;
  const page = closing?.filPage ?? null;
  return (
    <>
      <div className="rv-body ct-body" data-step="page">
        <RvTroisMotsSlot sessionId={session.id} chrome={session.plan.uiLanguage} mother={session.plan.glossLanguage} closed={Boolean(closing) && !props.readOnly} />
        {closing && !ended && closing.romyLineFr && <RomyLine line={{ fr: closing.romyLineFr, tr: null }} props={props} />}
        {page ? <FilClipping page={page} ccopy={ccopy} tiles={props.view.tell?.input === 'tiles'} /> : closing && <RvDispatch {...closing.dispatch} readOnly copy={copy} />}
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
