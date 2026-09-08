import React from 'react';
import type { VocabularyBiography, VocabularyBiographyEvent, VocabularyBiographyExample } from '@/services/api';
import { cn } from '@/lib/utils';
import { learnerGloss } from '@/lib/glosses';
import { AtelierV2Root, BottomSheet, Row, StateBlock, Surface } from '@/components/atelier-v2/ui';
import { FragilityBadge } from './FragilityBadge';

/* The word biography, on the Claude design system (Atelier V2).
 *
 * One bottom sheet (handle, scrim, 28px radius, focus trap, Escape) from the
 * shared primitive; inside it the memory ledger as four paper tiles, the
 * examples as Garamond-italic quotes, and the timeline as the design's paper
 * rows. The payload shape and every French label are unchanged. */

export interface WordBiographySheetProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  open: boolean;
  biography?: VocabularyBiography | null;
  loading?: boolean;
  error?: React.ReactNode;
  onClose: () => void;
  action?: React.ReactNode;
}

function formatThreadDate(value?: string | null) {
  if (!value) return 'Sans date';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Sans date';
  return new Intl.DateTimeFormat('fr-FR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatNumber(value?: number | null) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0';
  return new Intl.NumberFormat().format(value);
}

// The server resolves which gloss this learner reads (app/services/glosses.py)
// and sends it as `translation`. Reading the German column first here was the
// same bug that module exists to kill, so the raw columns are only a fallback
// for a payload that predates the resolution.
function translationFor(biography: VocabularyBiography) {
  return (
    learnerGloss(biography.word) ||
    biography.word.definition ||
    biography.origin.label
  );
}

// `source_type` is a storage key ("anki_deck", "graphic_novel"). It used to be
// printed with its underscores swapped for spaces — a machine key on a
// publication surface. Unknown keys print nothing rather than their internals.
const SOURCE_LABELS: Record<string, string> = {
  anki_deck: 'Paquet importé',
  atelier: 'L’Atelier',
  atelier_attempt: 'L’Épreuve',
  conversation: 'Le Studio',
  deck: 'Paquet',
  errata: 'Errata',
  fsrs: 'Révision',
  graphic_novel: 'Le Feuilleton',
  lexicon: 'Le Lexique',
  mission: 'Missions',
  pilot_capture: 'Capture pilote',
  srs: 'Révision',
};

function eventKicker(event: VocabularyBiographyEvent) {
  return SOURCE_LABELS[event.source_type] || '';
}

function ExampleList({ examples }: { examples: VocabularyBiographyExample[] }) {
  if (!examples.length) return null;
  return (
    <section className="lx-bio__section" aria-label="Exemples">
      <p className="av2-label">Exemples</p>
      <div className="av2-stack">
        {examples.map((example, index) => (
          <Surface key={`${example.source}:${index}:${example.sentence}`} className="lx-bio__example">
            <p className="av2-label">{example.source} · {formatThreadDate(example.occurred_at)}</p>
            <p className="av2-fr lx-bio__quote">« {example.sentence} »</p>
            {example.translation && <p className="av2-body">{example.translation}</p>}
          </Surface>
        ))}
      </div>
    </section>
  );
}

const WordBiographySheet = React.forwardRef<HTMLDivElement, WordBiographySheetProps>(
  ({ open, biography, loading = false, error, onClose, action, className, ...props }, ref) => {
    if (!open) return null;

    const title = biography?.word.word || 'Le fil du mot';
    const description = biography
      ? `${translationFor(biography)} / ${biography.origin.label}`
      : 'Ouverture…';

    return (
      <AtelierV2Root as="div" className={cn('word-biography-layer', className)}>
        <BottomSheet open={open} title={title} eyebrow="L’histoire du mot" onClose={onClose}>
          <div ref={ref} className="word-biography lx-bio" {...props}>
            <div className="lx-bio__lead">
              <p className="av2-body av2-body--lg">{description}</p>
              {biography ? action || <FragilityBadge progress={biography.progress} compact /> : action}
            </div>

            {loading && <StateBlock tone="loading" title="Ouverture de l’histoire…" />}
            {error && <StateBlock tone="error" title="L’histoire est indisponible." body={error} />}

            {biography && (
              <>
                <section className="lx-bio__ledger" aria-label="État de la mémoire">
                  <Surface shape="tile"><span className="av2-label">État</span><strong>{biography.progress.fragility_label}</strong></Surface>
                  <Surface shape="tile"><span className="av2-label">Vu</span><strong>{formatNumber(biography.progress.times_seen)}</strong></Surface>
                  <Surface shape="tile"><span className="av2-label">Employé</span><strong>{formatNumber(biography.progress.times_used_correctly)}</strong></Surface>
                  <Surface shape="tile"><span className="av2-label">Errata</span><strong>{formatNumber(biography.linked_errata_count)}</strong></Surface>
                </section>

                {biography.progress.fragility_reason && (
                  <FragilityBadge progress={biography.progress} showReason />
                )}

                <ExampleList examples={biography.examples} />

                <section className="lx-bio__section" aria-label="Le fil">
                  <p className="av2-label">Le fil</p>
                  <div className="av2-stack lx-bio__thread">
                    {biography.timeline.map((event) => {
                      const kicker = eventKicker(event);
                      return (
                        <Row
                          key={event.id}
                          eyebrow={[kicker, formatThreadDate(event.occurred_at)].filter(Boolean).join(' · ')}
                          title={event.label}
                          badge={event.description ? <span className="av2-body lx-bio__desc">{event.description}</span> : undefined}
                        />
                      );
                    })}
                    {biography.timeline.length === 0 && (
                      <p className="av2-body">Ce mot n’a pas encore laissé de trace.</p>
                    )}
                  </div>
                </section>
              </>
            )}
          </div>
        </BottomSheet>
        <style jsx global>{`
          .av2 .lx-bio { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
          .av2 .lx-bio__lead { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; min-width: 0; }
          .av2 .lx-bio__lead a { color: var(--av2-ink); font-weight: 700; text-underline-offset: 3px; }
          .av2 .lx-bio__ledger { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; min-width: 0; }
          .av2 .lx-bio__ledger strong { display: block; margin-top: 4px; font-size: var(--av2-t-body-lg); font-weight: 700; line-height: 1.2; overflow-wrap: anywhere; }
          .av2 .lx-bio__section { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
          .av2 .lx-bio__example { display: flex; flex-direction: column; gap: 4px; }
          .av2 .lx-bio__quote { margin: 0; font-size: var(--av2-t-action); color: var(--av2-ink); }
          .av2 .lx-bio__desc { flex: 0 1 40%; text-align: right; }
          @media (min-width: 560px) {
            .av2 .lx-bio__ledger { grid-template-columns: repeat(4, minmax(0, 1fr)); }
          }
        `}</style>
      </AtelierV2Root>
    );
  }
);

WordBiographySheet.displayName = 'WordBiographySheet';

export { WordBiographySheet };
