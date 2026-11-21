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

import type { ComptoirCopy } from '../comptoir/comptoir-copy';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { fill } from '../revue-copy';
import { RvCloseVignette, RvDispatch } from '../RvClose';
import { papierCopy } from '../papier/papier-copy';
import { bylineFr, editionOf, pagePicture } from '../papier/papier-model';
import { PpByline, PpFigure, PpFrontCols, PpFrontPage, PpLead, PpStamp, type PpEdition, type PpPicture } from '../papier/PapierPrint';
import { PICTURE_CREDIT_FR } from '../RvPicture';
import { INTOX_FR, TITRE_FR } from './rubriques-copy';
import type { RubriqueStepProps } from './RvRubriqueParts';

/** The page's byline with its sources («… · d'après …», the close's dispatch), else Romy's own. */
/** The intox page's signature: the learner checked the statements. */
const INTOX_BYLINE_FR = 'Vérifié par toi';

function bylineOf(byline: string | null | undefined, fallback: string): string {
  return byline && byline.trim() ? byline.trim() : fallback;
}

type PageExtras = {
  /** «La belle édition»: the day and the number the page is printed with, and its picture. */
  edition?: PpEdition | null;
  picture?: PpPicture | null;
  still?: boolean;
  /** The chrome language (what a screen reader hears of a stamp). */
  language?: string;
};

export function TitreClipping({
  page,
  ccopy,
  tiles = false,
  byline,
  edition = null,
  picture = null,
  still = false,
  language = 'fr',
}: { page: RvTitrePage; ccopy: ComptoirCopy; tiles?: boolean; byline?: string | null } & PageExtras) {
  // «La belle édition»: the learner's headline is the page's headline — the kicker says it is
  // theirs — signed under it in red small caps by how it reached print; the story runs as its
  // standfirst with a drop cap, then its picture, then Romy's credit and sources as a short list.
  return (
    <PpFrontPage className="rb-clip" edition={edition} kicker={papierCopy(language).page_kicker_mine} headline={page.headlineFr} deck={picture ? null : page.datelineFr || null} still={still}>
      <PpByline text={bylineFr(page.proof, tiles)} still={still} />
      <PpLead text={page.leadFr} />
      {picture && <PpFigure picture={picture} ratio="page" />}
      <Sources text={bylineOf(byline, TITRE_FR.byline)} />
      <PpFrontCols words={page.words} wordsLabel={ccopy.page_words} />
    </PpFrontPage>
  );
}

/** Romy's credit and the sources, one per line, in the small sans (never a block of capitals). */
function Sources({ text }: { text: string | null | undefined }) {
  const parts = (text ?? '')
    .split(/\s+·\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) return null;
  return (
    <ul className="ct-quote__by pp-front__sources" lang="fr">
      {parts.map((part, index) => (
        <li key={index}>{part}</li>
      ))}
    </ul>
  );
}

export function IntoxClipping({ page, ccopy, byline, edition = null, picture = null, still = false, language = 'fr' }: { page: RvIntoxPage; ccopy: ComptoirCopy; byline?: string | null } & PageExtras) {
  // «La belle édition»: the five statements as the fact-check box prints them, each stamped
  // «VRAI» or «INTOX», the false words struck beside the true line, the learner's own fixes.
  const pcopy = papierCopy(language);
  return (
    <PpFrontPage
      className="rb-clip"
      edition={edition}
      kicker={INTOX_FR.page_kicker}
      deck={picture ? null : page.datelineFr || null}
      headline={page.titleFr}
      still={still}
    >
      {picture && <PpFigure picture={picture} ratio="page" />}
      <p className="pp-front__section" lang="fr">
        {INTOX_FR.name}
      </p>
      <ol className="fl-wire pp-checks" lang="fr">
        {page.lines.map((line, index) => (
          <li key={index} className="fl-wire__row rb-page-line" data-false={line.wasFalse ? '' : undefined} data-right={line.answeredRight ? '' : undefined}>
            <span className="fl-wire__fr">{line.textFr}</span>
            <PpStamp
              kind={line.wasFalse ? 'intox' : 'vrai'}
              seed={`${page.titleFr}:${index}`}
              label={line.wasFalse ? pcopy.stamp_intox_aria : pcopy.stamp_vrai_aria}
              size="sm"
              still
            />
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
      <PpFrontCols words={page.words} wordsLabel={ccopy.page_words}>
        {/* The learner's part: the statements they settled, set as the page's figure, and signed. */}
        <p className="rb-score__n pp-front__figure" lang="fr">
          {fill(INTOX_FR.score, { n: String(page.score), total: String(page.total) })}
        </p>
        <PpByline text={INTOX_BYLINE_FR} still={still} />
      </PpFrontCols>
      <Sources text={byline} />
    </PpFrontPage>
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
  const edition = editionOf(session);
  const scene = closing?.titrePage?.datelineFr || closing?.intoxPage?.datelineFr || null;
  const picture = pagePicture(session.stage, scene, PICTURE_CREDIT_FR);
  const extras = { edition, picture, still: ended, language: props.chrome };
  if (closing?.titrePage) clipping = <TitreClipping page={closing.titrePage} ccopy={ccopy} tiles={tiles} byline={closing.dispatch?.bylineFr} {...extras} />;
  else if (closing?.intoxPage) clipping = <IntoxClipping page={closing.intoxPage} ccopy={ccopy} byline={closing.dispatch?.bylineFr} {...extras} />;
  else if (closing) clipping = <RvDispatch {...closing.dispatch} readOnly copy={copy} />;
  return (
    <>
      <div className="rv-body ct-body" data-step="page">
        {clipping}
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
