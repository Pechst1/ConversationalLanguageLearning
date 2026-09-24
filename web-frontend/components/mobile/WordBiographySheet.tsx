import React from 'react';
import type { VocabularyBiography, VocabularyBiographyEvent, VocabularyBiographyExample } from '@/services/api';
import { cn } from '@/lib/utils';
import { learnerGloss } from '@/lib/glosses';
import { AtelierV2Root, BottomSheet, Row, StateBlock, Surface, WordToken } from '@/components/atelier-v2/ui';
import { cahierCopy, type CahierCopy } from '@/components/cahiers/cahier-copy';
import { useChromeLanguage } from '@/lib/learner-language';
import { FragilityBadge, fragilityLabel } from './FragilityBadge';

/* The word biography, on the Claude design system (Atelier V2).
 *
 * One bottom sheet (handle, scrim, 28px radius, focus trap, Escape) from the
 * shared primitive; inside it the memory ledger as four paper tiles, the
 * examples as Garamond-italic quotes, and the timeline as the design's paper
 * rows. The payload shape is unchanged.
 *
 * WP-82: the sheet's own words (ledger tiles, section heads, states, source
 * kickers) are chrome, in the learner's chrome language from the Cahier copy
 * table; the word, the examples and the timeline's labels are content. Place
 * names (L’Atelier, Le Feuilleton, Le Lexique, Le Courrier…) stay French. */

type BiographyCopy = CahierCopy['biography'];

export interface WordBiographySheetProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  open: boolean;
  biography?: VocabularyBiography | null;
  loading?: boolean;
  error?: React.ReactNode;
  onClose: () => void;
  action?: React.ReactNode;
}

function formatThreadDate(value: string | null | undefined, t: BiographyCopy, locale: string) {
  if (!value) return t.no_date;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t.no_date;
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatNumber(value: number | null | undefined, locale: string) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0';
  return new Intl.NumberFormat(locale).format(value);
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
// Place names are French in every language; the rest is read from the table.
const PLACE_LABELS: Record<string, string> = {
  atelier: 'L’Atelier',
  atelier_attempt: 'L’Épreuve',
  conversation: 'Le Studio',
  graphic_novel: 'Le Feuilleton',
  lexicon: 'Le Lexique',
  mission: 'Le Courrier',
};
const SOURCE_KEYS: Record<string, keyof BiographyCopy> = {
  anki_deck: 'source_anki_deck',
  deck: 'source_deck',
  errata: 'source_errata',
  fsrs: 'source_review',
  pilot_capture: 'source_pilot_capture',
  srs: 'source_review',
};

function eventKicker(event: VocabularyBiographyEvent, t: BiographyCopy) {
  const key = SOURCE_KEYS[event.source_type];
  return PLACE_LABELS[event.source_type] || (key ? t[key] : '');
}

function ExampleList({ examples, t, locale }: { examples: VocabularyBiographyExample[]; t: BiographyCopy; locale: string }) {
  if (!examples.length) return null;
  return (
    <section className="lx-bio__section" aria-label={t.examples}>
      <p className="av2-label">{t.examples}</p>
      <div className="av2-stack">
        {examples.map((example, index) => (
          <Surface key={`${example.source}:${index}:${example.sentence}`} className="lx-bio__example">
            <p className="av2-label">{example.source} · {formatThreadDate(example.occurred_at, t, locale)}</p>
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
    const language = useChromeLanguage();
    if (!open) return null;

    const copy = cahierCopy(language);
    const t = copy.biography;
    const locale = copy.cahier.locale;
    const title = biography?.word.word || t.title_fallback;
    const description = biography
      ? `${translationFor(biography)} / ${biography.origin.label}`
      : t.opening;

    return (
      <AtelierV2Root as="div" language={language} className={cn('word-biography-layer', className)}>
        <BottomSheet open={open} title={title} eyebrow={t.eyebrow} onClose={onClose}>
          <div ref={ref} className="word-biography lx-bio" {...props}>
            <div className="lx-bio__lead">
              <span className="lx-bio__word">
                {/* WP-D6: the gender as the shape, the article inside. */}
                {biography && (
                  <WordToken
                    word={biography.word.word}
                    gender={biography.word.gender}
                    partOfSpeech={biography.word.part_of_speech}
                    state={biography.progress.fragility_level}
                    size="lg"
                  />
                )}
                <p className="av2-body av2-body--lg">{description}</p>
              </span>
              {biography ? action || <FragilityBadge progress={biography.progress} compact /> : action}
            </div>

            {loading && <StateBlock tone="loading" title={t.loading} />}
            {error && <StateBlock tone="error" title={t.failed} body={error} />}

            {biography && (
              <>
                <section className="lx-bio__ledger" aria-label={t.ledger_label}>
                  <Surface shape="tile"><span className="av2-label">{t.tile_state}</span><strong>{fragilityLabel(biography.progress, new Date(), language).label}</strong></Surface>
                  <Surface shape="tile"><span className="av2-label">{t.tile_seen}</span><strong>{formatNumber(biography.progress.times_seen, locale)}</strong></Surface>
                  <Surface shape="tile"><span className="av2-label">{t.tile_used}</span><strong>{formatNumber(biography.progress.times_used_correctly, locale)}</strong></Surface>
                  <Surface shape="tile"><span className="av2-label">{t.tile_errata}</span><strong>{formatNumber(biography.linked_errata_count, locale)}</strong></Surface>
                </section>

                {biography.progress.fragility_reason && (
                  <FragilityBadge progress={biography.progress} showReason />
                )}

                <ExampleList examples={biography.examples} t={t} locale={locale} />

                <section className="lx-bio__section" aria-label={t.thread}>
                  <p className="av2-label">{t.thread}</p>
                  <div className="av2-stack lx-bio__thread">
                    {biography.timeline.map((event) => {
                      const kicker = eventKicker(event, t);
                      return (
                        <Row
                          key={event.id}
                          eyebrow={[kicker, formatThreadDate(event.occurred_at, t, locale)].filter(Boolean).join(' · ')}
                          title={event.label}
                          badge={event.description ? <span className="av2-body lx-bio__desc">{event.description}</span> : undefined}
                        />
                      );
                    })}
                    {biography.timeline.length === 0 && (
                      <p className="av2-body">{t.no_trace}</p>
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
          .av2 .lx-bio__word { display: flex; align-items: center; gap: 12px; min-width: 0; }
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
