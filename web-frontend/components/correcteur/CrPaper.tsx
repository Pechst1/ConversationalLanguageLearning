/**
 * WP-122 B · the draft on paper (the RvDispatch look: double rule, kicker, Garamond
 * headline, body, byline with Romy's face). In the draft each word is a control: a tap
 * selects it, a drag across words selects the span (the screen owns the pointer
 * logic; the units carry `data-s` / `data-u` for it). Marked words are underlined
 * in red with a «marque» word for screen readers; the selection is outlined.
 */

import React from 'react';

import { CastPortrait } from '@/components/atelier-v2/ui';
import type { CrMark, CrSpan, CrUnit } from '@/lib/correcteur-types';

import { overlaps, type CrSelection } from './correcteur-model';

export type CrPaperProps = {
  kickerFr: string;
  titleFr: string;
  bylineFr: string;
  children: React.ReactNode;
};

export function CrPaper({ kickerFr, titleFr, bylineFr, children }: CrPaperProps) {
  return (
    <article className="rv-dispatch cr-paper" lang="fr" data-correcteur-paper="">
      <div className="rv-dispatch__rule" aria-hidden="true" />
      <p className="rv-kicker">{kickerFr}</p>
      <h2 className="rv-dispatch__hl">{titleFr}</h2>
      <div className="rv-dispatch__body cr-body">{children}</div>
      <p className="rv-dispatch__by">
        <CastPortrait characterId="romy_tremblay" name="Romy" size="xs" ring />
        <span>{bylineFr}</span>
      </p>
    </article>
  );
}

export type CrDraftTextProps = {
  sentences: string[];
  units: CrUnit[];
  marks: CrMark[];
  selection: CrSelection | null;
  /** A pending drag's span, drawn like a selection while the finger moves. */
  dragSpan?: { sentenceIndex: number; span: CrSpan } | null;
  onUnit: (sentenceIndex: number, unitIndex: number, extend: boolean) => void;
  markedLabel: string;
  disabled?: boolean;
};

export function CrDraftText({ sentences, units, marks, selection, dragSpan = null, onUnit, markedLabel, disabled = false }: CrDraftTextProps) {
  return (
    <>
      {sentences.map((sentence, sentenceIndex) => {
        const own = units.filter((u) => u.sentenceIndex === sentenceIndex).sort((a, b) => a.span[0] - b.span[0]);
        const parts: React.ReactNode[] = [];
        let cursor = 0;
        own.forEach((unit, unitIndex) => {
          if (unit.span[0] > cursor) parts.push(sentence.slice(cursor, unit.span[0]));
          const marked = marks.some((m) => m.sentenceIndex === sentenceIndex && overlaps(m.span, unit.span));
          const selected =
            (selection && selection.sentenceIndex === sentenceIndex && overlaps(selection.span, unit.span)) ||
            (dragSpan && dragSpan.sentenceIndex === sentenceIndex && overlaps(dragSpan.span, unit.span));
          parts.push(
            <button
              key={`${sentenceIndex}-${unitIndex}`}
              type="button"
              className="cr-unit"
              data-s={sentenceIndex}
              data-u={unitIndex}
              data-marked={marked ? '' : undefined}
              data-selected={selected ? '' : undefined}
              aria-pressed={Boolean(selected)}
              disabled={disabled}
              onClick={(event) => onUnit(sentenceIndex, unitIndex, event.shiftKey)}
            >
              {sentence.slice(unit.span[0], unit.span[1])}
              {marked && <span className="av2-sr"> ({markedLabel})</span>}
            </button>,
          );
          cursor = unit.span[1];
        });
        if (cursor < sentence.length) parts.push(sentence.slice(cursor));
        return (
          <span key={sentenceIndex} className="cr-sentence" data-sentence={sentenceIndex}>
            {parts}
            {sentenceIndex < sentences.length - 1 ? ' ' : null}
          </span>
        );
      })}
    </>
  );
}
