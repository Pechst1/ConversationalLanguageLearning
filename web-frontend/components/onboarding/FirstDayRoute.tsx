/**
 * GENTLE-ONBOARDING — the first day's route, drawn: 1 the story, 2 La Forge,
 * 3 the words (owner, 2026-10-12: «la forge and vocab should also start day
 * one, but as second and third after the story»).
 *
 * Done stages are ticked, the next one carries the one primary action. Shown
 * on the first day only: after the day's recap, on Home, at the end of the
 * forge séance and at the end of the word cards.
 */

import React from 'react';

import { Action, ArrowRightIcon, CheckIcon } from '@/components/atelier-v2/ui';
import { firstStepsCopy, nextRouteStage, ROUTE_STAGES, type RouteStage } from '@/lib/first-steps';

export const FIRST_DAY_WORDS_HREF = '/vocabulary/review';

export function FirstDayRoute({
  language,
  done,
  forgeHref,
  wordsHref = FIRST_DAY_WORDS_HREF,
  onNavigate,
}: {
  language: string;
  done: readonly RouteStage[];
  /** Where La Forge opens; without one the forge stage has no button. */
  forgeHref: string | null;
  wordsHref?: string;
  onNavigate: (href: string) => void;
}) {
  const copy = firstStepsCopy(language).route;
  const next = nextRouteStage(done);
  const hrefFor = (stage: RouteStage) => (stage === 'forge' ? forgeHref : stage === 'words' ? wordsHref : null);
  const nextHref = next ? hrefFor(next) : null;
  const hint: Partial<Record<RouteStage, string>> = { forge: copy.forge_hint, words: copy.words_hint };

  return (
    <section className="first-route" aria-label={copy.title} lang={language} data-first-day-route={next ?? 'done'}>
      <p className="av2-label first-route__title">{copy.title}</p>
      <ol className="first-route__list">
        {ROUTE_STAGES.map((stage, position) => {
          const isDone = done.includes(stage);
          return (
            <li key={stage} data-state={isDone ? 'done' : stage === next ? 'next' : 'todo'}>
              <span className="first-route__num" aria-hidden="true">
                {isDone ? <CheckIcon size={14} /> : position + 1}
              </span>
              <span className="first-route__text">
                <span className="first-route__name">{copy[stage]}</span>
                {hint[stage] && !isDone && <span className="first-route__hint">{hint[stage]}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {next && nextHref ? (
        <Action tone="primary" onClick={() => onNavigate(nextHref)} iconAfter={<ArrowRightIcon size={18} />}>
          {next === 'forge' ? copy.next_forge : copy.next_words}
        </Action>
      ) : !next ? (
        <p className="first-route__done">{copy.all_done}</p>
      ) : null}
      <style jsx>{`
        .first-route {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 16px;
          border-radius: var(--av2-r-card);
          background: var(--av2-card);
          min-width: 0;
        }
        .first-route__title,
        .first-route__done {
          margin: 0;
        }
        .first-route__list {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin: 0;
          padding: 0;
          list-style: none;
        }
        .first-route__list li {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .first-route__num {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex: none;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: var(--av2-line);
          color: var(--av2-ink);
          font-weight: 800;
        }
        li[data-state='next'] .first-route__num {
          background: var(--av2-ink);
          color: var(--av2-on-ink);
        }
        li[data-state='done'] .first-route__num {
          background: var(--av2-green);
          color: var(--av2-on-green);
        }
        .first-route__text {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }
        .first-route__name {
          font-weight: 700;
        }
        li[data-state='done'] .first-route__name {
          color: var(--av2-muted);
        }
        .first-route__hint {
          font-size: var(--av2-t-meta);
          color: var(--av2-muted);
        }
      `}</style>
    </section>
  );
}

export default FirstDayRoute;
