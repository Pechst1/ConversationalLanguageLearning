/** WP-122 B · the running «marques» list: what the learner marked, and their fix. */

import React from 'react';

import { CrossIcon, IconAction } from '@/components/atelier-v2/ui';
import type { CrMark } from '@/lib/correcteur-types';

import { fill, type CorrecteurCopy } from './correcteur-copy';

export function CrMarks({ marks, sentences, copy, onRemove, onOpen }: {
  marks: CrMark[];
  sentences: string[];
  copy: CorrecteurCopy;
  onRemove: (index: number) => void;
  onOpen?: (index: number) => void;
}) {
  return (
    <section className="cr-marks" aria-label={copy.marks_title}>
      <div className="cr-marks__head">
        <h2 className="av2-label">{copy.marks_title}</h2>
        <span className="cr-marks__n">{marks.length}</span>
      </div>
      {marks.length === 0 ? (
        <p className="cr-marks__empty">{copy.marks_empty}</p>
      ) : (
        <ol className="cr-marks__rows">
          {marks.map((mark, index) => {
            const text = (sentences[mark.sentenceIndex] ?? '').slice(mark.span[0], mark.span[1]);
            return (
              <li key={`${mark.sentenceIndex}-${mark.span[0]}`} className="cr-marks__row">
                <button type="button" className="cr-marks__open" onClick={() => onOpen?.(index)}>
                  <span className="cr-marks__was" lang="fr">{text}</span>
                  <span aria-hidden="true">→</span>
                  {mark.fixFr ? (
                    <span className="cr-marks__fix" lang="fr">{mark.fixFr}</span>
                  ) : (
                    <span className="cr-marks__none">{copy.no_fix}</span>
                  )}
                </button>
                <IconAction label={fill('{r} · {t}', { r: copy.remove, t: text })} onClick={() => onRemove(index)}>
                  <CrossIcon size={14} />
                </IconAction>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
