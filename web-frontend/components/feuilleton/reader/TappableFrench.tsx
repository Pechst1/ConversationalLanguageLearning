/* French text whose words can be tapped for help.
 *
 * Each word is a real <button>, so it is reachable by keyboard and announced as
 * an action; punctuation and élision articles stay inert text. The affordance is
 * a dotted underline, not a colour, so it never competes with the character
 * accent that identifies the speaker. */

import { useMemo } from 'react';

import { frenchSpacing } from '@/lib/french-typography';

import { tokenizeFrench } from './french-text';

export function TappableFrench({
  text,
  idPrefix,
  onWord,
  disabled = false,
}: {
  text: string;
  idPrefix: string;
  onWord: (word: { surface: string; term: string }) => void;
  disabled?: boolean;
}) {
  // WP-82: « ? ! » stay on their word's line (U+202F). The narrow space is a
  // non-word run, so the tappable words — and their lookup terms — are unchanged.
  const tokens = useMemo(() => tokenizeFrench(frenchSpacing(text), idPrefix), [idPrefix, text]);
  if (!tokens.length) return null;
  return (
    <>
      {tokens.map((token) =>
        token.word && !disabled ? (
          <button
            key={token.key}
            type="button"
            className="fr-word"
            onClick={() => onWord({ surface: token.text, term: token.term })}
            aria-label={`Aide pour « ${token.text} »`}
          >
            {token.text}
          </button>
        ) : (
          <span key={token.key}>{token.text}</span>
        ),
      )}
    </>
  );
}

export default TappableFrench;
