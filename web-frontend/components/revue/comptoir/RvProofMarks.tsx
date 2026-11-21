/**
 * Romy's marks on the learner's draft (2026-10-23), with «Le pourquoi» (2026-11-20): each
 * underlined word is a button that opens its why under the sentence — the rule in the
 * learner's mother tongue, never the corrected form — one at a time; the list under it does
 * the same with a 44 px row. Without a why (the switch off, or a refused why) it renders the
 * marks exactly as before. Shared by the players that show Romy's fix step.
 */

import React, { useEffect, useRef, useState } from 'react';

import { hairlineX } from '../papier/papier-model';

import type { RvComptoirMark, RvComptoirMarkKind, RvLanguage } from '@/lib/revue-types';

import { fill } from '../revue-copy';
import { markSegments } from './comptoir-model';
import { hasWhy, openWhy, toggleWhy, whySegments, type PourquoiCopy } from './pourquoi';

export type RvProofMarksProps = {
  draftFr: string;
  marks: RvComptoirMark[];
  kindLabels: Record<RvComptoirMarkKind, string>;
  copy: PourquoiCopy;
  /** The language the whys are written in (the learner's mother tongue). */
  whyLanguage: RvLanguage | string;
  /** The why open at first (tests; a resumed screen opens none). */
  initialOpen?: number | null;
  /** Ids stay unique when two players share a page. */
  idPrefix?: string;
};

export function RvProofMarks({ draftFr, marks, kindLabels, copy, whyLanguage, initialOpen = null, idPrefix = 'ct' }: RvProofMarksProps) {
  const [open, setOpen] = useState<number | null>(initialOpen);
  const proofRef = useRef<HTMLParagraphElement | null>(null);
  const noteRef = useRef<HTMLParagraphElement | null>(null);
  // «La belle édition»: the open why is Romy's margin note, its hairline rising to the word it is about.
  useEffect(() => {
    const note = noteRef.current;
    const proof = proofRef.current;
    if (!note || !proof || open === null) return;
    const word = proof.querySelector<HTMLElement>('[aria-expanded="true"]');
    if (!word) return;
    const n = note.getBoundingClientRect();
    const w = word.getBoundingClientRect();
    note.style.setProperty('--pp-x', `${hairlineX(w.left - n.left, w.width, n.width)}px`);
    note.style.setProperty('--pp-rise', `${Math.max(4, Math.round(n.top - w.bottom - 4))}px`);
  }, [open]);

  if (!hasWhy(marks)) {
    return (
      <>
        <p className="ct-paper__fr" lang="fr">
          {markSegments(draftFr, marks).map((segment, index) =>
            segment.kind ? (
              <mark key={index} className="ct-mark" data-kind={segment.kind}>
                {segment.text}
              </mark>
            ) : (
              <React.Fragment key={index}>{segment.text}</React.Fragment>
            ),
          )}
        </p>
        <ul className="ct-marks">
          {marks.map((mark, index) => (
            <li key={index} className="ct-why">
              <b lang="fr">{mark.spanFr}</b> · {kindLabels[mark.kind]}
            </li>
          ))}
        </ul>
      </>
    );
  }

  const panelId = `${idPrefix}-why`;
  const shown = openWhy(marks, open);
  const tap = (index: number) => setOpen((current) => toggleWhy(current, index));
  return (
    <>
      <p className="ct-paper__fr" lang="fr" ref={proofRef}>
        {whySegments(draftFr, marks).map((segment, index) => {
          if (segment.kind === null || segment.index === null) return <React.Fragment key={index}>{segment.text}</React.Fragment>;
          const mark = marks[segment.index];
          if (!mark?.why) {
            return (
              <mark key={index} className="ct-mark" data-kind={segment.kind}>
                {segment.text}
              </mark>
            );
          }
          const at = segment.index;
          return (
            <button
              key={index}
              type="button"
              className="ct-mark ct-mark--why"
              data-kind={segment.kind}
              aria-expanded={open === at}
              aria-controls={panelId}
              aria-label={fill(copy.why_open, { span: mark.spanFr })}
              onClick={() => tap(at)}
            >
              {segment.text}
            </button>
          );
        })}
      </p>
      {shown && (
        <p id={panelId} className="ct-why-open" data-kind={shown.mark.kind} aria-live="polite" ref={noteRef}>
          <span className="ct-why-open__k">
            <b lang="fr">{shown.mark.spanFr}</b> · {kindLabels[shown.mark.kind]}
          </span>
          <span className="ct-why-open__t" lang={whyLanguage}>
            {shown.mark.why}
          </span>
        </p>
      )}
      <ul className="ct-marks">
        {marks.map((mark, index) =>
          mark.why ? (
            <li key={index} className="ct-why">
              <button type="button" className="ct-why__b" aria-expanded={open === index} aria-controls={panelId} onClick={() => tap(index)}>
                <b lang="fr">{mark.spanFr}</b> · {kindLabels[mark.kind]}
              </button>
            </li>
          ) : (
            <li key={index} className="ct-why">
              <b lang="fr">{mark.spanFr}</b> · {kindLabels[mark.kind]}
            </li>
          ),
        )}
      </ul>
    </>
  );
}

export default RvProofMarks;
