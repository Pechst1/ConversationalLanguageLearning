/* WP-103 — La Forge's answers say what to do and what happened.

   - ForgeGoalLine (T3): the goal a Forge item states under its prompt, or the
     scene line it is cut from.
   - ForgeReading (T9): «Je relis…» — the grading character's face while the
     model reads a free-production answer. A wait, never a verdict; after a
     while it offers to move on, so it is never a wall.
   - ForgeFollowUp (T8): after «À corriger», «Corrigez la phrase» — the wrong
     sentence quoted, a field (or tiles at A1), «Passer» to see the right one.
   - ForgeCorrectedLine (T8): «La bonne phrase», when the server sent the
     corrected sentence but no follow-up.

   Presentation only. What is right, what is pending and what the follow-up
   accepts live in `lib/forge-verdict.ts` and `lib/forge-followup.ts`. Every
   colour is an --av2-* token; the primary of the screen stays the footer's. */

import React from 'react';

import { PendingIcon } from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import type { DrillGoal } from '@/components/atelier-v2/journey/drill-frame';
import { frenchSpacing } from '@/lib/french-typography';
import {
  followUpOutcome,
  type ForgeFollowUp as FollowUpSpec,
  type FollowUpOutcome,
} from '@/lib/forge-followup';
import type { PortraitMood } from '@/lib/onboarding-portraits';

import { EpBar, EpSetLine, EpSlug, useEpCopy } from './Epreuve';

/* ---------- T3 · the goal line ---------- */

export function ForgeGoalLine({ goal }: { goal: DrillGoal | null }) {
  const t = useEpCopy();
  if (!goal) return null;
  if (goal.kind === 'goal') {
    return (
      <p className="av2-goal ep-goal" data-goal="goal">
        {goal.text}
      </p>
    );
  }
  return (
    <div className="av2-goal ep-goal" data-goal="source">
      <p className="av2-label">{t.from_scene}</p>
      <p className="av2-fr av2-goal__fr" lang="fr">
        {frenchSpacing(goal.text)}
      </p>
    </div>
  );
}

/* ---------- T9 · «Je relis…» ---------- */

/** After this long the wait offers a way on: a wait is never a wall. */
export const READING_PATIENCE_MS = 30000;

export function ForgeReading({
  coach,
  mood = 'neutral',
  onSkip,
  patienceMs = READING_PATIENCE_MS,
}: {
  coach?: { id: string; name: string } | null;
  mood?: PortraitMood;
  onSkip?: () => void;
  patienceMs?: number;
}) {
  const t = useEpCopy();
  const [tired, setTired] = React.useState(false);
  React.useEffect(() => {
    const timer = window.setTimeout(() => setTired(true), patienceMs);
    return () => window.clearTimeout(timer);
  }, [patienceMs]);
  return (
    <div className="ep-feedback" data-verdict="checking" role="status" aria-live="polite">
      <div className="ep-reading">
        <span className="ep-reading__face">
          {coach ? (
            <CastPortrait characterId={coach.id} name={coach.name} mood={mood} size="sm" ring />
          ) : (
            <span className="av2-feedback__icon" aria-hidden="true">
              <PendingIcon size={15} />
            </span>
          )}
        </span>
        <p className="ep-reading__line">{t.reading}</p>
      </div>
      {tired && onSkip && (
        <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline ep-reading__skip" onClick={onSkip}>
          {t.skip_unscored}
        </button>
      )}
    </div>
  );
}

/* ---------- T8 · the follow-up ---------- */

export type FollowUpDraft = {
  text: string;
  /** Tiles: the indices placed, in order. */
  placed: number[];
  outcome: FollowUpOutcome | null;
  skipped: boolean;
};

export const FOLLOW_UP_EMPTY: FollowUpDraft = { text: '', placed: [], outcome: null, skipped: false };

/** What the learner has put together so far: the typed text, or the tiles in order. */
export function followUpAnswer(followUp: FollowUpSpec, draft: FollowUpDraft): string | string[] {
  return followUp.options ? draft.placed.map((index) => followUp.options?.[index] ?? '') : draft.text;
}

export function followUpReady(followUp: FollowUpSpec, draft: FollowUpDraft): boolean {
  return followUp.options ? draft.placed.length > 0 : draft.text.trim().length > 0;
}

export function ForgeFollowUp({
  followUp,
  draft,
  onDraft,
}: {
  followUp: FollowUpSpec;
  draft: FollowUpDraft;
  onDraft: (next: FollowUpDraft) => void;
}) {
  const t = useEpCopy();
  const settled = draft.outcome !== null;
  const ready = followUpReady(followUp, draft);
  const check = () => {
    if (!ready || settled) return;
    onDraft({ ...draft, outcome: followUpOutcome(followUpAnswer(followUp, draft), followUp), skipped: false });
  };
  const skip = () => {
    if (settled) return;
    onDraft({ ...draft, outcome: 'revealed', skipped: true });
  };
  const options = followUp.options;
  const label =
    draft.outcome === 'right' ? t.follow_right : draft.skipped ? t.corrected_sentence : t.follow_not_quite;

  return (
    <section className="ep-follow" data-outcome={draft.outcome ?? 'open'} aria-label={t.follow_title}>
      <p className="av2-label ep-follow__title">{t.follow_title}</p>
      {followUp.goalNative && <p className="av2-body ep-follow__goal">{followUp.goalNative}</p>}
      <blockquote className="ep-follow__quote" lang="fr">
        <span className="av2-sr">{t.follow_wrong_label}: </span>
        {frenchSpacing(followUp.sourceFr)}
      </blockquote>

      {!settled && options && (
        <>
          <EpSetLine empty={draft.placed.length === 0}>
            {draft.placed.map((index, position) => (
              <EpSlug
                key={`${index}-${position}`}
                set
                onClick={() => onDraft({ ...draft, placed: draft.placed.filter((_, at) => at !== position) })}
              >
                {options[index]}
              </EpSlug>
            ))}
          </EpSetLine>
          <div className="ep-typecase" aria-label={t.typecase_label}>
            {options.map((token, index) => {
              const used = draft.placed.includes(index);
              return (
                <EpSlug
                  key={`${token}-${index}`}
                  spent={used}
                  disabled={used}
                  onClick={() => onDraft({ ...draft, placed: [...draft.placed, index] })}
                >
                  {token}
                </EpSlug>
              );
            })}
          </div>
        </>
      )}

      {!settled && !options && (
        <label className="av2-field">
          <span className="av2-sr">{t.follow_title}</span>
          <textarea
            className="ep-composed-input ep-follow__input"
            lang="fr"
            rows={2}
            value={draft.text}
            placeholder={t.follow_placeholder}
            autoCapitalize="sentences"
            autoCorrect="off"
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => onDraft({ ...draft, text: event.target.value })}
          />
        </label>
      )}

      {!settled && (
        <div className="ep-follow__actions">
          <EpBar tone="ghost" disabled={!ready} onClick={check}>
            {t.check}
          </EpBar>
          <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline ep-follow__skip" onClick={skip}>
            {t.follow_skip}
          </button>
        </div>
      )}

      {settled && (
        <div className="ep-follow__answer" role="status" aria-live="polite">
          <p className="av2-label">{label}</p>
          {(followUp.correctedFr || followUp.accepted[0]) && (
            <p className="av2-fr ep-follow__fixed" lang="fr">
              {frenchSpacing(followUp.correctedFr || followUp.accepted[0])}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

/* ---------- T8 · «La bonne phrase» without a follow-up ---------- */

export function ForgeCorrectedLine({ fr }: { fr: string | null | undefined }) {
  const t = useEpCopy();
  const line = String(fr ?? '').trim();
  if (!line) return null;
  return (
    <div className="ep-follow ep-follow--line" data-outcome="revealed">
      <div className="ep-follow__answer">
        <p className="av2-label">{t.corrected_sentence}</p>
        <p className="av2-fr ep-follow__fixed" lang="fr">
          {frenchSpacing(line)}
        </p>
      </div>
    </div>
  );
}
