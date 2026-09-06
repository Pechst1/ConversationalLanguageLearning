import React from 'react';
import type { VocabularyBiography, VocabularyBiographyEvent, VocabularyBiographyExample } from '@/services/api';
import { cn } from '@/lib/utils';
import { learnerGloss } from '@/lib/glosses';
import { ContextAnchor } from './ContextAnchor';
import { FragilityBadge } from './FragilityBadge';
import { MobileBottomSheet } from './MobileBottomSheet';
import { MobileRow } from './MobileRow';

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
    <section className="word-biography-section">
      <h3>Exemples</h3>
      <div className="word-biography-examples">
        {examples.map((example, index) => (
          <ContextAnchor
            key={`${example.source}:${index}:${example.sentence}`}
            compact
            quote
            tone={index === 0 ? 'blue' : 'green'}
            label={example.source}
            text={example.sentence}
            translation={example.translation}
            meta={formatThreadDate(example.occurred_at)}
          />
        ))}
      </div>
      <style jsx>{`
        .word-biography-section {
          display: grid;
          gap: 10px;
        }
        .word-biography-section h3 {
          margin: 0;
          color: var(--bio-ink-3);
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .word-biography-examples {
          display: grid;
          gap: 10px;
        }
      `}</style>
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
      <MobileBottomSheet
        ariaLabel="L’histoire du mot"
        eyebrow="L’histoire du mot"
        title={title}
        description={description}
        onClose={onClose}
        action={biography ? action || <FragilityBadge progress={biography.progress} compact /> : action}
        className={cn('word-biography-layer', className)}
        bodyClassName="word-biography-body-shell"
      >
        <div ref={ref} className="word-biography" {...props}>
          {loading && <p className="word-biography-empty">Ouverture de l’histoire…</p>}
          {error && <div className="word-biography-error">{error}</div>}
          {biography && (
            <>
              <section className="word-biography-ledger" aria-label="État de la mémoire">
                <div>
                  <span>État</span>
                  <strong>{biography.progress.fragility_label}</strong>
                </div>
                <div>
                  <span>Vu</span>
                  <strong>{formatNumber(biography.progress.times_seen)}</strong>
                </div>
                <div>
                  <span>Employé</span>
                  <strong>{formatNumber(biography.progress.times_used_correctly)}</strong>
                </div>
                <div>
                  <span>Errata</span>
                  <strong>{formatNumber(biography.linked_errata_count)}</strong>
                </div>
              </section>

              {biography.progress.fragility_reason && (
                <FragilityBadge progress={biography.progress} showReason />
              )}

              <ExampleList examples={biography.examples} />

              <section className="word-biography-section">
                <h3>Le fil</h3>
                <div className="word-biography-thread">
                  {biography.timeline.map((event) => (
                    <MobileRow
                      key={event.id}
                      kicker={eventKicker(event)}
                      meta={formatThreadDate(event.occurred_at)}
                      title={event.label}
                      description={event.description}
                    />
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
        <style jsx>{`
          :global(.word-biography-body-shell) {
            padding-top: 16px;
          }
          .word-biography {
            --bio-paper: var(--app-paper, var(--paper, #f1ece1));
            --bio-sheet: var(--app-sheet, var(--paper-2, #f8f3e8));
            --bio-ink: var(--app-ink, var(--ink, #14110d));
            --bio-ink-2: var(--app-ink-2, var(--ink-2, #4a4538));
            --bio-ink-3: var(--app-ink-3, var(--ink-3, #8a826f));
            display: grid;
            gap: 16px;
            color: var(--bio-ink);
          }
          .word-biography-ledger {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            border: 1px solid var(--bio-ink);
            background: var(--bio-sheet);
          }
          .word-biography-ledger div {
            min-width: 0;
            border-right: 1px solid var(--bio-ink);
            border-bottom: 1px solid var(--bio-ink);
            padding: 10px 11px;
          }
          .word-biography-ledger div:nth-child(2n) {
            border-right: 0;
          }
          .word-biography-ledger div:nth-last-child(-n + 2) {
            border-bottom: 0;
          }
          .word-biography-ledger span {
            display: block;
            color: var(--bio-ink-3);
            font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
            letter-spacing: .1em;
            text-transform: uppercase;
          }
          .word-biography-ledger strong {
            display: block;
            margin-top: 5px;
            overflow-wrap: anywhere;
            color: var(--bio-ink);
            font-size: 16px;
            line-height: 1.15;
          }
          .word-biography-section {
            display: grid;
            gap: 10px;
          }
          .word-biography-section h3 {
            margin: 0;
            color: var(--bio-ink-3);
            font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
            letter-spacing: .12em;
            text-transform: uppercase;
          }
          .word-biography-thread {
            overflow: hidden;
            border: 1px solid var(--bio-ink);
            background: var(--bio-sheet);
          }
          .word-biography-empty,
          .word-biography-error {
            margin: 0;
            border: 1px solid var(--bio-ink);
            background: var(--bio-sheet);
            padding: 12px;
            color: var(--bio-ink-2);
            font-size: 13px;
            line-height: 1.35;
          }
          .word-biography-error {
            border-left: 4px solid var(--app-red, var(--red, #d8321a));
          }
          @media (min-width: 560px) {
            .word-biography-ledger {
              grid-template-columns: repeat(4, minmax(0, 1fr));
            }
            .word-biography-ledger div {
              border-bottom: 0;
            }
            .word-biography-ledger div:nth-child(2n) {
              border-right: 1px solid var(--bio-ink);
            }
            .word-biography-ledger div:last-child {
              border-right: 0;
            }
          }
        `}</style>
      </MobileBottomSheet>
    );
  }
);

WordBiographySheet.displayName = 'WordBiographySheet';

export { WordBiographySheet };
