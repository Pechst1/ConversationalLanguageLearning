/**
 * WP-75 — the sixty-second taste, before any account.
 *
 * Romy greets the learner at Le Mistral; the learner answers with one tap,
 * then orders a coffee from tiles. Graded on the device the instant the answer
 * is complete: the option turns green or red, Romy's face changes, the phone
 * ticks. No network, no model, no waiting screen. It ends on Romy's reply and
 * «Gardez votre histoire», which is the sign-up.
 */

import React from 'react';

import { Action, ChoiceList, FeedbackBand, WordTiles, type ChoiceOption } from '@/components/atelier-v2/ui';
import { pulseAppHaptic } from '@/lib/haptics';
import type { OnboardingLanguage } from '@/lib/onboarding-locale';
import {
  TASTE_COPY,
  TASTE_ITEMS,
  TASTE_NAV,
  gradeChoice,
  gradeTiles,
  rememberTasteDone,
  type TasteChoiceItem,
  type TasteCopy,
  type TasteLine,
  type TasteTilesItem,
  type TasteVerdict,
} from '@/lib/onboarding-taste';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { moodForVerdict } from '@/lib/cast-faces';

/** One French line with tap-to-translate. */
export function SpokenLine({
  line,
  language,
  copy,
}: {
  line: TasteLine;
  language: OnboardingLanguage;
  copy: TasteCopy;
}) {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => setOpen(false), [line.fr]);
  const translation = line.native[language];
  const translatable = translation && translation !== line.fr;

  return (
    <div className="ob-line">
      <button
        type="button"
        className="ob-line__fr av2-fr"
        lang="fr"
        aria-expanded={translatable ? open : undefined}
        aria-label={translatable ? `${line.fr} · ${open ? copy.hide_translation : copy.translate}` : undefined}
        onClick={() => translatable && setOpen((value) => !value)}
      >
        « {line.fr} »
      </button>
      {translatable && (
        <p className="ob-line__native av2-label" lang={language} aria-live="polite">
          {open ? translation : copy.translate}
        </p>
      )}
      <style jsx>{`
        .ob-line {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }
        .ob-line__fr {
          padding: 0;
          border: 0;
          background: none;
          text-align: left;
          font-size: var(--av2-t-title);
          line-height: 1.2;
          color: var(--av2-ink);
          cursor: pointer;
          text-decoration: underline dotted var(--av2-line);
          text-underline-offset: 5px;
        }
        .ob-line__native {
          margin: 0;
          color: var(--av2-muted);
          font-weight: 400;
        }
      `}</style>
    </div>
  );
}

function feel(verdict: TasteVerdict) {
  if (verdict === 'correct') pulseAppHaptic('correct');
  else if (verdict === 'wrong') pulseAppHaptic('repair');
}

function ChoiceTask({
  item,
  copy,
  onVerdict,
}: {
  item: TasteChoiceItem;
  copy: TasteCopy;
  onVerdict: (verdict: TasteVerdict) => void;
}) {
  const [selected, setSelected] = React.useState<string | null>(null);
  const [wrongIds, setWrongIds] = React.useState<string[]>([]);
  const verdict = gradeChoice(item, selected);

  const options: ChoiceOption[] = item.options.map((option) => ({
    id: option.id,
    textFr: option.fr,
    state:
      option.id === selected && verdict === 'correct'
        ? 'correct'
        : wrongIds.includes(option.id)
          ? 'wrong'
          : 'idle',
  }));

  return (
    <ChoiceList
      options={options}
      selectedId={selected}
      label={copy.options_label}
      disabled={verdict === 'correct'}
      statusLabels={copy.status}
      onSelect={(id) => {
        if (verdict === 'correct') return;
        const next = gradeChoice(item, id);
        setSelected(id);
        if (next === 'wrong') setWrongIds((ids) => (ids.includes(id) ? ids : [...ids, id]));
        feel(next);
        onVerdict(next);
      }}
    />
  );
}

function TilesTask({
  item,
  copy,
  verdict,
  onVerdict,
  resetKey,
}: {
  item: TasteTilesItem;
  copy: TasteCopy;
  verdict: TasteVerdict;
  onVerdict: (verdict: TasteVerdict) => void;
  resetKey: number;
}) {
  const [placed, setPlaced] = React.useState<string[]>([]);
  React.useEffect(() => setPlaced([]), [resetKey]);

  const options: ChoiceOption[] = item.tiles.map((tile) => ({ id: tile.id, textFr: tile.fr }));

  return (
    <div className="ob-tiles" data-verdict={verdict}>
      <WordTiles
        options={options}
        placed={placed}
        label={copy.options_label}
        emptyHint={copy.tiles_hint}
        removeLabel={copy.remove_tile}
        disabled={verdict !== 'pending'}
        onPlace={(id) => {
          const next = [...placed, id];
          setPlaced(next);
          const graded = gradeTiles(item, next);
          if (graded !== 'pending') {
            feel(graded);
            onVerdict(graded);
          } else {
            pulseAppHaptic('selection');
          }
        }}
        onRemoveLast={() => setPlaced((ids) => ids.slice(0, -1))}
      />
      <style jsx>{`
        .ob-tiles[data-verdict='correct'] :global(.av2-tiles__line) {
          color: var(--av2-green);
          border-color: var(--av2-green);
        }
        .ob-tiles[data-verdict='wrong'] :global(.av2-tiles__line) {
          color: var(--av2-red);
          border-color: var(--av2-red);
          animation: ob-shake 0.28s ease-in-out;
        }
        @keyframes ob-shake {
          0%,
          100% {
            transform: translateX(0);
          }
          25% {
            transform: translateX(-4px);
          }
          75% {
            transform: translateX(4px);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .ob-tiles[data-verdict='wrong'] :global(.av2-tiles__line) {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}

export function Taste({ language, onKeep }: { language: OnboardingLanguage; onKeep: () => void }) {
  const copy = TASTE_COPY[language];
  const [index, setIndex] = React.useState(0);
  const [verdict, setVerdict] = React.useState<TasteVerdict>('pending');
  const [resetKey, setResetKey] = React.useState(0);

  const item = TASTE_ITEMS[index];
  const last = index === TASTE_ITEMS.length - 1;
  const solved = verdict === 'correct';
  const finished = solved && last;
  const line = solved ? item.reply : item.line;
  const mood = moodForVerdict(verdict);

  React.useEffect(() => {
    if (finished) rememberTasteDone();
  }, [finished]);

  const next = () => {
    setIndex((value) => Math.min(value + 1, TASTE_ITEMS.length - 1));
    setVerdict('pending');
    setResetKey((value) => value + 1);
  };

  return (
    <section className="ob-taste" aria-label="Le Mistral">
      <div className="ob-taste__who">
        <CastPortrait characterId={line.characterId} name={line.speaker} mood={mood} size="lg" />
        <span className="av2-label">{line.speaker} · Le Mistral</span>
      </div>

      <SpokenLine line={line} language={language} copy={copy} />

      {!finished && (
        <p className="av2-body av2-body--lg ob-taste__task" lang={language}>
          {item.task[language]}
        </p>
      )}

      {!finished && item.kind === 'choice' && (
        <ChoiceTask key={item.id} item={item} copy={copy} onVerdict={setVerdict} />
      )}
      {!finished && item.kind === 'tiles' && (
        <TilesTask
          key={item.id}
          item={item}
          copy={copy}
          verdict={verdict}
          onVerdict={setVerdict}
          resetKey={resetKey}
        />
      )}

      {verdict === 'wrong' && (
        <FeedbackBand tone="wrong" title={copy.wrong}>
          {item.kind === 'tiles' && (
            <Action
              tone="secondary"
              inline
              onClick={() => {
                setVerdict('pending');
                setResetKey((value) => value + 1);
              }}
            >
              {TASTE_NAV.retry}
            </Action>
          )}
        </FeedbackBand>
      )}
      {solved && !finished && <FeedbackBand tone="correct" title={copy.correct} />}

      {finished && (
        <p className="av2-body av2-body--lg" lang={language}>
          {copy.closing}
        </p>
      )}

      <div className="ob-taste__foot">
        {solved && !last && (
          <Action tone="primary" onClick={next}>
            {TASTE_NAV.next}
          </Action>
        )}
        {finished && (
          <Action tone="primary" onClick={onKeep}>
            {TASTE_NAV.keep}
          </Action>
        )}
      </div>

      <style jsx>{`
        .ob-taste {
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          gap: 16px;
          min-width: 0;
        }
        .ob-taste__who {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 10px;
        }
        .ob-taste__task {
          margin: 0;
          color: var(--av2-muted);
        }
        .ob-taste__foot {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin-top: auto;
        }
      `}</style>
    </section>
  );
}

export default Taste;
