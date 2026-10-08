/**
 * F-1 — the x-ray sentence (content program 2026-10-03).
 *
 * One French sentence with each marked span underlined in an av2 role colour
 * (red, blue, yellow, green, in the catalogue's order). A discontinuous mark
 * («ne … que») underlines each of its pieces; overlapping marks stack their
 * lines. Tapping or hovering a span — or its key below — selects that mark:
 * its line thickens and its role and note are read out under the sentence.
 *
 * The sentence stays plain text for a screen reader; the keys are the
 * accessible controls (buttons with aria-pressed, the note in a live region).
 * Sans throughout: a screen's one Garamond line is its headline.
 */

import React, { useMemo, useState } from 'react';

import {
  RULE_CARD_COPY,
  locateXray,
  pickXrayMark,
  usableXray,
  xrayPieces,
  xrayRoleLabel,
  xraySegments,
  xrayTone,
  type XrayPayload,
} from '@/lib/rule-card';
import type { ControlLanguage } from '@/types/daily-journey';

export type XraySentenceProps = {
  xray: XrayPayload | null | undefined;
  language: ControlLanguage;
  /** Print the small title over the sentence (default true). */
  titled?: boolean;
};

/* Stacked 2px lines (4px for the selected mark), one per covering mark. The
   outer box-shadow is clipped to outside the box, so only the strip below the
   text shows — no stroke, no border, no new colour. */
function underline(marks: number[], selected: number | null): React.CSSProperties {
  let offset = 0;
  const lines = marks.map((mark) => {
    offset += mark === selected ? 4 : 2;
    return `0 ${offset}px 0 var(--xr-${xrayTone(mark)})`;
  });
  return { boxShadow: lines.join(', '), marginBottom: offset > 2 ? offset - 2 : 0 };
}

export function XraySentence({ xray, language, titled = true }: XraySentenceProps) {
  const copy = RULE_CARD_COPY[language] ?? RULE_CARD_COPY.en;
  const sentence = xray?.sentence ?? '';
  const marks = useMemo(() => (Array.isArray(xray?.marks) ? xray!.marks : []), [xray]);
  const located = useMemo(() => locateXray(sentence, marks), [sentence, marks]);
  const segments = useMemo(() => xraySegments(sentence, marks), [sentence, marks]);
  const firstDrawn = located.findIndex((ranges) => ranges.length > 0);
  const [selected, setSelected] = useState<number | null>(firstDrawn >= 0 ? firstDrawn : null);

  if (!usableXray(xray)) return null;
  const active = selected != null ? marks[selected] : null;
  const role = xrayRoleLabel(active?.role);
  const note = String(active?.explanation || '').trim();

  return (
    <section className="xr" aria-label={copy.xray}>
      {titled && <p className="xr-title">{copy.xray}</p>}
      <p className="xr-sentence" lang="fr">
        {segments.map((segment, index) =>
          segment.marks.length === 0 ? (
            <React.Fragment key={index}>{segment.text}</React.Fragment>
          ) : (
            <span
              key={index}
              className="xr-seg"
              data-on={selected != null && segment.marks.indexOf(selected) >= 0 ? 'true' : undefined}
              style={underline(segment.marks, selected)}
              onClick={() => setSelected(pickXrayMark(segment.marks, selected, sentence, marks))}
              onMouseEnter={() => {
                if (selected == null || segment.marks.indexOf(selected) < 0) {
                  setSelected(pickXrayMark(segment.marks, null, sentence, marks));
                }
              }}
            >
              {segment.text}
            </span>
          ),
        )}
      </p>
      <p className="xr-hint">{copy.xrayHint}</p>
      <ul className="xr-keys" aria-label={copy.xrayMarks}>
        {marks.map((mark, index) =>
          located[index]?.length ? (
            <li key={index}>
              <button
                type="button"
                className="xr-key"
                data-tone={xrayTone(index)}
                aria-pressed={selected === index}
                onClick={() => setSelected(index)}
              >
                <span className="xr-key__swatch" aria-hidden="true" />
                <span className="xr-key__token" lang="fr">
                  {xrayPieces(mark.token).join(' … ')}
                </span>
              </button>
            </li>
          ) : null,
        )}
      </ul>
      <div className="xr-note" aria-live="polite" data-tone={selected != null ? xrayTone(selected) : undefined}>
        {active && (
          <>
            {role && <p className="xr-note__role">{role}</p>}
            {note && <p className="xr-note__text">{note}</p>}
          </>
        )}
      </div>
    </section>
  );
}

export default XraySentence;
