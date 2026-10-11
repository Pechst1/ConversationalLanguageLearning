/**
 * The archive's printed marks (WP-96/97), shared by the archive, the reader
 * and the day's recap:
 *
 *   · `MarginNotes` — «Parce que vous avez dit à Marin « vas-y » — Nº 4», a
 *     dated note in the margin; tapping it opens the cause day in the archive;
 *   · `ChapterColophon` — «Fin du chapitre» under the Bauhaus mark, with the
 *     chapter's digest line «question → résolution»;
 *   · `TomeSeal` — a finished season, pressed as «Tome N»;
 *   · `TrustMeter` — five small marks, filled up to the trust, outlined after;
 *     it can fall, so it is a count of marks, never a ring and never a bar;
 *   · `Precedemment` — the chronicle's last lines before a new scene, with
 *     tappable words and one «Lire».
 *
 * Story (a note's sentence, a digest, a chronicle line) is French and marked
 * `lang="fr"`; the chrome comes from `archive-copy.ts` in the chrome language.
 */

import React, { useCallback, useState } from 'react';
import Link from 'next/link';

import { Action, AtelierMark } from '@/components/atelier-v2/ui';
import { Seal } from '@/components/ui/Seal';
import { FrenchLine } from '@/components/feuilleton/reader/TappableFrench';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import { readerCopy } from '@/components/feuilleton/reader/reader-copy';
import { frenchSpacing } from '@/lib/french-typography';
import type { ControlLanguage } from '@/types/daily-journey';

import { archiveCopy, archiveDate, faFill } from './archive-copy';
import {
  digestParts,
  marginNoteEdition,
  marginNoteHref,
  type ArchiveMarginNote,
  type ArchivePayload,
} from './archive-model';
import { trustMarks } from './trombinoscope-model';

/* ------------------------------------------------------------------ notes */

/** The «— Nº 4» (or «— 12 sept.») a note is signed with. */
export function marginNoteReference(note: ArchiveMarginNote, archive?: ArchivePayload | null): string {
  const edition = marginNoteEdition(note, archive);
  if (edition !== null) return `Nº ${edition}`;
  // The note is story, so its date is printed the way the story prints one.
  return archiveDate(note.cause_date, 'fr');
}

export function MarginNotes({
  notes,
  language = null,
  archive = null,
}: {
  notes: ArchiveMarginNote[] | null | undefined;
  language?: ControlLanguage | null;
  /** Lets a note without its own edition number find the cause day's. */
  archive?: ArchivePayload | null;
}) {
  const t = archiveCopy(language);
  if (!notes || !notes.length) return null;
  return (
    <ul className="fa-margins" aria-label={t.margin_aria} data-margin-notes="">
      {notes.map((note, index) => {
        const href = marginNoteHref(note);
        const reference = marginNoteReference(note, archive);
        const body = (
          <>
            <span className="fa-margin__text" lang="fr">
              {frenchSpacing(note.text_fr)}
            </span>
            {reference && <span className="fa-margin__ref" lang="fr">{` — ${reference}`}</span>}
          </>
        );
        const date = archiveDate(note.cause_date, language);
        return (
          <li className="fa-margin" key={`${note.cause_scene_id || note.cause_date || 'n'}-${index}`} data-margin-note="">
            {href ? (
              <Link className="fa-margin__link" href={href} title={date ? faFill(t.margin_open, { date }) : undefined}>
                {body}
              </Link>
            ) : (
              <span className="fa-margin__static">{body}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------------------------------------- colophon */

export function DigestLine({ digest }: { digest: string | null | undefined }) {
  const parts = digestParts(digest);
  if (!parts) return null;
  return (
    <p className="fa-digest" lang="fr" data-digest="">
      {frenchSpacing(parts.question)}
      {parts.resolution && (
        <>
{' '}
          <span className="fa-digest__arrow" aria-hidden="true">→</span>
          <span className="fa-sr"> — </span>{' '}
          {frenchSpacing(parts.resolution)}
        </>
      )}
    </p>
  );
}

export function ChapterColophon({ digest }: { digest?: string | null }) {
  return (
    <figure className="fa-colophon" data-colophon="">
      <AtelierMark size={28} />
      <figcaption>
        <span className="fa-colophon__end" lang="fr">
          Fin du chapitre
        </span>
      </figcaption>
      <hr className="fa-colophon__rule" aria-hidden="true" />
      <DigestLine digest={digest} />
    </figure>
  );
}

/* ------------------------------------------------------------------ tome */

export function TomeSeal({
  number,
  title,
  language = null,
  stamp = false,
}: {
  number: number;
  title?: string | null;
  language?: ControlLanguage | null;
  /** Press it (the recap, the moment the season closes); Reduce Motion removes the press. */
  stamp?: boolean;
}) {
  const t = archiveCopy(language);
  const top = faFill(t.tome_n, { n: number });
  return (
    <Seal
      stamp={stamp}
      variant="quad"
      tone="gilt"
      size="md"
      topLine={top}
      caption={(title || '').trim() || faFill(archiveCopy('fr').season_n, { n: number })}
      label={faFill(t.tome_aria, { n: number })}
    />
  );
}

/* ----------------------------------------------------------------- trust */

export function TrustMeter({ trust, language = null }: { trust: number | null; language?: ControlLanguage | null }) {
  const t = archiveCopy(language);
  const marks = trustMarks(trust);
  if (!marks) {
    return <span className="av2-label" data-trust="none">{t.trust_none}</span>;
  }
  const filled = marks.filter((mark) => mark === 'filled').length;
  return (
    <span className="fa-trust" role="img" aria-label={faFill(t.trust_aria, { n: filled })} data-trust={filled}>
      {marks.map((mark, index) => (
        <i key={index} data-mark={mark} aria-hidden="true" />
      ))}
    </span>
  );
}

/* ---------------------------------------------------------- précédemment */

export function Precedemment({
  lines,
  language = null,
  onRead,
  journeyId = null,
}: {
  lines: string[];
  language?: ControlLanguage | null;
  onRead: () => void;
  journeyId?: string | null;
}) {
  const t = archiveCopy(language);
  const reader = readerCopy(language);
  const [help, setHelp] = useState<WordHelpRequest | null>(null);
  const openHelp = useCallback(
    (sentence: string) => (word: { surface: string; term: string }) =>
      setHelp({ surface: word.surface, term: word.term, sentence, journeyId }),
    [journeyId],
  );
  return (
    <section className="fa-previously" aria-label={t.previously_aria} data-precedemment="">
      <p className="av2-label">{t.previously}</p>
      <ul className="fa-previously__list">
        {lines.map((line, index) => (
          <li key={`${index}-${line}`}>
            <FrenchLine
              text={line}
              idPrefix={`prev-${index}`}
              onWord={openHelp(line)}
              wordLabel={reader.word_help}
            />
          </li>
        ))}
      </ul>
      <Action tone="primary" onClick={onRead}>
        {t.read}
      </Action>
      <WordHelpSheet request={help} onClose={() => setHelp(null)} language={language} />
    </section>
  );
}
