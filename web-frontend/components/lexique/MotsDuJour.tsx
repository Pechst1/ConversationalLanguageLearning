import React from 'react';
import Link from 'next/link';

import { AtelierV2Root, Chip, ShapeToken } from '@/components/atelier-v2/ui';
import type { DailyWordEntry, DailyWordSlate } from '@/services/api';

/* "Les Mots du jour" — the day's coordinated vocabulary slate.
   Each word wants three stamps in three memory modes across the edition:
   LU (feuilleton read) · RETROUVÉ (review recall) · PLACÉ (mission production).
   Every string maps to /vocabulary/words-of-the-day payload fields; renders
   nothing when the slate is empty.

   Claude design system (Atelier V2): the ruled strip became one paper surface
   of rows — the word in Garamond italic, its gloss beside it, and the three
   stamps as small pills. An earned stamp is an ink pill (ink = done); a triple
   is the yellow reward chip. Colour never carries the state alone: every pill
   prints its word, and the stamp row exposes its "n sur 3" count. */

const STAMP_ORDER: Array<{ key: 'lu' | 'retrouve' | 'place'; label: string }> = [
  { key: 'lu', label: 'Lu' },
  { key: 'retrouve', label: 'Retrouvé' },
  { key: 'place', label: 'Placé' },
];

function stampCount(entry: DailyWordEntry): number {
  const stamps = entry.stamps || {};
  return STAMP_ORDER.filter(({ key }) => Boolean(stamps[key])).length;
}

export default function MotsDuJour({
  slate,
  due = 0,
  href = '/vocabulary/review',
}: {
  slate: DailyWordSlate | null;
  due?: number;
  href?: string;
}) {
  const words = slate?.words || [];
  if (words.length === 0) return null;
  const triples = words.filter((entry) => entry.triple).length;
  const allTriple = triples === words.length;

  return (
    <AtelierV2Root as="section" className="mdj" aria-label="Le Lexique — les mots du jour">
      <div className="mdj-head">
        <p className="av2-label">Le Lexique · les mots du jour</p>
        {allTriple
          ? <Chip tone="reward" icon={<ShapeToken kind="reward" size="sm" />}>Édition triplée</Chip>
          : due > 0 && <Chip tone="quiet">{due} à revoir</Chip>}
      </div>
      <Link className="mdj-tap" href={href} aria-label="Ouvrir la révision du lexique">
        <ul className="mdj-list">
          {words.map((entry) => {
            const count = stampCount(entry);
            return (
              <li key={entry.word_id} className="mdj-row" data-triple={entry.triple ? 'true' : undefined}>
                <span className="mdj-word">
                  <b className="av2-fr">{entry.word}</b>
                  {entry.translation ? <i>{entry.translation}</i> : null}
                </span>
                <span className="mdj-stamps" aria-label={`${count} sur 3`}>
                  {STAMP_ORDER.map(({ key, label }) => {
                    const earned = Boolean((entry.stamps || {})[key]);
                    return (
                      <span key={key} className="mdj-stamp" data-on={earned ? 'true' : undefined}>
                        {label}
                      </span>
                    );
                  })}
                  {entry.triple && <span className="mdj-stamp mdj-stamp--triple">Triplé</span>}
                </span>
              </li>
            );
          })}
        </ul>
      </Link>
      <MotsDuJourStyles />
    </AtelierV2Root>
  );
}

export function MotsDuJourStyles() {
  return (
    <style jsx global>{`
      .av2 .mdj-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        min-width: 0;
        margin-bottom: 8px;
      }
      .av2 .mdj-tap {
        display: block;
        padding: 6px 14px;
        border-radius: var(--av2-r-card);
        background: var(--av2-card);
        color: inherit;
        text-decoration: none;
        transition: transform var(--av2-press-dur);
      }
      .av2 .mdj-tap:active { transform: scale(0.985); }
      .av2 .mdj-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; min-width: 0; }
      .av2 .mdj-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        min-height: var(--av2-tap);
        padding: 8px 0;
        min-width: 0;
      }
      .av2 .mdj-row + .mdj-row { border-top: 1px solid var(--av2-line); }
      .av2 .mdj-word { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
      .av2 .mdj-word b {
        font-family: var(--av2-serif);
        font-weight: 600;
        font-size: var(--av2-t-rule);
        font-style: italic;
        color: var(--av2-ink);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .av2 .mdj-word i {
        font-style: normal;
        font-size: var(--av2-t-meta);
        color: var(--av2-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .av2 .mdj-stamps { display: flex; align-items: center; gap: 4px; flex: 0 0 auto; }
      .av2 .mdj-stamp {
        display: inline-flex;
        align-items: center;
        min-height: 1.5rem;
        padding: 0 8px;
        border-radius: var(--av2-r-pill);
        background: var(--av2-line);
        color: var(--av2-muted);
        font-size: 0.6875rem;
        font-weight: 700;
        line-height: 1;
      }
      .av2 .mdj-stamp[data-on='true'] { background: var(--av2-ink); color: var(--av2-on-ink); }
      .av2 .mdj-stamp--triple { background: var(--av2-yellow); color: var(--av2-on-yellow); }
      @media (max-width: 360px) {
        .av2 .mdj-row { flex-wrap: wrap; }
      }
    `}</style>
  );
}
