/**
 * WP-120 §5.3 · a pin's card: what happened there, in French first.
 *
 * The av2 bottom sheet: the vignette large, the week and the place, the headline,
 * the plate as a band, the learner's part with their own words marked (underline +
 * «toi», never colour alone), the question kept, the kept words as tokens (a tap
 * opens the word's help), and two actions: «Relire» (the one red press) and «Dans
 * le Relevé».
 *
 * WP-121: with due words the card's first row is «3 mots t'attendent ici» and the one
 * red press moves to «Réviser ici» («Relire» becomes secondary). A Papier six weeks
 * old with a kept question offers «Relire ta question»; once re-read, «Relue le …»
 * opens the pair again.
 */

import React from 'react';

import { Action, BottomSheet } from '@/components/atelier-v2/ui';
import { RvVignette } from '@/components/revue/RvVignette';
import type { CartePin } from '@/lib/carte-types';

import type { CarteCopy } from './carte-copy';
import { markSpans, weekNo } from './carte-model';
import { relectureAction } from './palais-model';

export type CartePinCardProps = {
  pin: CartePin | null;
  copy: CarteCopy;
  onClose: () => void;
  onRelire: (pin: CartePin) => void;
  onReleve: (pin: CartePin) => void;
  onReview?: (pin: CartePin) => void;
  onRelecture?: (pin: CartePin) => void;
  onWord?: (word: string, pin: CartePin) => void;
};

export function CartePinCard({ pin, copy, onClose, onRelire, onReleve, onReview, onRelecture, onWord }: CartePinCardProps) {
  if (!pin) return null;
  const due = onReview && pin.dueWords > 0 ? pin.dueWords : 0;
  const relecture = onRelecture ? relectureAction(pin) : null;
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
        {due > 0 && onReview && (
          <section className="carte-card__due" data-due={due}>
            <p className="carte-card__due-line">
              <i className="carte-due-dot carte-due-dot--inline" aria-hidden="true" />
              <span>{copy.due_waiting(due)}</span>
            </p>
            <Action tone="primary" onClick={() => onReview(pin)}>
              {copy.review_here}
            </Action>
          </section>
        )}
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
        {relecture && onRelecture && (
          <section className="carte-card__part carte-card__relecture" data-relecture={relecture.kind}>
            <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={() => onRelecture(pin)}>
              <span>
                {relecture.kind === 'open'
                  ? relecture.headline
                    ? copy.relecture_open_headline
                    : copy.relecture_open_question
                  : copy.relecture_read(relecture.at ? copy.date_short(relecture.at) : '')}
              </span>
            </button>
          </section>
        )}
        <div className="carte-card__actions">
          <Action tone={due > 0 ? 'secondary' : 'primary'} onClick={() => onRelire(pin)}>
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
