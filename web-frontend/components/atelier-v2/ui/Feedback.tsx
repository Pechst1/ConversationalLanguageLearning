/**
 * Feedback, notices and artwork (WP-01).
 *
 * The design's session footer changes tint when an answer is graded — mint for
 * correct, blush for wrong — with a round icon badge and a Garamond-italic
 * verdict. That band is `FeedbackBand`.
 *
 * The distinction this file exists to protect: a **verdict** and a **notice**
 * look different on purpose. A verdict is something the server scored. A
 * notice is a fact about the connection, the queue or a retry — it gets no
 * tint, no tick and no celebration, because being offline is not a grade.
 * `journey-state.ts` already guarantees that separation in the data; this
 * keeps it true in the pixels.
 */

import React, { useState } from 'react';

import { resolveMediaUrl } from '@/lib/media-url';

import { CheckIcon, PendingIcon, RepairIcon, ShapeToken, type ShapeKind } from './Shapes';

export type FeedbackTone = 'correct' | 'supported' | 'wrong' | 'neutral';

export type FeedbackBandProps = {
  tone: FeedbackTone;
  /** The verdict, in the learner's control language. */
  title: string;
  /** One supporting line. The character's reply, or why it was supported. */
  detail?: React.ReactNode;
  children?: React.ReactNode;
};

export function FeedbackBand({ tone, title, detail, children }: FeedbackBandProps) {
  return (
    <div
      className="av2-feedback"
      data-tone={tone}
      role="status"
      // The verdict must be announced as one unit; assertive would interrupt
      // the learner mid-sentence if they are still typing elsewhere.
      aria-live="polite"
    >
      <span className="av2-feedback__icon" aria-hidden="true">
        {tone === 'correct' ? <CheckIcon size={15} /> : null}
        {tone === 'supported' ? <CheckIcon size={15} /> : null}
        {tone === 'wrong' ? <RepairIcon size={15} /> : null}
        {tone === 'neutral' ? <PendingIcon size={15} /> : null}
      </span>
      <div style={{ minWidth: 0 }}>
        <p className="av2-feedback__title">{title}</p>
        {detail && <p className="av2-feedback__sub">{detail}</p>}
        {children}
      </div>
    </div>
  );
}

export type CorrectionProps = {
  label: string;
  spanFr: string;
  correctedFr: string;
  noteNative?: string | null;
};

/** At most one correction, under the verdict, never a second headline. */
export function Correction({ label, spanFr, correctedFr, noteNative }: CorrectionProps) {
  return (
    <div className="av2-correction">
      <p className="av2-label">{label}</p>
      <p style={{ margin: '4px 0 0' }}>
        <span className="av2-correction__span" lang="fr">
          {spanFr}
        </span>{' '}
        <span aria-hidden="true">→</span>{' '}
        <span className="av2-correction__fix" lang="fr">
          {correctedFr}
        </span>
      </p>
      {noteNative && <p style={{ margin: '6px 0 0' }}>{noteNative}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Notice
// ---------------------------------------------------------------------------

export type NoticeProps = {
  /** `quiet` for connection facts, `alert` for something that needs an answer. */
  tone?: 'plain' | 'quiet' | 'alert';
  /** `status` for information, `alert` for a refusal the learner must see. */
  live?: 'status' | 'alert';
  /** The shape token. Never the only carrier of the message. */
  shape?: ShapeKind;
  children: React.ReactNode;
};

export function Notice({ tone = 'plain', live = 'status', shape, children }: NoticeProps) {
  return (
    <div className="av2-notice" data-tone={tone} role={live === 'alert' ? 'alert' : 'status'}>
      {shape && <ShapeToken kind={shape} size="sm" className="av2-notice__mark" />}
      <div className="av2-notice__body">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Artwork
// ---------------------------------------------------------------------------

export type ArtworkProps = {
  url: string | null | undefined;
  /** Empty string marks the image decorative; otherwise a real description. */
  alt: string;
  /** Shown in place of a failed or absent image. */
  fallbackLabel: string;
};

/**
 * Artwork is decoration: a missing or broken image must never block reading or
 * answering. It degrades to the design's own hatched placeholder rather than
 * to a browser's broken-image glyph, and it reserves 16:9 either way so the
 * step does not reflow when the image resolves.
 */
export function Artwork({ url, alt, fallbackLabel }: ArtworkProps) {
  const [failed, setFailed] = useState(false);
  const resolved = url ? resolveMediaUrl(url) || url : null;

  if (!resolved || failed) {
    return (
      <div className="av2-art__fallback" role="img" aria-label={fallbackLabel}>
        <ShapeToken kind="story" size="lg" />
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="av2-art"
      src={resolved}
      alt={alt}
      onError={() => setFailed(true)}
      loading="lazy"
      decoding="async"
    />
  );
}

// ---------------------------------------------------------------------------
// Character portrait
// ---------------------------------------------------------------------------

/**
 * The design's round initial avatar. Its `#2c6a5d` is the serial world bible's
 * `--char-marin`, so this reads the existing `--char-*` tokens rather than
 * opening a parallel palette; an unknown character falls back to the neutral
 * `--char-marchand` tone instead of picking a colour at random.
 */
const CHARACTER_TOKENS: Record<string, string> = {
  marin: 'var(--char-marin, #2c6a5d)',
  lila: 'var(--char-lila, #c2890f)',
  gus: 'var(--char-gus, #8a2f2a)',
  romy: 'var(--char-romy, #1d3a8a)',
  margaux: 'var(--char-margaux, #a85d24)',
  marchand: 'var(--char-marchand, #5b5346)',
  toi: 'var(--char-toi, #14110d)',
};

export function characterAccent(name: string | null | undefined): string | undefined {
  if (!name) return undefined;
  // Titles are stripped so "Monsieur Marchand" resolves to the same accent as
  // "Marchand"; the world bible keys characters by bare name.
  const key = name.trim().toLowerCase().replace(/^(monsieur|madame|m\.|mme)\s+/, '');
  for (const [token, value] of Object.entries(CHARACTER_TOKENS)) {
    if (key === token || key.startsWith(token)) return value;
  }
  return undefined;
}

export type PortraitProps = {
  /** The character's name, as the server sent it. Its initial is drawn. */
  name: string;
  size?: 'sm' | 'md';
};

export function Portrait({ name, size = 'md' }: PortraitProps) {
  const accent = characterAccent(name);
  const initial = name.trim().charAt(0).toUpperCase() || '·';
  return (
    <span
      className={['av2-portrait', size === 'sm' ? 'av2-portrait--sm' : null]
        .filter(Boolean)
        .join(' ')}
      style={accent ? ({ ['--av2-char' as string]: accent } as React.CSSProperties) : undefined}
      aria-hidden="true"
    >
      {initial}
    </span>
  );
}

/** Portrait + name, as one labelled unit. */
export function Byline({ name, meta }: { name: string; meta?: React.ReactNode }) {
  return (
    <span className="av2-byline">
      <Portrait name={name} size="sm" />
      <span className="av2-label">
        {name}
        {meta ? <> · {meta}</> : null}
      </span>
    </span>
  );
}
