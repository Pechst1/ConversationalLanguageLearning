/**
 * «Papier · la belle édition» (2026-11-21) · the newsroom's own paper objects, drawn with the
 * app's existing means (styles/revue-papier.css: `.av2` scope, `--av2-*` tokens only, the serif
 * italic and the sans, ruled lines and print conventions — no new colour, font or ornament).
 *
 * Shared by the four assignments and open to the ones being built («La photo», «Le micro»):
 *
 *   PpDateline     «PARIS · VENDREDI 21 NOVEMBRE · Nº 47», in small caps between hairlines
 *   PpOpening      the masthead at display size, its rule and the dateline (a screen that opens the paper)
 *   PpSection      the assignment as a section head («LE FIL — Remettre en ordre»)
 *   PpFolio        the screen as a page number, «2 / 5», in the serif's old-style figures
 *   PpInkDefs      the one SVG filter that makes a stamp's ink uneven (alpha only: both themes)
 *   PpStamp        «VRAI» in green ink, «INTOX» in red, tilted by its seed, landed with a thud
 *   PpPencilLoop   the grease-pencil loop drawn round a chosen headline (~300 ms)
 *   PpStrike       a proofreader's strike through a refused proof
 *   PpDeleatur     the delete mark (a strike ending in the deleatur's loop) over a word
 *   PpCutting      a pasted press cutting, its outlet as the footer
 *   PpFigure       a press photograph: hairline frame, italic caption, credit in small caps under a rule
 *   PpFrontPage    «La page»: masthead, dateline, kicker, headline, lead with a drop cap, the picture,
 *                  the learner's piece signed in red small caps (stamped last), the Lexique sidebar
 *
 * The wire's strip, the proof and the slip are CSS on the players' own elements (`.fl-strip`,
 * `.rb-head`, `.rb-card`, `.ct-paper`), so the markup the players' tests read stays as it was.
 */

import React, { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react';

import { resolveMediaUrl } from '@/lib/media-url';

import { knownTranslation, translateOnce } from '../revue-translate';
import { PAPIER_FR, papierCopy } from './papier-copy';
import { datelineParts, dropCap, editionOf, pencilLoop, stampTilt, standfirstFor, tilt } from './papier-model';

const useIsoLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

// ---------------------------------------------------------------------------
// The edition
// ---------------------------------------------------------------------------

/** What every page of today's paper is printed with. */
export type PpEdition = {
  /** The session's day (`closedAt` once filed, else `startedAt`). */
  dateIso?: string | null;
  /** The session's ISO week: the edition's number. */
  weekIso?: string | null;
};

export function PpDateline({ edition, className = '' }: { edition: PpEdition; className?: string }) {
  const parts = datelineParts(edition);
  return (
    <p className={`pp-dateline ${className}`.trim()} lang="fr">
      {parts.map((part, index) => (
        <React.Fragment key={part}>
          {index > 0 && (
            <span className="pp-dateline__dot" aria-hidden="true">
              {' · '}
            </span>
          )}
          <span>{part}</span>
        </React.Fragment>
      ))}
    </p>
  );
}

/** The masthead at display size, its rule and the dateline: the first screen opens the paper. */
export function PpOpening({ edition, section, step, tools = null }: { edition: PpEdition; section: string; step?: string | null; tools?: React.ReactNode }) {
  const mastRef = useRef<HTMLParagraphElement | null>(null);
  // Once the masthead at display size has scrolled under the head, the head prints its own.
  useEffect(() => {
    const mast = mastRef.current;
    if (!mast || typeof IntersectionObserver === 'undefined') return undefined;
    const head = mast.closest('.av2')?.querySelector<HTMLElement>('.pp-head');
    if (!head) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) head.dataset.opening = '';
        else delete head.dataset.opening;
      },
      { rootMargin: '-72px 0px 0px 0px' },
    );
    observer.observe(mast);
    return () => {
      observer.disconnect();
      delete head.dataset.opening;
    };
  }, []);
  return (
    <header className="pp-opening">
      <p className="pp-opening__mast" lang="fr" ref={mastRef}>
        {PAPIER_FR.masthead}
      </p>
      <PpDateline edition={edition} className="pp-opening__date" />
      <PpSectionLine section={section} step={step} tools={tools} />
    </header>
  );
}

function PpSectionLine({ section, step, tools = null }: { section: string; step?: string | null; tools?: React.ReactNode }) {
  return (
    <div className="pp-section__row">
      <p className="pp-section__line" lang="fr">
        <span className="pp-section__name">{section}</span>
        {step && <span className="pp-section__step">{step}</span>}
      </p>
      {tools}
    </div>
  );
}

/** The assignment as a section head; on its opening screen, the masthead and dateline above it. */
export function PpSection({
  edition,
  section,
  step,
  opening = false,
  tools = null,
}: {
  edition: PpEdition;
  section: string;
  step?: string | null;
  opening?: boolean;
  /** The screen's one quiet tool (the set's «Tout traduire»), at the right of the section head. */
  tools?: React.ReactNode;
}) {
  if (opening) return <PpOpening edition={edition} section={section} step={step} tools={tools} />;
  return (
    <header className="pp-section">
      <PpSectionLine section={section} step={step} tools={tools} />
    </header>
  );
}

// ---------------------------------------------------------------------------
// One quiet translation for a set
// ---------------------------------------------------------------------------

type TranslateSet = { all: boolean; toggle: () => void };
const TranslateSetContext = createContext<TranslateSet | null>(null);

/**
 * A screen whose items are a set (the wire's strips, the three proofs, the statements): one
 * «Tout traduire» in its section head shows every item's translation at once, instead of a
 * button on each. Wrap the section head and the screen; `key` it by the screen shown.
 */
export function PpTranslateSet({ children }: { children: React.ReactNode }) {
  const [all, setAll] = useState(false);
  return <TranslateSetContext.Provider value={{ all, toggle: () => setAll((value) => !value) }}>{children}</TranslateSetContext.Provider>;
}

/** The set's one toggle: a quiet text control (44 px tall), in the chrome language. */
export function PpTranslateToggle({ language }: { language: string }) {
  const set = useContext(TranslateSetContext);
  if (!set) return null;
  const copy = papierCopy(language);
  return (
    <button type="button" className="pp-link pp-translate-all" aria-pressed={set.all} onClick={set.toggle}>
      {set.all ? copy.translate_all_hide : copy.translate_all}
    </button>
  );
}

/** An item of a set: its translation, shown while the set's toggle is on (fetched once if the payload has none). */
export function PpItemTranslation({ textFr, translation = null, language }: { textFr: string; translation?: string | null; language: string }) {
  const set = useContext(TranslateSetContext);
  const on = Boolean(set?.all);
  const supplied = (translation || '').trim() || knownTranslation(textFr, language);
  const [fetched, setFetched] = useState('');
  useEffect(() => {
    if (!on || supplied || fetched || !textFr.trim()) return undefined;
    let alive = true;
    translateOnce(textFr, language)
      .then((text) => alive && setFetched(text))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [on, supplied, fetched, textFr, language]);
  const text = supplied || fetched;
  if (!on || !text) return null;
  return (
    <p className="rv-translation pp-tr" lang={language}>
      {text}
    </p>
  );
}

/** The screen as a page number: «2 / 5». Decorative: the head's progress bar says it in words. */
export function PpFolio({ n, total }: { n: number; total: number }) {
  return (
    <span className="pp-folio" aria-hidden="true">
      <span className="pp-folio__n">{n}</span>
      <span className="pp-folio__of">/</span>
      <span className="pp-folio__t">{total}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Ink
// ---------------------------------------------------------------------------

/**
 * The stamp's ink: a little turbulence displaces the letters' edges and knocks a few specks out
 * of the solid (alpha only, so the token colours — and both themes — come through untouched).
 */
export function PpInkDefs() {
  return (
    <svg className="pp-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <filter id="pp-ink" x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="noise" />
        <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.6" xChannelSelector="R" yChannelSelector="G" result="rough" />
        <feComponentTransfer in="noise" result="specks">
          <feFuncA type="discrete" tableValues="1 1 1 1 1 1 0.35 1 1 1" />
        </feComponentTransfer>
        <feComposite in="rough" in2="specks" operator="in" />
      </filter>
    </svg>
  );
}

export type PpStampProps = {
  kind: 'vrai' | 'intox';
  /** What the stamp lands on (the statement's key): its tilt. */
  seed: string;
  /** Screen readers hear this instead of the printed word. */
  label: string;
  /** A filed page shows it at rest: no thud. */
  still?: boolean;
  size?: 'md' | 'sm';
};

export function PpStamp({ kind, seed, label, still = false, size = 'md' }: PpStampProps) {
  const style = { '--pp-tilt': `${stampTilt(seed)}deg` } as React.CSSProperties;
  return (
    <span className="pp-stamp" data-ink={kind} data-still={still ? '' : undefined} data-size={size} style={style} role="img" aria-label={label}>
      <span className="pp-stamp__ink" lang="fr" aria-hidden="true">
        {kind === 'vrai' ? PAPIER_FR.stamp_vrai : PAPIER_FR.stamp_intox}
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Proofreader's marks
// ---------------------------------------------------------------------------

/** The grease-pencil loop round a chosen headline, drawn in ~300 ms (at rest under reduced motion). */
export function PpPencilLoop({ seed, label, still = false }: { seed: string; label?: string; still?: boolean }) {
  return (
    <svg
      className="pp-loop"
      data-still={still ? '' : undefined}
      viewBox="0 0 100 40"
      preserveAspectRatio="none"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <path d={pencilLoop(seed)} pathLength={1} />
    </svg>
  );
}

/** A refused proof: one rising stroke through it, as a proofreader strikes a galley. */
export function PpStrike({ label }: { label?: string }) {
  return (
    <svg
      className="pp-strike"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <path d="M1 98 L99 2" pathLength={1} />
    </svg>
  );
}

/** The delete mark over a word: the strike, then the deleatur's loop at its end. */
export function PpDeleatur() {
  return (
    <svg className="pp-del" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <path d="M0 13 C 30 11, 70 12, 86 12 C 96 12, 99 4, 93 3 C 86 2, 86 13, 94 16 C 97 17, 99 20, 97 23" pathLength={1} />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Cuttings and pictures
// ---------------------------------------------------------------------------

/** A pasted press cutting: its text, then a rule and the outlet's name as the footer. */
export function PpCutting({ seed, source, children, className = '' }: { seed: string; source?: string | null; children: React.ReactNode; className?: string }) {
  const style = { '--pp-tilt': `${tilt(seed, 0.8)}deg` } as React.CSSProperties;
  return (
    <figure className={`pp-cutting ${className}`.trim()} style={style}>
      {children}
      {source && (
        <figcaption className="pp-cutting__src" lang="fr">
          {source}
        </figcaption>
      )}
    </figure>
  );
}

export type PpPicture = { url: string; captionFr?: string | null; creditFr: string };

/**
 * A press photograph: the frame (never cropping its credit), the italic caption, the credit under a rule.
 * `legend` replaces the paper's caption with the learner's own (La photo's page); `links` print
 * after the credit (a photograph's licence and source).
 */
export function PpFigure({
  picture,
  ratio = 'wide',
  legend = null,
  links = null,
  alt = '',
}: {
  picture: PpPicture;
  ratio?: 'wide' | 'page' | 'natural';
  legend?: React.ReactNode;
  links?: React.ReactNode;
  alt?: string;
}) {
  const [failed, setFailed] = React.useState(false);
  const src = resolveMediaUrl(picture.url) ?? picture.url;
  const caption = (picture.captionFr ?? '').trim();
  return (
    <figure className="pp-figure" data-ratio={ratio}>
      <div className="pp-figure__frame">
        {!failed && (
          // eslint-disable-next-line @next/next/no-img-element -- a painted print or a Commons thumbnail, already sized
          <img className="pp-figure__img" src={src} alt={alt} decoding="async" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
        )}
      </div>
      <figcaption className="pp-figure__cap" lang="fr">
        {legend ?? (caption && <span className="pp-figure__fr">{caption}</span>)}
        <span className="pp-figure__credit">
          {picture.creditFr}
          {links}
        </span>
      </figcaption>
    </figure>
  );
}

/** A photograph's licence and source after its credit, «· CC BY-SA 4.0 · Source» (each a 44 px tap). */
export function PpLinks({ links, newTab }: { links: Array<{ kind: string; href: string; label: string }>; newTab: string }) {
  if (!links.length) return null;
  return (
    <>
      {links.map((link) => (
        <React.Fragment key={link.kind}>
          <span aria-hidden="true">{' · '}</span>
          <a className="pp-figure__link" href={link.href} target="_blank" rel="noopener noreferrer" data-link={link.kind}>
            {link.label}
            <span className="av2-sr"> ({newTab})</span>
          </a>
        </React.Fragment>
      ))}
    </>
  );
}

/** One frame of a contact sheet: the picture, its credit (and licence links), never without them. */
export type PpFrame = { key: string; url: string; creditFr: string; links?: React.ReactNode };

/**
 * «La photo»: the contact sheet — the story's pictures as frames on one sheet, their numbers
 * in the margin, the credits listed under the sheet by number. A frame is the choice itself (a
 * radio, 44 px and more); the one picked is circled with the grease pencil (as «Le titre»'s
 * proofs), a refused one struck through. Nothing is marked before the learner picks.
 */
export function PpSheet({
  frames,
  seed,
  label,
  frameLabel,
  chosen,
  tried = [],
  right = null,
  disabled,
  onPick,
  still = false,
  pickLabel,
  refusedLabel,
}: {
  frames: PpFrame[];
  seed: string;
  label: string;
  frameLabel: (n: number) => string;
  chosen: string | null;
  tried?: string[];
  right?: string | null;
  disabled: (key: string) => boolean;
  onPick: (key: string) => void;
  still?: boolean;
  pickLabel?: string;
  refusedLabel?: string;
}) {
  return (
    <section className="pp-sheet" aria-label={label} data-frames={frames.length}>
      <ul className="rb-planche pp-sheet__frames" role="radiogroup" aria-label={label}>
        {frames.map((frame, index) => {
          const isRight = right === frame.key;
          const isTried = tried.includes(frame.key) && !isRight;
          const isChosen = chosen === frame.key;
          const src = resolveMediaUrl(frame.url) ?? frame.url;
          return (
            <li key={frame.key} className="rb-planche__item pp-frame" data-tried={isTried ? '' : undefined} data-right={isRight ? '' : undefined} data-chosen={isChosen ? '' : undefined}>
              <button
                type="button"
                role="radio"
                className="rb-planche__pick pp-frame__pick"
                aria-checked={isChosen || isRight}
                aria-label={frameLabel(index + 1)}
                disabled={disabled(frame.key)}
                onClick={() => onPick(frame.key)}
              >
                <span className="pp-frame__img">
                  {/* eslint-disable-next-line @next/next/no-img-element -- a painted print or a Commons thumbnail, already sized */}
                  <img src={src} alt="" decoding="async" referrerPolicy="no-referrer" />
                </span>
                {(isRight || (isChosen && !isTried)) && <PpPencilLoop seed={`${seed}:${frame.key}`} label={pickLabel} still={still || isRight} />}
                {isTried && <PpStrike label={refusedLabel} />}
              </button>
              <span className="pp-frame__n" aria-hidden="true">
                {index + 1}
              </span>
            </li>
          );
        })}
      </ul>
      <ol className="pp-sheet__credits" lang="fr">
        {frames.map((frame, index) => (
          <li key={frame.key}>
            <span className="pp-sheet__cn" aria-hidden="true">
              {index + 1}
            </span>
            <span className="rv-picture__credit pp-sheet__credit">{frame.creditFr}</span>
            {frame.links}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** A blank to fill, set as a rule (a gap in a cutting, a hole in Romy's notes). */
export function PpBlank({ label = '…', wide = false }: { label?: string; wide?: boolean }) {
  return <span className="pp-blank" data-wide={wide ? '' : undefined} role="img" aria-label={label} />;
}

/** The proofreader's «stet» (let it stand) beside a line the learner suspected but which is right. */
export function PpStet({ label }: { label: string }) {
  return (
    <span className="pp-stet" role="img" aria-label={label}>
      <span aria-hidden="true">stet</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// «La page»
// ---------------------------------------------------------------------------

/** A lead set with a drop cap (its first letter over two lines); plain when it opens on no letter. */
export function PpLead({ text, className = 'pp-front__lead' }: { text: string; className?: string }) {
  const cap = dropCap(text);
  if (!cap) {
    return (
      <p className={className} lang="fr">
        {text}
      </p>
    );
  }
  return (
    <p className={className} lang="fr" data-cap="">
      <span className="pp-cap" aria-hidden="true">
        {cap.cap}
      </span>
      <span className="av2-sr">{cap.cap}</span>
      {cap.rest}
    </p>
  );
}

/** The learner's byline in red small caps, stamped last as the page settles. */
export function PpByline({ text, still = false }: { text: string; still?: boolean }) {
  return (
    <span className="pp-byline" lang="fr" data-still={still ? '' : undefined}>
      {text}
    </span>
  );
}

/** The kept words, boxed as the page's «Lexique» sidebar. */
export function PpLexique({ words, label }: { words: string[]; label: string }) {
  if (!words.length) return null;
  return (
    <aside className="pp-lexique" aria-label={label}>
      <p className="pp-lexique__k" lang="fr" aria-hidden="true">
        {PAPIER_FR.lexique}
      </p>
      <ul className="pp-lexique__list ct-words">
        {words.map((word) => (
          <li key={word} lang="fr">
            {word}
          </li>
        ))}
      </ul>
    </aside>
  );
}

export type PpFrontPageProps = {
  edition?: PpEdition | null;
  /** The section the page was made in («Le fil de Romy»). */
  kicker: string;
  headline: React.ReactNode;
  /** The scene line, set as the deck under the headline (when no picture carries it as a caption). */
  deck?: string | null;
  /** The article: the lead, the picture, the learner's piece, the columns — in the page's own order. */
  children?: React.ReactNode;
  /** A filed page opened again: no movement. */
  still?: boolean;
  className?: string;
  /** What leads the page above its kicker and headline (La photo: the picture). */
  top?: React.ReactNode;
};

/**
 * The closing screen's front page: the masthead, the dateline between its rules, the section's
 * kicker and the headline at display size, then the article. It arrives with one movement (it
 * slides up and settles; the byline is stamped last); under reduced motion it is simply there.
 */
export function PpFrontPage({ edition, kicker, headline, deck = null, children, still = false, className = '', top = null }: PpFrontPageProps) {
  return (
    <article className={`ct-clip ${className}`.trim()} data-pp-front="" data-still={still ? '' : undefined}>
      <header className="pp-front__mast">
        <p className="pp-front__title" lang="fr">
          {PAPIER_FR.masthead}
        </p>
        {edition && <PpDateline edition={edition} className="pp-front__date" />}
      </header>
      {top}
      <p className="ct-clip__k pp-front__kicker" lang="fr">
        {kicker}
      </p>
      <h2 className="ct-clip__hl pp-front__hl" lang="fr">
        {headline}
      </h2>
      {/* Never a deck that repeats the headline's own words. */}
      {(typeof headline === 'string' ? standfirstFor(headline, deck) : deck) && (
        <p className="pp-front__deck" lang="fr">
          {deck}
        </p>
      )}
      {children}
    </article>
  );
}

/** The page's foot: a column of the article beside the boxed Lexique, a column rule between them. */
export function PpFrontCols({ children, words = [], wordsLabel }: { children?: React.ReactNode; words?: string[]; wordsLabel: string }) {
  if (!children && !words.length) return null;
  return (
    <div className="pp-front__cols" data-lexique={words.length && children ? '' : undefined}>
      {children && <div className="pp-front__main">{children}</div>}
      <PpLexique words={words} label={wordsLabel} />
    </div>
  );
}

/** The learner's own piece as the page's key element, signed (the byline stamped last). */
export function PpMine({ textFr, byline, still = false, quoted = true, lead = false }: { textFr: string; byline: string; still?: boolean; quoted?: boolean; lead?: boolean }) {
  return (
    <div className="pp-front__mine" data-lead={lead ? '' : undefined}>
      {lead ? (
        <PpLead text={textFr} className="pp-front__mine-fr" />
      ) : (
        <p className="pp-front__mine-fr" lang="fr" data-plain={quoted ? undefined : ''}>
          {textFr}
        </p>
      )}
      <PpByline text={byline} still={still} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Motion
// ---------------------------------------------------------------------------

function reducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * The wire's strips slide to their new places (FLIP, 200 ms, eased): each child of `ref` with a
 * `data-key` starts from where it was and moves to where it now is; its neighbours make room the
 * same way. `order` is the keys in their current order. Nothing moves under reduced motion.
 */
export function useFlip(ref: React.RefObject<HTMLElement | null>, order: string) {
  const last = useRef<Record<string, number>>({});
  useIsoLayoutEffect(() => {
    const root = ref.current;
    if (!root) return;
    const rows = Array.from(root.querySelectorAll<HTMLElement>(':scope > [data-key]'));
    const now: Record<string, number> = {};
    for (const row of rows) now[row.dataset.key as string] = row.offsetTop;
    const before = last.current;
    last.current = now;
    if (reducedMotion()) return;
    for (const row of rows) {
      const key = row.dataset.key as string;
      if (!(key in before)) continue;
      const delta = before[key] - now[key];
      if (Math.abs(delta) < 1) continue;
      row.style.transition = 'none';
      row.style.transform = `translateY(${delta}px)`;
      row.dataset.moving = '';
      // Next frame: let it slide home.
      requestAnimationFrame(() => {
        row.style.transition = 'transform 200ms cubic-bezier(0.2, 0.7, 0.2, 1)';
        row.style.transform = '';
        const done = () => {
          row.style.transition = '';
          delete row.dataset.moving;
          row.removeEventListener('transitionend', done);
        };
        row.addEventListener('transitionend', done);
        window.setTimeout(done, 260);
      });
    }
  }, [order]);
}

// ---------------------------------------------------------------------------
// A player's section head
// ---------------------------------------------------------------------------

/**
 * Under the head of every assignment: the section it is played in («LE FIL — Remettre en
 * ordre»); on its first screen the masthead at display size and the dateline above it. «La page»
 * prints its own masthead: no section head there. Then the ink filter the stamps use.
 */
export function PpPlayerSection({
  session,
  section,
  step,
  shown,
  set = false,
  language,
}: {
  session: { startedAt?: string | null; closedAt?: string | null; week?: { iso: string } | null };
  section: string;
  step: string | null;
  shown: string;
  /** The screen's items are a set: its section head carries the one «Tout traduire». */
  set?: boolean;
  /** The chrome language (the toggle's words). */
  language?: string;
}) {
  const edition = editionOf(session);
  return (
    <>
      <PpInkDefs />
      {shown !== 'page' && (
        <PpSection edition={edition} section={section} step={step} opening={shown === 'read'} tools={set ? <PpTranslateToggle language={language ?? 'en'} /> : null} />
      )}
    </>
  );
}

/** The head with only its × (the chooser, the loading state): the masthead is printed below it. */
export function PpBareHead({ children }: { children: React.ReactNode }) {
  return (
    <div className="rv-head pp-head" data-bare="" data-opening="">
      {children}
      <p className="pp-head__mast" lang="fr" aria-hidden="true">
        {PAPIER_FR.masthead}
      </p>
    </div>
  );
}
