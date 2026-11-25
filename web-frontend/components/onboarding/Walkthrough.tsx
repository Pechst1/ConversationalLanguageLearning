/**
 * GENTLE-ONBOARDING — the walkthrough: two cards before the very first scene.
 *
 *   1. what the Atelier is (a story you play, a day at a time);
 *   2. what the first day holds: the story, then La Forge, then the words.
 *
 * P9 (walk of 17 Nov): «Les quatre formes» and «Où tu en es» went. Four cards
 * of chrome before any story was a tour, and the shapes and the progress row
 * explain themselves on the day (the stickers name each step the first time).
 *
 * The situation and the characters follow on the next screen (`CastIntro`),
 * so they are not repeated here. Shown once per device; «Überspringen» counts
 * as seen.
 *
 * #143: the day on the second card is the plan's (`dayProgramme`: Szene,
 * Grammatik, 15 Wörter, Fertig), the list Home shows and the session header
 * counts. The device route («Die Geschichte, La Forge, Deine Wörter») listed
 * three steps under a header that read «Schritt 1 von 4». It stands only when no
 * plan came (an older server).
 */

import React from 'react';

import { Action, ArrowRightIcon, AtelierMark } from '@/components/atelier-v2/ui';
import { normalizeControlLanguage } from '@/lib/atelier-v2-copy';
import { dayProgramme } from '@/lib/day-plan';
import { firstStepsCopy, ROUTE_STAGES } from '@/lib/first-steps';
import type { DaySession } from '@/types/daily-journey';

export function Walkthrough({
  language,
  plan,
  onDone,
}: {
  language: string;
  /** The day's plan (`TodayEnvelope.session`); its steps are the day this card lists. */
  plan?: DaySession | null;
  onDone: () => void;
}) {
  const copy = firstStepsCopy(language).walkthrough;
  const route = firstStepsCopy(language).route;
  const day = dayProgramme(plan, normalizeControlLanguage(language)) ?? ROUTE_STAGES.map((stage) => route[stage]);
  const [index, setIndex] = React.useState(0);
  const cards = 2;
  const last = index === cards - 1;

  return (
    <section className="walkthrough" aria-label={copy.aria} lang={language} data-walkthrough={index + 1}>
      <ol className="walkthrough__dots" aria-hidden="true">
        {Array.from({ length: cards }, (_, dot) => (
          <li key={dot} data-on={dot <= index ? '' : undefined} />
        ))}
      </ol>

      {index === 0 && (
        <div className="walkthrough__card">
          <AtelierMark size={56} />
          <h2 className="av2-headline av2-headline--title">{copy.welcome_title}</h2>
          <p className="walkthrough__body">{copy.welcome_body}</p>
        </div>
      )}

      {index === 1 && (
        <div className="walkthrough__card">
          <h2 className="av2-headline av2-headline--title">{copy.day_title}</h2>
          <ol className="walkthrough__route">
            {day.map((label, position) => (
              <li key={position}>
                <span className="walkthrough__num">{position + 1}</span>
                <span>{label}</span>
              </li>
            ))}
          </ol>
          <p className="walkthrough__body">{copy.day_body}</p>
        </div>
      )}

      <div className="walkthrough__actions">
        <Action
          tone="primary"
          onClick={() => (last ? onDone() : setIndex((value) => value + 1))}
          iconAfter={<ArrowRightIcon size={18} />}
        >
          {last ? copy.start : copy.next}
        </Action>
        {!last && (
          <Action tone="quiet" inline onClick={onDone}>
            {copy.skip}
          </Action>
        )}
      </div>

      <style jsx>{`
        .walkthrough {
          display: flex;
          flex-direction: column;
          gap: 22px;
          min-width: 0;
        }
        .walkthrough__dots {
          display: flex;
          gap: 6px;
          margin: 0;
          padding: 0;
          list-style: none;
        }
        .walkthrough__dots li {
          flex: 1;
          height: 4px;
          border-radius: 2px;
          background: var(--av2-line);
        }
        .walkthrough__dots li[data-on] {
          background: var(--av2-blue);
        }
        .walkthrough__card {
          display: flex;
          flex-direction: column;
          gap: 14px;
          min-width: 0;
        }
        .walkthrough__card h2,
        .walkthrough__body {
          margin: 0;
        }
        .walkthrough__body {
          font-size: var(--av2-t-body-lg);
          line-height: 1.5;
        }
        .walkthrough__route {
          display: flex;
          flex-direction: column;
          gap: 14px;
          margin: 0;
          padding: 0;
          list-style: none;
        }
        .walkthrough__route li {
          display: flex;
          align-items: center;
          gap: 14px;
          line-height: 1.4;
        }
        .walkthrough__num {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 30px;
          height: 30px;
          flex: none;
          border-radius: 50%;
          background: var(--av2-ink);
          color: var(--av2-on-ink);
          font-weight: 800;
        }
        .walkthrough__actions {
          display: flex;
          flex-direction: column;
          align-items: stretch;
          gap: 8px;
        }
      `}</style>
    </section>
  );
}

export default Walkthrough;
