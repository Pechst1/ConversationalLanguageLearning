/**
 * Recall inputs (WP-01): choice cards, word tiles, and the text field.
 *
 * The choice card is the design's option button — 2px edge, 16px radius,
 * Garamond italic, `0 3px 0` press — with the design's own state colouring:
 * unselected paper/line, selected blue edge and blue dot, correct green face,
 * wrong red face.
 *
 * Two accessibility rules the artboard cannot express:
 *
 *  1. **A graded option stays legible.** The options lock after grading, and a
 *     locked option must not be dimmed — `opacity` on a disabled button is the
 *     usual way answered questions become unreadable. Only the affordance goes
 *     away; the text keeps full contrast.
 *  2. **Status is never colour alone.** Green/red faces are paired with a
 *     glyph *and* a visually-hidden word, so the verdict survives greyscale,
 *     colour-blindness and a screen reader.
 */

import React from 'react';

import { CheckIcon, RepairIcon } from './Shapes';

export type ChoiceState = 'idle' | 'selected' | 'correct' | 'wrong';

export type ChoiceOption = {
  id: string;
  /** French answer text. Rendered `lang="fr"` so it is spoken correctly. */
  textFr: string;
  state?: ChoiceState;
};

export type ChoiceListProps = {
  options: ChoiceOption[];
  selectedId: string | null;
  /** Group name, in the learner's control language. */
  label: string;
  disabled?: boolean;
  onSelect: (id: string) => void;
  /** Localized status words, for the non-colour half of each state. */
  statusLabels: { selected: string; correct: string; wrong: string };
};

export function ChoiceList({
  options,
  selectedId,
  label,
  disabled = false,
  onSelect,
  statusLabels,
}: ChoiceListProps) {
  return (
    <ul className="av2-choices" role="radiogroup" aria-label={label}>
      {options.map((option) => {
        const selected = option.id === selectedId;
        const state: ChoiceState =
          option.state ?? (selected ? 'selected' : 'idle');
        const statusWord =
          state === 'correct'
            ? statusLabels.correct
            : state === 'wrong'
              ? statusLabels.wrong
              : selected
                ? statusLabels.selected
                : null;

        return (
          <li key={option.id}>
            <button
              type="button"
              role="radio"
              aria-checked={selected}
              className="av2-choice"
              data-state={state}
              disabled={disabled}
              onClick={() => onSelect(option.id)}
            >
              <span lang="fr">{option.textFr}</span>
              <span className="av2-choice__dot" aria-hidden="true">
                {state === 'correct' ? <CheckIcon size={13} /> : null}
                {state === 'wrong' ? <RepairIcon size={13} /> : null}
              </span>
              {statusWord && <span className="av2-sr">{statusWord}</span>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Word tiles
// ---------------------------------------------------------------------------

export type WordTilesProps = {
  /** The bank, in the server's order. */
  options: ChoiceOption[];
  /** Ids the learner has placed, in their chosen order. */
  placed: string[];
  label: string;
  emptyHint: string;
  removeLabel: string;
  disabled?: boolean;
  onPlace: (id: string) => void;
  onRemoveLast: () => void;
};

export function WordTiles({
  options,
  placed,
  label,
  emptyHint,
  removeLabel,
  disabled = false,
  onPlace,
  onRemoveLast,
}: WordTilesProps) {
  const byId = new Map(options.map((option) => [option.id, option]));
  const remaining = options.filter((option) => !placed.includes(option.id));

  return (
    <div className="av2-tiles">
      {/* The assembled sentence. `aria-live` so a screen reader hears each
          word land, rather than having to re-read the whole region. */}
      <p
        className="av2-tiles__line"
        lang="fr"
        data-empty={placed.length === 0 ? 'true' : undefined}
        aria-live="polite"
        aria-label={label}
      >
        {placed.length === 0
          ? emptyHint
          : placed.map((id) => byId.get(id)?.textFr ?? '').join(' ')}
      </p>

      <div className="av2-tiles__bank">
        {remaining.map((option) => (
          <button
            key={option.id}
            type="button"
            className="av2-tile"
            lang="fr"
            disabled={disabled}
            onClick={() => onPlace(option.id)}
          >
            {option.textFr}
          </button>
        ))}
      </div>

      {placed.length > 0 && !disabled && (
        <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={onRemoveLast}>
          {removeLabel}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Text field
// ---------------------------------------------------------------------------

export type TextAnswerProps = {
  label: string;
  value: string;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  /** Set when the answer was refused as empty. Drives `aria-invalid`. */
  invalid?: boolean;
  /** Id of the message explaining `invalid`. */
  describedBy?: string;
  onChange: (text: string) => void;
  inputRef?: React.Ref<HTMLTextAreaElement>;
};

/**
 * The answer field, as a plain element factory rather than a component.
 *
 * Callers that need the `<textarea>` to sit in their **own** returned element
 * tree — the daily-journey step renderers do, because the WP-10 draft-recovery
 * tests drive the real `onChange` through a shallow tree walk — call this
 * directly: `{textAnswerField({ ... })}`. `TextAnswer` below is the ordinary
 * component wrapper over the identical implementation, so there is one field in
 * the system, not two.
 */
export function textAnswerField({
  label,
  value,
  placeholder,
  rows = 3,
  disabled = false,
  invalid = false,
  describedBy,
  onChange,
  inputRef,
}: TextAnswerProps): JSX.Element {
  return (
    <label className="av2-field">
      <span className="av2-field__label">{label}</span>
      <textarea
        ref={inputRef}
        className="av2-field__control"
        lang="fr"
        rows={rows}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function TextAnswer(props: TextAnswerProps) {
  return textAnswerField(props);
}
