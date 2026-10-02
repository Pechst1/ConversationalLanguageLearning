/**
 * WP-120 §5.3 · a pin's card: what happened there, in French first.
 *
 * The av2 bottom sheet: the vignette large, the week and the place, the headline,
 * the plate as a band, the learner's part with their own words marked (underline +
 * «toi», never colour alone), the question kept, the kept words as tokens (a tap
 * opens the word's help), and two actions: «Relire» (the one red press) and «Dans
 * le Relevé».
 */

import React from 'react';

import { Action, BottomSheet } from '@/components/atelier-v2/ui';
import { RvVignette } from '@/components/revue/RvVignette';
import type { CartePin } from '@/lib/carte-types';

import type { CarteCopy } from './carte-copy';
import { markSpans, weekNo } from './carte-model';

export type CartePinCardProps = {
  pin: CartePin | null;
  copy: CarteCopy;
  onClose: () => void;
  onRelire: (pin: CartePin) => void;
  onReleve: (pin: CartePin) => void;
  onWord?: (word: string, pin: CartePin) => void;
};

export function CartePinCard({ pin, copy, onClose, onRelire, onReleve, onWord }: CartePinCardProps) {
  if (!pin) return null;
  const week = weekNo(pin.week);
  const contribution = pin.contributionFr
    ? markSpans(pin.contributionFr, pin.contributionSpans)
    : [];
  const contributionLabel = pin.contributionKind ? copy.contribution[pin.contributionKind] : null;
  const showQuestion = pin.questionFr && pin.questionFr !== pin.contributionFr;

  return (
    <BottomSheet
      open
      onClose={onClose}
      title={pin.headlineFr}
      // With a vignette, the stamp itself prints the week and the place beneath it.
      eyebrow={<span lang="fr">{pin.vignette ? copy.week_fr(week) : [copy.week_fr(week), pin.placeLabelFr].filter(Boolean).join(' · ')}</span>}
    >
      <div className="carte-card" data-session={pin.sessionId}>
        {pin.vignette && (
          <div className="carte-card__stamp">
            <RvVignette
              week={pin.week}
              placeLabelFr={pin.placeLabelFr}
              ring={pin.vignette.ring}
              keptContribution={pin.vignette.keptContribution}
              pictogramSvg={pin.vignette.pictogramSvg}
              size="large"
            />
          </div>
        )}
        {pin.plateUrl && (
          <div className="carte-card__plate" aria-hidden="true">
            {/* eslint-disable-next-line @next/next/no-img-element -- a static plate, already sized */}
              <img src={pin.plateUrl} alt="" loading="lazy" decoding="async" />
          </div>
        )}
        {contribution.length > 0 && (
          <section className="carte-card__part" aria-label={contributionLabel ?? undefined}>
            {contributionLabel && <p className="av2-label">{contributionLabel}</p>}
            <p className="carte-card__made" lang="fr">
              {contribution.map((segment, index) =>
                segment.yours ? (
                  <span key={index} className="carte-yours">
                    {segment.text}
                    <sup>{copy.yours}</sup>
                  </span>
                ) : (
                  <React.Fragment key={index}>{segment.text}</React.Fragment>
                ),
              )}
            </p>
          </section>
        )}
        {showQuestion && (
          <section className="carte-card__part">
            <p className="av2-label">{copy.question_kept}</p>
            <p className="carte-card__made" lang="fr">
              {pin.questionFr}
            </p>
          </section>
        )}
        {pin.keptWords.length > 0 && (
          <section className="carte-card__part">
            <p className="av2-label">{copy.kept_words}</p>
            <ul className="carte-card__words" lang="fr">
              {pin.keptWords.map((word) => (
                <li key={word}>
                  {onWord ? (
                    <button type="button" className="av2-chip carte-word" onClick={() => onWord(word, pin)}>
                      <span>{word}</span>
                    </button>
                  ) : (
                    <span className="av2-chip carte-word">
                      <span>{word}</span>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
        <div className="carte-card__actions">
          <Action tone="primary" onClick={() => onRelire(pin)}>
            {copy.relire}
          </Action>
          <Action tone="secondary" onClick={() => onReleve(pin)}>
            {copy.releve}
          </Action>
        </div>
      </div>
    </BottomSheet>
  );
}

export default CartePinCard;
