/**
 * WP-79 + WP-D4 — the end of the day, as a reward. One screen:
 *
 *   the Seal pressing (a *completed* day only; an early stop never shows one)
 *   and the one headline → three facts (Scène · Mots «+N» · Série «N jours»)
 *   → the words → the character's face and how the day left them → a level
 *   move, when the estimate moved → «La suite demain» → «Ranger le sceau»
 *   («Continuer» after an early stop), quiet «Plus de pratique».
 *
 * Calm on purpose: no confetti, no mascot — the cast's face is the reward. The
 * one motion is the Seal's press (`av2-seal-press`), which Reduce Motion
 * removes. The day-complete haptic and sound
 * are `useJourneyFeel`'s «complete» moment, felt once on the transition that
 * opens this screen.
 *
 * Deleted with this package (appendix A): «La durée n'est pas encore
 * mesurée» and «Optional. It does not reopen today's scene.». An unmeasured
 * duration now reads as the steps the learner did.
 */

import React from 'react';

import { Action, Surface } from '@/components/atelier-v2/ui';
import { Seal } from '@/components/ui/Seal';
import { PRACTICE_LABEL } from '@/lib/atelier-next';
import { CastPortrait } from '@/components/onboarding/Portrait';
import type { ControlLanguage, JourneyRecap as JourneyRecapPayload, JourneySnapshot } from '@/types/daily-journey';

import { journeyCopy } from './journey-copy';
import { keepsakeDate, rewardView } from './journey-recap-model';
import { RECAP_CHROME } from './recap-copy';

export type JourneyRecapProps = {
  journey: JourneySnapshot;
  recap: JourneyRecapPayload | null;
  language: ControlLanguage;
  onExit?: () => void;
  morePractice?: { label: string; onSelect: () => void } | null;
  /** WP-16 / D-0: open the drill loop at a server-issued practice href. */
  onPractice?: (href: string) => void;
  /** WP-80's push pre-prompt, mounted by the session shell. */
  pushOptIn?: React.ReactNode;
};

export function JourneyRecap({
  journey,
  recap,
  language,
  onExit,
  morePractice,
  onPractice,
  pushOptIn,
}: JourneyRecapProps) {
  const copy = journeyCopy(language);
  const view = rewardView(journey, recap, language);
  const partial = view?.partial ?? journey.status === 'ended_early';
  const keepsake = view?.keepsake ?? null;
  const date = keepsakeDate(keepsake?.local_date);
  const seal = partial ? null : view?.seal ?? null;

  // «Plus de pratique» opens the drill loop on what today practised when the
  // server named a place for it; otherwise the general entry.
  const practice =
    onPractice && view?.practiceHref
      ? {
          onSelect: () => onPractice(view.practiceHref as string),
          ariaLabel: `${copy.practice_this} — ${view.practiceLabelFr ?? ''}`.trim(),
        }
      : morePractice
        ? { onSelect: morePractice.onSelect, ariaLabel: morePractice.label || copy.more_practice }
        : null;

  return (
    <section
      className="journey-recap av2-reward av2-stack"
      data-state={partial ? 'partial' : 'complete'}
      aria-label={partial ? copy.finished_partial_title : copy.finished_title}
    >
      <Surface tone={partial ? 'outline' : 'paper'} shape="hero" className="av2-recap__header">
        {seal && (
          <figure
            className="av2-recap__seal"
            data-edition={seal.no ?? undefined}
            data-keepsake={keepsake?.collectible_id}
          >
            <Seal stamp size="lg" variant={seal.variant} no={seal.no} date={seal.date ?? ''} />
            {keepsake && (
              <figcaption className="av2-reward__caption">
                <span className="av2-fr av2-reward__title" lang="fr">
                  {keepsake.title_fr}
                </span>
                <span className="av2-label">
                  {[keepsake.location_name, date].filter(Boolean).join(' · ')}
                </span>
              </figcaption>
            )}
          </figure>
        )}
        <h2 className="av2-headline">{partial ? copy.finished_partial_title : copy.finished_title}</h2>
        {partial && <p className="av2-body av2-body--lg">{copy.finished_partial_body}</p>}
      </Surface>

      {view && view.facts.length > 0 && (
        <dl className="av2-reward__facts">
          {view.facts.map((fact) => (
            <div key={fact.id} className="av2-reward__fact" data-fact={fact.id}>
              <dt className="av2-label">{fact.label}</dt>
              <dd className="av2-reward__value">{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {view?.freezeNote && <p className="av2-label">{view.freezeNote}</p>}

      {view && view.words.length > 0 && (
        <ul className="av2-reward__words" aria-label={RECAP_CHROME.words_label}>
          {view.words.map((word) => (
            <li key={word.id} className="av2-reward__word">
              <span className="av2-fr" lang="fr">
                {word.label_fr}
              </span>
              {word.label_native && <span className="av2-reward__gloss"> · {word.label_native}</span>}
            </li>
          ))}
        </ul>
      )}

      {view?.face && (
        <Surface className="av2-reward__face">
          <CastPortrait
            characterId={view.face.characterId}
            name={view.face.name}
            mood={view.face.expression}
            size="md"
          />
          <div className="av2-reward__face-body">
            <p className="av2-label">
              {view.face.moodLine ? (
                <span data-mood={view.face.moodDirection ?? undefined}>
                  {view.face.moodLine}{' '}
                  <span aria-hidden="true">{view.face.moodDirection === 'down' ? '↓' : '↑'}</span>
                </span>
              ) : (
                view.face.name
              )}
            </p>
            {view.face.lineFr && (
              <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
                {view.face.lineFr}
              </p>
            )}
          </div>
        </Surface>
      )}

      {view?.levelUp && (
        <Surface tone="blue" className="av2-reward__level">
          <p className="av2-label">{RECAP_CHROME.level_label}</p>
          <p className="av2-headline av2-headline--rule">
            {view.levelUp.from_level} → {view.levelUp.to_level}
          </p>
          {view.levelUp.evidence && <p className="av2-body">{view.levelUp.evidence}</p>}
        </Surface>
      )}

      {view?.teaser && (
        <div className="av2-reward__teaser" data-source={view.teaser.source}>
          <p className="av2-label">{RECAP_CHROME.teaser_label}</p>
          <p className="av2-fr av2-reward__teaser-line" lang="fr">
            « {view.teaser.text_fr} »
            {view.teaser.character_name && (
              <span className="av2-reward__teaser-by"> — {view.teaser.character_name}</span>
            )}
          </p>
        </div>
      )}

      {pushOptIn}

      <div className="av2-recap__actions">
        {onExit && (
          <Action tone="primary" onClick={onExit}>
            {seal ? RECAP_CHROME.keep_seal : copy.continue}
          </Action>
        )}
        {practice && (
          <Action tone="quiet" onClick={practice.onSelect} aria-label={practice.ariaLabel}>
            {morePractice?.label || PRACTICE_LABEL}
          </Action>
        )}
      </div>
    </section>
  );
}

export default JourneyRecap;
