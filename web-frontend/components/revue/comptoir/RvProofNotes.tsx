/**
 * «Le pourquoi» once the opinion is settled (owner 2026-11-20): under what was printed, each
 * slip with its rule in full (the learner's mother tongue; it may show the corrected form
 * now), «Dans l'article : …» when today's story carries the same pattern, and one quiet line
 * when the slip has a rule La Forge brings back (no button: nothing leaves the session).
 * Renders nothing without notes (the switch off is today's screen).
 */

import React from 'react';

import type { RvComptoirMarkKind, RvComptoirNote, RvLanguage } from '@/lib/revue-types';

import { settledNotes, type PourquoiCopy } from './pourquoi';

export type RvProofNotesProps = {
  notes: RvComptoirNote[] | undefined;
  kindLabels: Record<RvComptoirMarkKind, string>;
  copy: PourquoiCopy;
  /** The language the whys are written in (the learner's mother tongue). */
  whyLanguage: RvLanguage | string;
};

export function RvProofNotes({ notes, kindLabels, copy, whyLanguage }: RvProofNotesProps) {
  const { rows, forge } = settledNotes(notes);
  if (!rows.length && !forge) return null;
  return (
    <div className="ct-notes" aria-label={copy.notes_label} role="group">
      {rows.length > 0 && (
        <ul className="ct-marks">
          {rows.map((note, index) => (
            <li key={index} className="ct-note" data-kind={note.kind}>
              <span className="ct-why">
                <b lang="fr">{note.spanFr}</b> · {kindLabels[note.kind]}
              </span>
              {note.why && (
                <span className="ct-note__why" lang={whyLanguage}>
                  {note.why}
                </span>
              )}
              {note.exampleFr && (
                <span className="ct-note__ex">
                  {copy.in_article}{' '}
                  <q lang="fr">{note.exampleFr}</q>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {forge && <p className="ct-note__forge">{copy.forge_line}</p>}
    </div>
  );
}

export default RvProofNotes;
