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

import type { ComptoirCopy } from '../comptoir/comptoir-copy';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { fill } from '../revue-copy';
import { RvCloseVignette, RvDispatch } from '../RvClose';
import { papierCopy } from '../papier/papier-copy';
import { bylineFr, editionOf, legendeBylineFr, pagePicture, proofNoteFr } from '../papier/papier-model';
import { PpByline, PpFigure, PpFrontCols, PpFrontPage, PpLead, PpStamp, type PpEdition, type PpPicture } from '../papier/PapierPrint';
import { PICTURE_CREDIT_FR } from '../RvPicture';
import { pictureLinks } from '../revue-gallery';
import type { RevueCopy } from '../revue-copy';
import { MICRO_FR, PHOTO_FR } from './photo-micro-copy';
import { asRvPicture } from './photo-micro-model';
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

/**
 * «La photo» · La page: the picture leads the front page, printed large in its press frame;
 * under it the learner's caption, set as the paper's legend and signed «Légende · par toi»
 * (how it reached print), the credit and licence always with the picture; Romy's sources, the
 * Lexique.
 */
export function PhotoClipping({
  page,
  ccopy,
  copy,
  tiles = false,
  byline,
  edition = null,
  still = false,
}: { page: RvPhotoPage; ccopy: ComptoirCopy; copy: RevueCopy; tiles?: boolean; byline?: string | null } & PageExtras) {
  const links = pictureLinks(asRvPicture(page.picture), copy);
  return (
    <PpFrontPage
      className="rb-clip pp-photo-page"
      edition={edition}
      kicker={PHOTO_FR.page_kicker}
      headline={page.titleFr}
      still={still}
      top={
        <PpFigure
          picture={{ url: page.picture.url, creditFr: page.picture.creditFr }}
          ratio="page"
          legend={
            <span className="pp-legend">
              <span className="pp-legend__fr">{page.captionFr}</span>
              <PpByline text={legendeBylineFr(page.proof, tiles)} still={still} />
            </span>
          }
          links={<PictureLinks links={links} newTab={copy.new_tab} />}
        />
      }
    >
      {page.datelineFr && (
        <p className="pp-front__deck" lang="fr">
          {page.datelineFr}
        </p>
      )}
      <Sources text={bylineOf(byline, PHOTO_FR.byline)} />
      <PpFrontCols words={page.words} wordsLabel={ccopy.page_words} />
    </PpFrontPage>
  );
}

/** A photograph's licence and source, after its credit (each a 44 px tap). */
function PictureLinks({ links, newTab }: { links: Array<{ kind: string; href: string; label: string }>; newTab: string }) {
  if (!links.length) return null;
  return (
    <>
      {links.map((link) => (
        <React.Fragment key={link.kind}>
          {' · '}
          <a className="pp-figure__link" href={link.href} target="_blank" rel="noopener noreferrer" data-link={link.kind}>
            {link.label}
            <span className="av2-sr"> ({newTab})</span>
          </a>
        </React.Fragment>
      ))}
    </>
  );
}

/**
 * «Le micro» · La page: the interview printed as a Q&A under the headline — the learner's
 * questions set bold, the witness's answers as the text — one answer lifted as the pull quote,
 * «Propos recueillis par …» stamped last, each answer's source in the sources list.
 */
export function MicroClipping({
  page,
  ccopy,
  byline,
  edition = null,
  still = false,
}: { page: RvMicroPage; ccopy: ComptoirCopy; byline?: string | null } & PageExtras) {
  const witness = [page.witness.nameFr, page.witness.roleFr].filter(Boolean).join(', ');
  const pull = pullQuoteOf(page.lines);
  const rows = page.lines.map((line, index) => (
    <div key={index} className="rb-qa__row">
      <dt className="rb-qa__q">
        <span className="rb-qa__k">{MICRO_FR.q}</span> {line.questionFr}
      </dt>
      <dd className="rb-qa__a">
        <span className="rb-qa__k">{MICRO_FR.a}</span> {line.answerFr}
      </dd>
    </div>
  ));
  // The pull quote after the first exchange (before the Q&A when there is only one).
  const at = rows.length > 1 ? 1 : 0;
  const quote = pull ? (
    <div key="pull" className="pp-pull" role="presentation">
      <p className="pp-pull__fr" lang="fr">
        {pull}
      </p>
      <p className="pp-pull__by" lang="fr">
        {page.witness.nameFr}
      </p>
    </div>
  ) : null;
  return (
    <PpFrontPage className="rb-clip pp-micro-page" edition={edition} kicker={`${MICRO_FR.page_kicker} · ${page.witness.nameFr}`} headline={page.titleFr} deck={witness || null} still={still}>
      {page.datelineFr && (
        <p className="pp-front__scene" lang="fr">
          {page.datelineFr}
        </p>
      )}
      <dl className="rb-qa pp-qa" lang="fr">
        {rows.slice(0, at)}
        {quote}
        {rows.slice(at)}
      </dl>
      <PpByline text={[page.bylineFr, proofNoteFr(page.proof)].filter(Boolean).join(' · ')} still={still} />
      <Sources text={sourcesOf(byline, page.lines)} />
      <PpFrontCols words={page.words} wordsLabel={ccopy.page_words} />
    </PpFrontPage>
  );
}

/** The pull quote: the witness's longest answer of the interview (null with none). */
export function pullQuoteOf(lines: Array<{ answerFr: string }>): string | null {
  let best = '';
  for (const line of lines) if (line.answerFr.trim().length > best.length) best = line.answerFr.trim();
  return best || null;
}

/** The dispatch's credit and sources, then any answer's source it does not already name. */
function sourcesOf(byline: string | null | undefined, lines: Array<{ sourceName: string }>): string {
  const head = bylineOf(byline, '');
  const missing = Array.from(new Set(lines.map((line) => line.sourceName).filter((name) => name && !head.includes(name))));
  return [head, ...missing.map((name) => `d’après ${name}`)].filter(Boolean).join(' · ');
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
  else if (closing?.photoPage)
    clipping = <PhotoClipping page={closing.photoPage} ccopy={ccopy} copy={copy} tiles={tiles} byline={closing.dispatch?.bylineFr} edition={edition} still={ended} language={props.chrome} />;
  else if (closing?.microPage) clipping = <MicroClipping page={closing.microPage} ccopy={ccopy} byline={closing.dispatch?.bylineFr} edition={edition} still={ended} language={props.chrome} />;
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
