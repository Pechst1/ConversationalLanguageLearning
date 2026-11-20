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
import type { RvIntoxPage, RvMicroPage, RvPhotoPage, RvTitrePage } from '@/lib/revue-rubriques-types';

import { inPaperLabel, type ComptoirCopy } from '../comptoir/comptoir-copy';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { fill } from '../revue-copy';
import { RvCloseVignette, RvDispatch } from '../RvClose';
import { RvGalleryPicture } from '../RvGallery';
import type { RevueCopy } from '../revue-copy';
import { MICRO_FR, PHOTO_FR } from './photo-micro-copy';
import { asRvPicture } from './photo-micro-model';
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

/** «La photo»: the picture printed large, the learner's caption under it, its credit, signed with the sources. */
export function PhotoClipping({ page, ccopy, copy, tiles = false, byline }: { page: RvPhotoPage; ccopy: ComptoirCopy; copy: RevueCopy; tiles?: boolean; byline?: string | null }) {
  return (
    <article className="ct-clip rb-clip" data-ct-anchor="start">
      <p className="ct-clip__k" lang="fr">
        {PHOTO_FR.page_kicker}
        {page.datelineFr ? ` · ${page.datelineFr}` : ''}
      </p>
      <h2 className="ct-clip__hl" lang="fr">
        {page.titleFr}
      </h2>
      <div className="rb-clip__pic">
        <RvGalleryPicture picture={asRvPicture(page.picture)} copy={copy} />
      </div>
      <p className="ct-clip__ld rb-clip__cap" lang="fr">
        {page.captionFr}
      </p>
      <p className="ct-quote__by" lang="fr">
        {bylineOf(byline, PHOTO_FR.byline)} · {inPaperLabel(page.proof ?? 'as_written', tiles)}
      </p>
      <Words words={page.words} ccopy={ccopy} />
    </article>
  );
}

/** «Le micro»: the interview as Q&A under the learner's name, each answer's source printed. */
export function MicroClipping({ page, ccopy, byline }: { page: RvMicroPage; ccopy: ComptoirCopy; byline?: string | null }) {
  return (
    <article className="ct-clip rb-clip" data-ct-anchor="start">
      <p className="ct-clip__k" lang="fr">
        {MICRO_FR.page_kicker} · {page.witness.nameFr}
        {page.witness.roleFr ? `, ${page.witness.roleFr}` : ''}
        {page.datelineFr ? ` · ${page.datelineFr}` : ''}
      </p>
      <h2 className="ct-clip__hl" lang="fr">
        {page.titleFr}
      </h2>
      <dl className="rb-qa" lang="fr">
        {page.lines.map((line, index) => (
          <div key={index} className="rb-qa__row">
            <dt className="rb-qa__q">
              <span className="rb-qa__k">{MICRO_FR.q}</span> {line.questionFr}
            </dt>
            <dd className="rb-qa__a">
              <span className="rb-qa__k">{MICRO_FR.a}</span> {line.answerFr}
              {line.sourceName && <span className="rb-qa__src"> · d’après {line.sourceName}</span>}
            </dd>
          </div>
        ))}
      </dl>
      <p className="ct-quote__by" lang="fr">
        {bylineOf(byline, page.bylineFr)}
      </p>
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
  else if (closing?.photoPage) clipping = <PhotoClipping page={closing.photoPage} ccopy={ccopy} copy={copy} tiles={tiles} byline={closing.dispatch?.bylineFr} />;
  else if (closing?.microPage) clipping = <MicroClipping page={closing.microPage} ccopy={ccopy} byline={closing.dispatch?.bylineFr} />;
  else if (closing) clipping = <RvDispatch {...closing.dispatch} readOnly copy={copy} />;
  return (
    <>
      <div className="rv-body ct-body" data-step="page">
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
