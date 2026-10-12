/**
 * GENTLE-ONBOARDING — the first day's route, drawn: 1 the story, 2 La Forge,
 * 3 the words (owner, 2026-10-12: «la forge and vocab should also start day
 * one, but as second and third after the story»).
 *
 * Done stages are ticked, the next one carries the one primary action. Shown
 * on the first day after the day's recap, at the end of the forge séance and
 * at the end of the word cards.
 *
 * CONTINUE (owner, 2026-10-12): on Home it is every day's route, with a title
 * of its own; once the three are done its one button keeps the learner going
 * («more»), and the target the learning moves towards is drawn under it.
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
  title,
  more = null,
  target = null,
}: {
  language: string;
  done: readonly RouteStage[];
  /** Where La Forge opens; without one the forge stage has no button. */
  forgeHref: string | null;
  wordsHref?: string;
  onNavigate: (href: string) => void;
  /** The route's heading; the first day's by default. */
  title?: string;
  /** CONTINUE: once the three are done, the one button keeps going. */
  more?: { href: string; label: string; hint: string | null } | null;
  /** CONTINUE: the target the learning moves towards. */
  target?: { goal: string; when: string | null; percent: number } | null;
}) {
  const copy = firstStepsCopy(language).route;
  const next = nextRouteStage(done);
  const hrefFor = (stage: RouteStage) => (stage === 'forge' ? forgeHref : stage === 'words' ? wordsHref : null);
  const nextHref = next ? hrefFor(next) : null;
  const hint: Partial<Record<RouteStage, string>> = { forge: copy.forge_hint, words: copy.words_hint };

  return (
    <section
      className="first-route"
      aria-label={title ?? copy.title}
      lang={language}
      data-first-day-route={next ?? (more ? 'more' : 'done')}
    >
      <p className="av2-label first-route__title">{title ?? copy.title}</p>
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
      ) : !next && more ? (
        <>
          <Action tone="primary" onClick={() => onNavigate(more.href)} iconAfter={<ArrowRightIcon size={18} />}>
            {more.label}
          </Action>
          {more.hint && <p className="first-route__hint first-route__more">{more.hint}</p>}
        </>
      ) : !next ? (
        <p className="first-route__done">{copy.all_done}</p>
      ) : null}
      {target && (
        <div className="first-route__target" data-target="">
          <span className="first-route__bar" aria-hidden="true">
            <span style={{ width: `${Math.max(2, target.percent)}%` }} />
          </span>
          <p className="first-route__goal">{target.goal}</p>
          {target.when && <p className="first-route__hint">{target.when}</p>}
        </div>
      )}
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
        .first-route__more,
        .first-route__goal {
          margin: 0;
        }
        .first-route__goal {
          font-weight: 700;
        }
        .first-route__target {
          display: flex;
          flex-direction: column;
          gap: 4px;
          padding-top: 12px;
          border-top: 1px solid var(--av2-line);
        }
        .first-route__target p {
          margin: 0;
        }
        .first-route__bar {
          display: block;
          height: 6px;
          border-radius: 3px;
          background: var(--av2-line);
          overflow: hidden;
        }
        .first-route__bar > span {
          display: block;
          height: 100%;
          border-radius: 3px;
          background: var(--av2-blue);
        }
      `}</style>
    </section>
  );
}

export default FirstDayRoute;
