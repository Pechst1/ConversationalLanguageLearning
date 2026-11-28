/**
 * «Le bilan» — one week, top to bottom. Presentation only: `pages/bilan.tsx` loads the
 * week (or a fixture in the gallery) and hands it here.
 *
 *   Semaine du 16–22 novembre                       the kicker
 *   Quatre jours dans l'histoire cette semaine.     the one Garamond headline
 *   [saucers] 4   L ■ M ■ M □ J ■ V □ S ■ D □        the days, with the streak's mark
 *   Ce que tu sais dire maintenant                  the corrected sentences, each playable
 *   Mots · Règles · L'histoire                      only the sections with something true
 *   Retour à l'histoire                             the one 3D-press action
 *   ← Semaine précédente        Semaine suivante →  quiet links
 *
 * Calm and typographic: one headline, hairlines between sections, the av2 tokens only
 * (styles/bilan.css). The sentences are played with the line voice the reader uses
 * (`useLineVoice`): a recap line has no server clip, so it is the device's French voice.
 */

import React from 'react';
import Link from 'next/link';

import { useLineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { StreakSaucers } from '@/components/atelier-v2/home/StreakSaucers';
import { Action, ArrowLeftIcon, ArrowRightIcon } from '@/components/atelier-v2/ui';
import { bilanHref } from '@/lib/bilan-api';
import type { Bilan } from '@/lib/bilan-types';

import { fill, type BilanCopy } from './bilan-copy';
import {
  bilanHeadline,
  bilanKicker,
  bilanSections,
  ruleMove,
  storyRows,
  weekdayInitial,
  weekdayName,
  wordLines,
} from './bilan-model';

export type BilanViewProps = {
  bilan: Bilan;
  copy: BilanCopy;
  /** The one primary action: back to the day's story. */
  onContinue: () => void;
  /** Where the week links go; the gallery passes a no-op. */
  hrefFor?: (weekStart: string) => string;
};

/** French spacing that never breaks: «Lila ?» keeps its «?» on the same line. */
function fr(text: string): string {
  return text.replace(/\s+([?!:;»])/g, '\u00a0$1').replace(/«\s+/g, '«\u00a0');
}

function quoted(text: string): string {
  return fr(`« ${text.replace(/^[«"“\s]+|[»"”\s]+$/g, '')} »`);
}

export function BilanDays({ bilan, copy }: { bilan: Bilan; copy: BilanCopy }) {
  return (
    <section className="bl-days" aria-label={fill(copy.days_aria, { n: bilan.daysPlayed })}>
      {bilan.daysPlayed > 0 && (
        <span className="bl-days__pile" aria-hidden="true">
          <StreakSaucers streak={bilan.daysPlayed} />
          <span className="bl-days__n">{bilan.daysPlayed}</span>
        </span>
      )}
      <ol className="bl-week">
        {bilan.days.map((day) => (
          <li
            key={day.date}
            className="bl-week__day"
            data-played={day.played ? '' : undefined}
            data-future={day.future ? '' : undefined}
            title={weekdayName(day.date, bilan.language)}
          >
            <span className="bl-week__mark" aria-hidden="true" />
            <span className="bl-week__initial" aria-hidden="true">
              {weekdayInitial(day.date, bilan.language)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function BilanLines({ bilan, copy }: { bilan: Bilan; copy: BilanCopy }) {
  const voice = useLineVoice();
  return (
    <section className="bl-sec" aria-labelledby="bl-lines">
      <h2 id="bl-lines" className="bl-sec__title">
        {copy.lines_title}
      </h2>
      <p className="av2-body bl-sec__note">{copy.lines_note}</p>
      <ul className="bl-lines">
        {bilan.lines.map((line, index) => {
          const key = `bilan-${bilan.weekStart}-${index}`;
          const speaking = voice.speakingKey === key;
          return (
            <li key={key} className="bl-line">
              <p className="av2-fr bl-line__fr" lang="fr">
                {fr(line.textFr)}
              </p>
              {voice.supported && (
                <button
                  type="button"
                  className="bl-listen"
                  aria-pressed={speaking}
                  aria-label={`${speaking ? copy.listen_stop : copy.listen} : ${line.textFr}`}
                  onClick={() => (speaking ? voice.stop() : voice.speak({ key, text_fr: line.textFr }))}
                >
                  <span className="bl-listen__play" aria-hidden="true" data-speaking={speaking ? '' : undefined} />
                  <span>{speaking ? copy.listen_stop : copy.listen}</span>
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function BilanView({ bilan, copy, onContinue, hrefFor = bilanHref }: BilanViewProps) {
  const head = bilanHeadline(bilan, copy);
  const sections = bilanSections(bilan);
  const words = wordLines(bilan, copy);
  const story = storyRows(bilan);
  return (
    <article className="bl" data-tone={bilan.daysPlayed > 1 ? 'full' : bilan.daysPlayed === 1 ? 'thin' : 'empty'}>
      <header className="bl-head">
        <p className="av2-label bl-head__kicker">{bilanKicker(bilan, copy)}</p>
        <h1 className="av2-headline av2-headline--screen bl-head__title">{head.title}</h1>
        {head.body && <p className="av2-body av2-body--lg bl-head__body">{head.body}</p>}
      </header>

      <BilanDays bilan={bilan} copy={copy} />

      {sections.lines && <BilanLines bilan={bilan} copy={copy} />}

      {sections.words && (
        <section className="bl-sec" aria-labelledby="bl-words">
          <h2 id="bl-words" className="bl-sec__title">
            {copy.words_title}
          </h2>
          {words.map((line) => (
            <p key={line} className="av2-body av2-body--lg bl-sec__line">
              {line}
            </p>
          ))}
          {bilan.words.shown.length > 0 && (
            <ul className="bl-words">
              {bilan.words.shown.map((word) => (
                <li key={word.word} className="bl-word">
                  <span className="av2-fr bl-word__fr" lang="fr">
                    {word.word}
                  </span>
                  <span className="bl-word__gloss">{word.gloss}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {sections.rules && (
        <section className="bl-sec" aria-labelledby="bl-rules">
          <h2 id="bl-rules" className="bl-sec__title">
            {copy.rules_title}
          </h2>
          <ul className="bl-rules">
            {bilan.rules.map((rule) => (
              <li key={rule.conceptId} className="bl-rule" data-stage={rule.stage}>
                <span className="bl-rule__title">{rule.title}</span>
                <span className="bl-rule__move">{ruleMove(rule, copy)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {sections.story && (
        <section className="bl-sec" aria-labelledby="bl-story">
          <h2 id="bl-story" className="bl-sec__title">
            {copy.story_title}
          </h2>
          {bilan.story.episodes.length > 0 && (
            <div className="bl-story__group">
              <p className="av2-label">{copy.episodes_label}</p>
              <ul className="bl-story__list">
                {story.episodes.map(({ episode, choices }) => (
                  <li key={`${episode.date}-${episode.titleFr}`} className="bl-story__episode">
                    <span className="av2-fr bl-story__item" lang="fr">
                      {fr(episode.titleFr)}
                    </span>
                    {choices.length > 0 && (
                      <span className="bl-story__choices" lang="fr">
                        {choices.map((choice) => quoted(choice.labelFr)).join(' · ')}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {story.rest.length > 0 && (
            <div className="bl-story__group">
              <p className="av2-label">{copy.decisions_label}</p>
              <ul className="bl-story__list">
                {story.rest.map((decision) => (
                  <li key={`${decision.date}-${decision.labelFr}`} className="av2-fr bl-story__item" lang="fr">
                    {decision.kind === 'choice' ? quoted(decision.labelFr) : fr(decision.labelFr)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {bilan.story.nextFr && (
            <div className="bl-story__group bl-story__next">
              <p className="av2-label av2-label--story">{copy.next_label}</p>
              <p className="av2-fr bl-story__item" lang="fr">
                {fr(bilan.story.nextFr)}
              </p>
            </div>
          )}
        </section>
      )}

      <div className="bl-foot">
        <Action tone="primary" onClick={onContinue} iconAfter={<ArrowRightIcon size={18} />}>
          {copy.cta}
        </Action>
        {(bilan.previousWeekStart || bilan.nextWeekStart) && (
          <nav className="bl-nav" aria-label={copy.page_title}>
            {bilan.previousWeekStart ? (
              <Link className="bl-nav__link" href={hrefFor(bilan.previousWeekStart)}>
                <ArrowLeftIcon size={16} />
                <span>{copy.previous_week}</span>
              </Link>
            ) : (
              <span />
            )}
            {bilan.nextWeekStart ? (
              <Link className="bl-nav__link bl-nav__link--next" href={hrefFor(bilan.nextWeekStart)}>
                <span>{copy.next_week}</span>
                <ArrowRightIcon size={16} />
              </Link>
            ) : (
              <span />
            )}
          </nav>
        )}
      </div>
    </article>
  );
}

export default BilanView;
