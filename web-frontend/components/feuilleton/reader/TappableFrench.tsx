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
  revealChars = null,
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
  /**
   * WP-144: the words arrive with the voice. Only the tokens whose first
   * character is within this many characters show; the rest keep their place
   * (the line never reflows) but are invisible. Null shows the whole line.
   */
  revealChars?: number | null;
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
  let offset = 0;
  const starts = tokens.map((token) => {
    const start = offset;
    offset += token.text.length;
    return start;
  });
  const hidden = (index: number) =>
    revealChars !== null && revealChars !== undefined && starts[index] > revealChars ? '' : undefined;
  const render = (token: (typeof tokens)[number], index: number, part?: { text: string; key: string }) =>
        token.word && !disabled ? (
          <button
            key={token.key}
            type="button"
            className="fr-word"
            data-word=""
            data-unrevealed={hidden(index)}
            data-mark={token.marked ? 'rule' : undefined}
            tabIndex={roving ? -1 : undefined}
            onClick={() => onWord({ surface: token.text, term: token.term })}
            aria-label={labelFor(wordLabel, token.text)}
          >
            {token.text}
          </button>
        ) : (
          <span key={part ? part.key : token.key} data-mark={token.marked ? 'rule' : undefined} data-unrevealed={hidden(index)}>
            {part ? part.text : token.text}
          </span>
        );
  // WP-144b: a word button is an atomic inline, so the browser may break on
  // either side of it. An elided form never ends a line alone («d’» + «Odile»,
  // and l’, qu’, j’, n’, s’, c’, m’, t’, jusqu’, lorsqu’, puisqu’), and the
  // punctuation after a word («Marin» + «.») never starts the next line.
  const units = lineUnits(tokens);
  const renderPart = (part: LinePart) =>
    render(tokens[part.index], part.index, part.text !== undefined ? { text: part.text, key: `${tokens[part.index].key}-${part.tail ? 'b' : 'a'}` } : undefined);
  return (
    <>
      {units.map((unit) =>
        unit.length === 1 ? (
          renderPart(unit[0])
        ) : (
          <span key={`${tokens[unit[0].index].key}-run`} className="fr-elision" style={{ whiteSpace: 'nowrap' }}>
            {unit.map(renderPart)}
          </span>
        ),
      )}
    </>
  );
}

/** A token, or a slice of a punctuation run (`text`), in a line unit. */
export type LinePart = { index: number; text?: string; tail?: boolean };

const LETTER_END = /[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]$/;
const HAS_LETTER = /[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]/;
/** The punctuation that hangs on the word before it: up to the first breakable space (U+202F holds). */
const HANGING = /^(?:[^\s]|\u202F)+/;

/**
 * The line's tokens as unbreakable units: an elision group, then the
 * punctuation that follows a word (up to its first breakable space) glued to
 * it. Everything else is a unit of its own.
 */
export function lineUnits(tokens: Array<{ text: string }>): LinePart[][] {
  const units: LinePart[][] = [];
  const groups = elisionGroups(tokens);
  for (let g = 0; g < groups.length; g += 1) {
    const unit: LinePart[] = groups[g].map((index) => ({ index }));
    const last = groups[g][groups[g].length - 1];
    const next = groups[g + 1];
    const follower = next && next.length === 1 ? tokens[next[0]] : null;
    const hanging = follower && !HAS_LETTER.test(follower.text) && LETTER_END.test(tokens[last].text)
      ? (follower.text.match(HANGING) || [''])[0]
      : '';
    if (follower && hanging) {
      unit.push(hanging === follower.text ? { index: next[0] } : { index: next[0], text: hanging });
      units.push(unit);
      if (hanging !== follower.text) units.push([{ index: next[0], text: follower.text.slice(hanging.length), tail: true }]);
      g += 1;
    } else {
      units.push(unit);
    }
  }
  return units;
}

const ELIDED = new Set(['l', 'd', 'j', 'n', 'm', 't', 's', 'c', 'qu', 'jusqu', 'lorsqu', 'puisqu']);
const APOSTROPHE_ONLY = /^['’ʼ]$/;

/**
 * Token indexes grouped so that an elided form, its apostrophe and the word
 * after it form one group (one unbreakable run); every other token is alone.
 */
export function elisionGroups(tokens: Array<{ text: string }>): number[][] {
  const groups: number[][] = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const elided = ELIDED.has(tokens[index].text.toLowerCase());
    const apostrophe = tokens[index + 1] && APOSTROPHE_ONLY.test(tokens[index + 1].text);
    const next = tokens[index + 2];
    if (elided && apostrophe && next && /^[A-Za-zÀ-ÖØ-öø-ÿŒœ]/.test(next.text)) {
      groups.push([index, index + 1, index + 2]);
      index += 2;
    } else {
      groups.push([index]);
    }
  }
  return groups;
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
  revealChars = null,
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
  /** WP-144: see `TappableFrench`. */
  revealChars?: number | null;
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
        revealChars={revealChars}
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
