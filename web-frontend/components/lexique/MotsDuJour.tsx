import React from 'react';
import Link from 'next/link';

import type { DailyWordEntry, DailyWordSlate } from '@/services/api';

/* "Les Mots du jour" — the day's coordinated vocabulary slate on La Une.
   Each word wants three stamps in three memory modes across the edition:
   LU (feuilleton read) · RETROUVÉ (review recall) · PLACÉ (mission production).
   Every string maps to /vocabulary/words-of-the-day payload fields; renders
   nothing when the slate is empty. Tokens only — theme-aware for free. */

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
    <section className="mdj" aria-label="Le Lexique — les mots du jour">
      <div className="mdj-kicker">
        Le Lexique<span className="tail" />
        {allTriple
          ? <span className="mdj-complete">Édition triplée</span>
          : due > 0 && <span className="mdj-due">{due} à revoir</span>}
      </div>
      <Link className="mdj-tap" href={href} aria-label="Ouvrir la révision du lexique">
        <ul className="mdj-list">
          {words.map((entry) => {
            const count = stampCount(entry);
            return (
              <li key={entry.word_id} className={'mdj-row' + (entry.triple ? ' triple' : '')}>
                <span className="mdj-word">
                  <b>{entry.word}</b>
                  {entry.translation ? <i>{entry.translation}</i> : null}
                </span>
                <span className="mdj-stamps" aria-label={`${count} sur 3`}>
                  {STAMP_ORDER.map(({ key, label }) => {
                    const earned = Boolean((entry.stamps || {})[key]);
                    return (
                      <span key={key} className={'mdj-stamp' + (earned ? ' on' : '')}>
                        {label}
                      </span>
                    );
                  })}
                  {entry.triple && <span className="mdj-triple">Triplé</span>}
                </span>
              </li>
            );
          })}
        </ul>
      </Link>
      <MotsDuJourStyles />
    </section>
  );
}

export function MotsDuJourStyles() {
  return (
    <style jsx global>{`
      .mdj {
        border-top: 1px solid var(--app-ink);
        border-bottom: 1px solid var(--app-paper-3);
        padding: 10px 0 12px;
        color: var(--app-ink);
      }
      .mdj-kicker {
        display: flex; align-items: center; gap: 8px;
        font-size: 9px; font-weight: 900; letter-spacing: 0.14em;
        text-transform: uppercase; color: var(--app-blue);
      }
      .mdj-kicker .tail { flex: 1 1 auto; height: 1px; background: var(--app-paper-3); }
      .mdj-complete {
        border: 1px solid var(--app-red); color: var(--app-red);
        padding: 2px 5px 1px; font-size: 8px; letter-spacing: 0.12em;
        transform: rotate(-3deg);
      }
      .mdj-tap { display: block; text-decoration: none; color: inherit; }
      .mdj-list { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 7px; }
      .mdj-row {
        display: flex; align-items: baseline; justify-content: space-between; gap: 10px;
      }
      .mdj-word { display: flex; align-items: baseline; gap: 7px; min-width: 0; }
      .mdj-word b {
        font-family: var(--app-serif); font-weight: 600; font-size: 16px;
        font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .mdj-word i {
        font-style: normal; font-size: 10px; color: var(--app-ink-3);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .mdj-stamps { display: flex; align-items: center; gap: 4px; flex: 0 0 auto; }
      .mdj-stamp {
        border: 1px solid var(--app-paper-3); color: var(--app-ink-3);
        padding: 2px 4px 1px; font-size: 8px; font-weight: 700;
        letter-spacing: 0.1em; text-transform: uppercase;
      }
      .mdj-stamp.on { border-color: var(--app-ink); color: var(--app-ink); background: var(--app-paper-2); }
      .mdj-triple {
        border: 1px solid var(--app-red); color: var(--app-red);
        padding: 2px 4px 1px; font-size: 8px; font-weight: 900;
        letter-spacing: 0.1em; text-transform: uppercase; transform: rotate(-2deg);
      }
      .mdj-row.triple .mdj-word b { color: var(--app-ink); }
      .mdj-due {
        color: var(--app-blue); font-size: 9px; font-weight: 900;
        letter-spacing: 0.12em; white-space: nowrap;
      }
    `}</style>
  );
}
