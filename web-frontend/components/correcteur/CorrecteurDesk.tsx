/**
 * WP-122 B · the desk: the draft on paper, the field, the marks, «Bon à tirer», then
 * the result. Owns the interaction state; the page owns loading and the client.
 *
 * Tap a word → the field opens on it. Drag across words (pointer down on one, move,
 * up on another; same sentence) → the field opens on the span. Shift+click extends
 * the open selection for keyboard and mouse users. Tapping a marked word reopens its
 * mark with the fix filled in.
 */

import React, { useCallback, useRef, useState } from 'react';

import { Action } from '@/components/atelier-v2/ui';
import type { CrDraft, CrMark, CrResult, CrSpan } from '@/lib/correcteur-types';

import { fill, type CorrecteurCopy } from './correcteur-copy';
import { markIndexAt, removeMark, selectUnits, unitsOf, upsertMark, type CrSelection } from './correcteur-model';
import { CrDraftText, CrPaper } from './CrPaper';
import { CrField } from './CrField';
import { CrMarks } from './CrMarks';
import { CrResultView } from './CrResult';

export type CorrecteurDeskProps = {
  draft: CrDraft;
  copy: CorrecteurCopy;
  onSubmit: (marks: CrMark[]) => Promise<CrResult>;
  onReleve?: () => void;
  /** Tests and the mock gallery: start with these. */
  initialMarks?: CrMark[];
  initialSelection?: CrSelection | null;
};

type Drag = { sentenceIndex: number; from: number; to: number; moved: boolean };

export function CorrecteurDesk({ draft, copy, onSubmit, onReleve, initialMarks = [], initialSelection = null }: CorrecteurDeskProps) {
  const [marks, setMarks] = useState<CrMark[]>(initialMarks);
  const [selection, setSelection] = useState<CrSelection | null>(initialSelection);
  const [anchor, setAnchor] = useState<{ sentenceIndex: number; unit: number } | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [result, setResult] = useState<CrResult | null>(draft.result);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const suppressClick = useRef(false);

  const open = useCallback(
    (sentenceIndex: number, from: number, to: number = from) => {
      const next = selectUnits(draft, sentenceIndex, from, to);
      setSelection(next);
      setAnchor({ sentenceIndex, unit: from });
    },
    [draft],
  );

  const onUnit = (sentenceIndex: number, unitIndex: number, extend: boolean) => {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    if (extend && anchor && anchor.sentenceIndex === sentenceIndex) {
      open(sentenceIndex, anchor.unit, unitIndex);
      setAnchor(anchor);
      return;
    }
    open(sentenceIndex, unitIndex);
  };

  const unitFromPoint = (x: number, y: number): { s: number; u: number } | null => {
    if (typeof document === 'undefined') return null;
    const element = document.elementFromPoint(x, y)?.closest?.('[data-u]') as HTMLElement | null;
    if (!element) return null;
    return { s: Number(element.dataset.s), u: Number(element.dataset.u) };
  };

  const pointerHandlers = {
    onPointerDown: (event: React.PointerEvent) => {
      // A drag that ended off a word never got its click: do not swallow the next tap.
      suppressClick.current = false;
      const hit = unitFromPoint(event.clientX, event.clientY);
      if (hit) setDrag({ sentenceIndex: hit.s, from: hit.u, to: hit.u, moved: false });
    },
    onPointerMove: (event: React.PointerEvent) => {
      if (!drag) return;
      const hit = unitFromPoint(event.clientX, event.clientY);
      if (hit && hit.s === drag.sentenceIndex && hit.u !== drag.to) setDrag({ ...drag, to: hit.u, moved: true });
    },
    onPointerUp: () => {
      if (drag && drag.moved && drag.from !== drag.to) {
        suppressClick.current = true;
        open(drag.sentenceIndex, drag.from, drag.to);
      }
      setDrag(null);
    },
    onPointerCancel: () => setDrag(null),
  };

  let dragSpan: { sentenceIndex: number; span: CrSpan } | null = null;
  if (drag && drag.moved) {
    const units = unitsOf(draft, drag.sentenceIndex);
    const a = units[Math.min(drag.from, drag.to)];
    const b = units[Math.max(drag.from, drag.to)];
    if (a && b) dragSpan = { sentenceIndex: drag.sentenceIndex, span: [a.span[0], b.span[1]] };
  }

  const existing = selection ? markIndexAt(marks, selection.sentenceIndex, selection.span) : -1;

  const submit = async () => {
    setPending(true);
    setFailed(false);
    try {
      setResult(await onSubmit(marks));
      setSelection(null);
      // The proof comes back from the printer: read it from the top.
      if (typeof window !== 'undefined') window.scrollTo?.({ top: 0 });
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };

  if (result) {
    return (
      <div className="cr-desk" data-state="result">
        <CrResultView result={result} kickerFr={draft.kickerFr} titleFr={draft.titleFr} bylineFr={draft.bylineFr} copy={copy} onReleve={onReleve} />
      </div>
    );
  }

  return (
    <div className="cr-desk" data-state="draft">
      <p className="cr-intro">
        <strong>{draft.errorsCount === 1 ? copy.intro_one : fill(copy.intro, { n: draft.errorsCount })}</strong> {copy.how}
      </p>
      <div className="cr-paper-wrap" {...pointerHandlers}>
        <CrPaper kickerFr={draft.kickerFr} titleFr={draft.titleFr} bylineFr={draft.bylineFr}>
          <CrDraftText
            sentences={draft.sentences}
            units={draft.units}
            marks={marks}
            selection={selection}
            dragSpan={dragSpan}
            onUnit={onUnit}
            markedLabel={copy.marks_title}
            disabled={pending}
          />
        </CrPaper>
      </div>
      {selection && (
        <CrField
          selection={selection}
          initialFix={existing >= 0 ? marks[existing].fixFr : null}
          copy={copy}
          onMark={(fix, picked) => {
            setMarks((current) => upsertMark(current, { sentenceIndex: selection.sentenceIndex, span: selection.span, fixFr: fix, picked }));
            setSelection(null);
          }}
          onCancel={() => setSelection(null)}
        />
      )}
      <CrMarks
        marks={marks}
        sentences={draft.sentences}
        copy={copy}
        onRemove={(index) => setMarks((current) => removeMark(current, index))}
        onOpen={(index) => {
          const mark = marks[index];
          const sentence = draft.sentences[mark.sentenceIndex] ?? '';
          setSelection({ sentenceIndex: mark.sentenceIndex, span: mark.span, text: sentence.slice(mark.span[0], mark.span[1]), options: null });
        }}
      />
      <div className="rv-foot cr-foot">
        {failed && (
          <p className="cr-failed" role="alert">
            {copy.error_body}
          </p>
        )}
        <Action tone="primary" pending={pending} pendingLabel={copy.pending} onClick={() => void submit()}>
          {copy.press}
        </Action>
      </div>
    </div>
  );
}
