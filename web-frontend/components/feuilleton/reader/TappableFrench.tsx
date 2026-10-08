/* French text whose words can be tapped for help.
 *
 * Each word is a real <button>, so it is reachable by keyboard and announced as
 * an action; punctuation and élision articles stay inert text. The affordance is
 * a dotted underline, not a colour, so it never competes with the character
 * accent that identifies the speaker.
 *
 * WP-90: the word's label is in the learner's language (`wordLabel`, from the
 * reader's copy table), and `FrenchLine` makes a whole line one focusable
 * element labelled with the sentence, its words reached by the arrow keys
 * (a roving tabindex) instead of one Tab stop per word. */

import React, { useCallback, useMemo, useRef } from 'react';

import { frenchSpacing } from '@/lib/french-typography';

import { rovingWordTarget, tokenizeFrench } from './french-text';
import { markTokens, type MarkRange } from './grammar-marks';

const DEFAULT_WORD_LABEL = 'Aide pour « {word} »';

function labelFor(template: string, word: string): string {
  return template.replace('{word}', word);
}

export function TappableFrench({
  text,
  idPrefix,
  onWord,
  disabled = false,
  wordLabel = DEFAULT_WORD_LABEL,
  roving = false,
  marks = null,
}: {
  text: string;
  idPrefix: string;
  onWord: (word: { surface: string; term: string }) => void;
  disabled?: boolean;
  /** «Help with “{word}”» — the learner's language; French by default. */
  wordLabel?: string;
  /** Inside a `FrenchLine`: the words leave the Tab order and rove by arrow. */
  roving?: boolean;
  /**
   * WP-92 «Rayons X»: the rule's form in this line (ranges into `text`). Marks
   * snap to whole words, so a word button is marked whole, never split.
   */
  marks?: MarkRange[] | null;
}) {
  // WP-82: « ? ! » stay on their word's line (U+202F). The narrow space is a
  // non-word run, so the tappable words — and their lookup terms — are unchanged.
  const tokens = useMemo(
    () =>
      marks && marks.length
        ? markTokens(text, marks, idPrefix)
        : tokenizeFrench(frenchSpacing(text), idPrefix).map((token) => ({ ...token, marked: false })),
    [idPrefix, text, marks],
  );
  if (!tokens.length) return null;
  return (
    <>
      {tokens.map((token) =>
        token.word && !disabled ? (
          <button
            key={token.key}
            type="button"
            className="fr-word"
            data-word=""
            data-mark={token.marked ? 'rule' : undefined}
            tabIndex={roving ? -1 : undefined}
            onClick={() => onWord({ surface: token.text, term: token.term })}
            aria-label={labelFor(wordLabel, token.text)}
          >
            {token.text}
          </button>
        ) : (
          <span key={token.key} data-mark={token.marked ? 'rule' : undefined}>
            {token.text}
          </span>
        ),
      )}
    </>
  );
}

/**
 * One line of French as ONE focusable element, labelled with the whole
 * sentence — so a screen reader reads it as a sentence, and Tab moves line by
 * line. Arrow keys (or Enter) step into its words; Escape steps back out.
 */
export function FrenchLine({
  text,
  idPrefix,
  onWord,
  wordLabel,
  className = 'fr-line',
  marks = null,
  marksLabel = '',
  marksLang,
}: {
  text: string;
  idPrefix: string;
  onWord: (word: { surface: string; term: string }) => void;
  wordLabel?: string;
  className?: string;
  /** WP-92 «Rayons X»: the rule's form in this line, when the marks are on. */
  marks?: MarkRange[] | null;
  /**
   * What a screen reader hears once for the line while the marks are on —
   * «Today's rule: suis allé» — visually hidden, and the line's description.
   */
  marksLabel?: string;
  /** The label's language (the reader's chrome); the line itself is French. */
  marksLang?: string;
}) {
  const ref = useRef<HTMLParagraphElement | null>(null);
  const onKeyDown = useCallback((event: React.KeyboardEvent<HTMLParagraphElement>) => {
    const root = ref.current;
    if (!root) return;
    const words = Array.from(root.querySelectorAll<HTMLButtonElement>('button[data-word]'));
    const current = words.indexOf(event.target as HTMLButtonElement);
    // Enter and Space on a word are its own click; only the line itself treats
    // them as "step in".
    if (current >= 0 && (event.key === 'Enter' || event.key === ' ')) return;
    const next = rovingWordTarget(event.key, event.target === root ? -1 : current, words.length);
    if (next === null) return;
    event.preventDefault();
    event.stopPropagation();
    if (next < 0) root.focus();
    else words[next]?.focus();
  }, []);
  const sentence = frenchSpacing(text);
  const marked = Boolean(marks && marks.length && marksLabel);
  const describedBy = marked ? `${idPrefix}-rx` : undefined;
  return (
    <p
      ref={ref}
      className={className}
      lang="fr"
      role="group"
      tabIndex={0}
      aria-label={sentence}
      aria-describedby={describedBy}
      data-roving-line=""
      data-marked={marked ? 'true' : undefined}
      onKeyDown={onKeyDown}
    >
      <TappableFrench
        text={text}
        idPrefix={idPrefix}
        onWord={onWord}
        wordLabel={wordLabel}
        roving
        marks={marks}
      />
      {marked && (
        <span className="fr-sr" id={describedBy} lang={marksLang}>
          {` ${marksLabel}`}
        </span>
      )}
    </p>
  );
}

export default TappableFrench;
