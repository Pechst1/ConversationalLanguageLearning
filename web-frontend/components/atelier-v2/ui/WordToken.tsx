/**
 * WP-D6 — the gender is the shape.
 *
 * Feminine noun = circle, masculine noun = square (8 px radius), anything else
 * = triangle; the article in Garamond italic inside. Colour is the learner
 * state (yellow new, blue learning, ink known), never the gender. A word with
 * no stored gender is a plain ink token: its initial, no shape, no article.
 * The model (and every rule about what is known) lives in `lib/word-token.ts`.
 */

import React from 'react';

import { wordTokenModel } from '@/lib/word-token';

export type WordTokenProps = {
  word: string;
  gender?: string | null;
  partOfSpeech?: string | null;
  /** Any learner-state key: new / learning / mastered / holding / due… */
  state?: string | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
};

export function WordToken({ word, gender, partOfSpeech, state, size = 'md', className }: WordTokenProps) {
  const model = wordTokenModel({ word, gender, partOfSpeech, state });
  const classes = ['av2-word-token', size !== 'md' ? `av2-word-token--${size}` : null, className]
    .filter(Boolean)
    .join(' ');
  const text = model.shape === 'plain' ? model.initial : model.article;
  return (
    <span
      className={classes}
      data-shape={model.shape}
      data-tone={model.tone}
      role={model.label ? 'img' : undefined}
      aria-label={model.label || undefined}
      aria-hidden={model.label ? undefined : true}
    >
      {text ? <span className="av2-word-token__article" aria-hidden="true">{text}</span> : null}
    </span>
  );
}
