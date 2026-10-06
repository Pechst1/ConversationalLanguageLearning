/**
 * WP-122 B · the small field «Corrige» that a tapped word or a dragged span opens:
 * type the right form, or (A1–A2) pick one of three forms the rules made — the
 * word's own and two others. «Marquer» files the mark (a secondary press: the one
 * primary on the screen is «Bon à tirer»); a mark may go without a fix.
 */

import React, { useEffect, useRef, useState } from 'react';

import { Action, ChoiceList } from '@/components/atelier-v2/ui';

import type { CorrecteurCopy } from './correcteur-copy';
import type { CrSelection } from './correcteur-model';

export type CrFieldProps = {
  selection: CrSelection;
  initialFix?: string | null;
  copy: CorrecteurCopy;
  onMark: (fix: string | null, picked: boolean) => void;
  onCancel: () => void;
};

export function CrField({ selection, initialFix = null, copy, onMark, onCancel }: CrFieldProps) {
  const [value, setValue] = useState(initialFix ?? '');
  const [picked, setPicked] = useState<string | null>(null);
  const ref = useRef<HTMLElement>(null);
  const key = `${selection.sentenceIndex}:${selection.span[0]}:${selection.span[1]}`;
  useEffect(() => {
    setValue(initialFix ?? '');
    setPicked(null);
    // The field opens under the paper: bring it into view (and above the sticky press).
    ref.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
  }, [key, initialFix]);

  const fix = value.trim();
  return (
    <section ref={ref} className="cr-field" aria-label={copy.field_label} data-correcteur-field="">
      <p className="cr-field__what">
        <span className="av2-label">{copy.field_label}</span>{' '}
        <span className="cr-field__text" lang="fr">
          «&nbsp;{selection.text}&nbsp;»
        </span>
      </p>
      {selection.options && (
        <ChoiceList
          label={copy.options_label}
          options={selection.options.map((option) => ({ id: option, textFr: option }))}
          selectedId={picked}
          onSelect={(id) => {
            setPicked(id);
            setValue(id);
          }}
          statusLabels={{ selected: copy.status_selected, correct: copy.status_correct, wrong: copy.status_wrong }}
        />
      )}
      <label className="av2-field">
        <span className="av2-field__label">{copy.field_label}</span>
        <input
          className="av2-field__control cr-field__input"
          lang="fr"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          value={value}
          placeholder={copy.field_placeholder}
          onChange={(event) => {
            setValue(event.target.value);
            setPicked(null);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onMark(fix || null, Boolean(picked && picked === fix));
          }}
        />
      </label>
      <div className="cr-field__actions">
        <Action tone="secondary" onClick={() => onMark(fix || null, Boolean(picked && picked === fix))}>
          {fix ? copy.mark : copy.mark_no_fix}
        </Action>
        <Action tone="quiet" onClick={onCancel}>
          {copy.cancel}
        </Action>
      </div>
    </section>
  );
}
