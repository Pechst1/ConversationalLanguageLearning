/**
 * WP-119 phase 3 · one Papier in Le Relevé (design §3.6 `#releve`).
 *
 * A clipping, distinct from a story day's entry (the Carnet seal row) by its
 * double rule, its source lines, and the absence of a seal and of a face:
 *
 *   ═══════════════════════════════  the double hairline (`rv-dispatch__rule`)
 *   Semaine 40 · 2 oct.     Le Monde · RFI   period in blue, outlets on the right
 *   The story's title (Garamond)
 *   «Ton titre» — what was made, quoted
 *   the claims: kind rule + label, the French, who says so, «D'après …, date ↗»
 *   the words as chips: token, French, gloss
 *
 * Collapsed (older periods): the title and «Ton titre · 4 mots · 2 faits».
 * The anchor is `revue-<period>`, so `/notebook?mode=releve#revue-2026-W40`
 * lands on it. av2 tokens and existing classes only.
 */

import React from 'react';

import { ShapeToken, Surface, WordToken } from '@/components/atelier-v2/ui';
import { releveAnchor, type RvReleveEntryData, type RvReleveMadeKind } from '@/lib/revue-releve';

import { count, type ReleveCopy } from './releve-copy';
import type { RevueCopy } from './revue-copy';
import { sourceDate } from './revue-model';
import { RvSourceLine } from './RvThread';

export type RvReleveEntryProps = {
  entry: RvReleveEntryData;
  collapsed: boolean;
  onToggle: () => void;
  copy: RevueCopy;
  releve: ReleveCopy;
  now?: Date;
};

export function madeKindLabel(kind: RvReleveMadeKind, copy: RevueCopy, releve: ReleveCopy): string {
  if (kind === 'reader_question') return copy.made_question;
  if (kind === 'short_report') return copy.made_report;
  if (kind === 'tell_margaux') return releve.made_tell_margaux;
  return copy.made_headline;
}

/** «Semaine 40 · 2 oct.»; a daily period already names its day. */
export function entryKicker(entry: RvReleveEntryData, now?: Date): string {
  const date = sourceDate(entry.date, now);
  if (!date || /^\d{4}-\d{2}-\d{2}$/.test(entry.period)) return entry.periodLabel;
  return `${entry.periodLabel} · ${date}`;
}

/** The collapsed line: «Ton titre · 4 mots · 2 faits». */
export function entrySummary(entry: RvReleveEntryData, copy: RevueCopy, releve: ReleveCopy): string {
  const facts = entry.claims.filter((claim) => claim.kind === 'fact').length;
  return [
    entry.made ? madeKindLabel(entry.made.kind, copy, releve) : null,
    count(releve, 'words', entry.words.length),
    count(releve, 'facts', facts),
  ]
    .filter(Boolean)
    .join(' · ');
}

/** The outlets named once each, in the order the sources came. */
export function entryOutlets(entry: RvReleveEntryData): string[] {
  const names = entry.sources.length ? entry.sources.map((s) => s.name) : entry.claims.map((c) => c.source.name);
  return Array.from(new Set(names.map((name) => name.replace(/\s*\(.*\)$/, '')).filter(Boolean)));
}

function gender(fr: string): string | null {
  const lead = fr.trim().toLowerCase();
  if (lead.startsWith('la ') || lead.startsWith('une ')) return 'f';
  if (lead.startsWith('le ') || lead.startsWith('un ')) return 'm';
  return null;
}

const ROW: React.CSSProperties = { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '4px 12px', flexWrap: 'wrap', margin: 0 };
const KICKER: React.CSSProperties = { margin: 0, fontSize: 'var(--av2-t-meta)', fontWeight: 700, color: 'var(--av2-blue)' };
const OUTLETS: React.CSSProperties = { fontSize: 'var(--av2-t-meta)', fontWeight: 600, color: 'var(--av2-muted)' };
const TITLE: React.CSSProperties = { margin: 0, fontFamily: 'var(--av2-serif)', fontWeight: 500, fontSize: 'var(--av2-t-title)', lineHeight: 1.15, color: 'var(--av2-ink)' };
const CHIPS: React.CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 8, margin: 0, padding: 0, listStyle: 'none' };
const CHIP: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 7,
  padding: '5px 12px 5px 6px',
  borderRadius: 999,
  background: 'var(--av2-paper)',
};
const TOGGLE: React.CSSProperties = {
  alignSelf: 'flex-start',
  minHeight: 'var(--av2-tap)',
  padding: 0,
  border: 0,
  background: 'none',
  color: 'var(--av2-ink-2)',
  font: 'inherit',
  fontSize: 'var(--av2-t-meta)',
  fontWeight: 600,
  textDecoration: 'underline dotted',
  textUnderlineOffset: 3,
  cursor: 'pointer',
};

export function RvReleveEntry({ entry, collapsed, onToggle, copy, releve, now }: RvReleveEntryProps) {
  const anchor = releveAnchor(entry.period);
  const bodyId = `${anchor}-body`;
  const outlets = entryOutlets(entry);
  return (
    <Surface as="article" className="nb-sec rv-releve-entry" id={anchor} data-revue-entry={entry.period} data-collapsed={collapsed ? '' : undefined}>
      <div className="rv-dispatch__rule" aria-hidden="true" />
      <div style={ROW}>
        <p style={KICKER}>
          {entryKicker(entry, now)}
          {entry.second ? ` · ${releve.second}` : ''}
        </p>
        {outlets.length > 0 && <span style={OUTLETS}>{outlets.join(' · ')}</span>}
      </div>
      <h3 style={TITLE} lang="fr">
        {entry.titleFr}
      </h3>

      {collapsed ? (
        <p className="nb-piece__m" data-releve-summary="">
          {entrySummary(entry, copy, releve)}
        </p>
      ) : (
        <div id={bodyId} className="nb-sec">
          {entry.made && (
            <div className="rv-made" data-made={entry.made.kind}>
              <p className="av2-label">{madeKindLabel(entry.made.kind, copy, releve)}</p>
              <blockquote className="rv-quote" lang="fr" style={{ fontStyle: 'normal' }}>
                « {entry.made.textFr} »
              </blockquote>
            </div>
          )}

          {entry.claims.length > 0 && (
            <div className="rv-claims" aria-label={releve.claims_label}>
              {entry.claims.map((claim) => (
                <article key={claim.id || claim.fr} className="rv-claim" data-kind={claim.kind}>
                  <p className="rv-claim__kind">
                    <ShapeToken kind={claim.kind === 'fact' ? 'done' : 'story'} size="sm" />
                    {claim.kind === 'fact' ? copy.fact : claim.kind === 'forecast' ? copy.forecast : copy.interpretation}
                  </p>
                  <p className="rv-claim__fr" lang="fr">
                    {claim.fr}
                  </p>
                  {claim.attributedTo && claim.kind !== 'fact' && (
                    <p className="rv-claim__by" lang="fr">
                      {claim.kind === 'forecast' ? `selon ${claim.attributedTo}` : `d'après ${claim.attributedTo}`}
                    </p>
                  )}
                  {claim.source.url && <RvSourceLine source={claim.source} quote={claim.quote || null} copy={copy} now={now} />}
                </article>
              ))}
            </div>
          )}

          {entry.words.length > 0 && (
            <ul style={CHIPS} aria-label={releve.words_label}>
              {entry.words.map((word) => (
                <li key={`${word.claimId}-${word.fr}`} style={CHIP} data-releve-word="">
                  <WordToken word={word.fr} gender={gender(word.fr)} state={word.used ? 'learning' : 'new'} size="sm" />
                  <span className="rv-kept__fr" lang="fr">
                    {word.fr}
                  </span>
                  {word.gloss && <span className="rv-kept__de">{word.gloss}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <button type="button" style={TOGGLE} aria-expanded={!collapsed} aria-controls={collapsed ? undefined : bodyId} onClick={onToggle}>
        {collapsed ? releve.show : releve.hide}
      </button>
    </Surface>
  );
}

export default RvReleveEntry;
