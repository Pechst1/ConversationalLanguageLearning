/**
 * «Le titre» and «L'intox express» · «La page» (no model call at the close).
 *
 * «Le titre»: the story under the learner's headline, signed «Romy Tremblay, avec toi · d'après
 * …» (its sources, from the close's dispatch), with how the headline reached print. «L'intox express»: the five statements as they should read
 * (the false words struck beside them), the learner's score and own right corrections. Then
 * Romy's thanks, the vignette, the colophon, «Classer le Papier» and at most one quiet «Voir
 * dans le Relevé». Opened after the close: the page as filed.
 */

import React from 'react';

import { Action } from '@/components/atelier-v2/ui';
import type { RvIntoxPage, RvTitrePage } from '@/lib/revue-rubriques-types';

import { inPaperLabel, type ComptoirCopy } from '../comptoir/comptoir-copy';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { fill } from '../revue-copy';
import { RvTroisMotsSlot } from '../rdv/RvTroisMots';
import { RvCloseVignette, RvDispatch } from '../RvClose';
import { INTOX_FR, TITRE_FR } from './rubriques-copy';
import type { RubriqueStepProps } from './RvRubriqueParts';

function Words({ words, ccopy }: { words: string[]; ccopy: ComptoirCopy }) {
  if (!words.length) return null;
  return (
    <div className="ct-words" aria-label={ccopy.page_words}>
      {words.map((word) => (
        <span key={word} lang="fr">
          {word}
        </span>
      ))}
    </div>
  );
}

/** The page's byline with its sources («… · d'après …», the close's dispatch), else Romy's own. */
function bylineOf(byline: string | null | undefined, fallback: string): string {
  return byline && byline.trim() ? byline.trim() : fallback;
}

export function TitreClipping({ page, ccopy, tiles = false, byline }: { page: RvTitrePage; ccopy: ComptoirCopy; tiles?: boolean; byline?: string | null }) {
  return (
    <article className="ct-clip rb-clip" data-ct-anchor="start">
      <p className="ct-clip__k" lang="fr">
        {TITRE_FR.page_kicker}
        {page.datelineFr ? ` · ${page.datelineFr}` : ''}
      </p>
      <h2 className="ct-clip__hl" lang="fr">
        {page.headlineFr}
      </h2>
      <p className="ct-clip__ld" lang="fr">
        {page.leadFr}
      </p>
      <p className="ct-quote__by" lang="fr">
        {bylineOf(byline, TITRE_FR.byline)} · {inPaperLabel(page.proof ?? 'as_written', tiles)}
      </p>
      <Words words={page.words} ccopy={ccopy} />
    </article>
  );
}

export function IntoxClipping({ page, ccopy, byline }: { page: RvIntoxPage; ccopy: ComptoirCopy; byline?: string | null }) {
  return (
    <article className="ct-clip rb-clip" data-ct-anchor="start">
      <p className="ct-clip__k" lang="fr">
        {INTOX_FR.page_kicker}
        {page.datelineFr ? ` · ${page.datelineFr}` : ''}
      </p>
      <h2 className="ct-clip__hl" lang="fr">
        {page.titleFr}
      </h2>
      <p className="rb-score__n" lang="fr">
        {fill(INTOX_FR.score, { n: String(page.score), total: String(page.total) })}
      </p>
      <ol className="fl-wire" lang="fr">
        {page.lines.map((line, index) => (
          <li key={index} className="fl-wire__row rb-page-line" data-false={line.wasFalse ? '' : undefined} data-right={line.answeredRight ? '' : undefined}>
            <span className="fl-wire__fr">{line.textFr}</span>
            {line.wasFalse && line.wrongFr && (
              <span className="rb-page-line__was">
                {INTOX_FR.was} <s className="ct-strike">{line.wrongFr}</s>
              </span>
            )}
            {line.learnerFr && (
              <span className="rb-page-line__mine">
                {INTOX_FR.fixed} : « {line.learnerFr} »
              </span>
            )}
          </li>
        ))}
      </ol>
      {byline && (
        <p className="ct-quote__by" lang="fr">
          {byline}
        </p>
      )}
      <Words words={page.words} ccopy={ccopy} />
    </article>
  );
}

export function RvRubriquePage({
  props,
  ended,
  tiles,
  onExit,
  onReleve,
}: {
  props: RubriqueStepProps;
  ended: boolean;
  tiles: boolean;
  onExit: () => void;
  onReleve?: () => void;
}) {
  const { session, copy, ccopy, readOnly, footRef, notice } = props;
  const closing = session.closing;
  let clipping: React.ReactNode = null;
  if (closing?.titrePage) clipping = <TitreClipping page={closing.titrePage} ccopy={ccopy} tiles={tiles} byline={closing.dispatch?.bylineFr} />;
  else if (closing?.intoxPage) clipping = <IntoxClipping page={closing.intoxPage} ccopy={ccopy} byline={closing.dispatch?.bylineFr} />;
  else if (closing) clipping = <RvDispatch {...closing.dispatch} readOnly copy={copy} />;
  return (
    <>
      <div className="rv-body ct-body" data-step="page">
        <RvTroisMotsSlot sessionId={session.id} chrome={session.plan.uiLanguage} mother={session.plan.glossLanguage} closed={Boolean(closing) && !props.readOnly} />
        {closing && !ended && closing.romyLineFr && <RomyLine line={{ fr: closing.romyLineFr, tr: null }} props={props} />}
        {clipping}
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
