/**
 * GENTLE-ONBOARDING — the walkthrough: four cards before the very first scene.
 *
 *   1. what the Atelier is (a story you play, a day at a time);
 *   2. the four shapes and what each stands for;
 *   3. how to read the progress row and the mark at the top;
 *   4. what the first day holds: the story, then the words, then La Forge.
 *
 * The situation and the characters follow on the next screen (`CastIntro`),
 * so they are not repeated here. Shown once per device; «Überspringen» counts
 * as seen.
 */

import React from 'react';

import { Action, ArrowRightIcon, AtelierMark, ShapeToken } from '@/components/atelier-v2/ui';
import { firstStepsCopy, ROUTE_STAGES } from '@/lib/first-steps';

const SHAPE_ORDER = ['story', 'reward', 'action', 'done'] as const;

export function Walkthrough({ language, onDone }: { language: string; onDone: () => void }) {
  const copy = firstStepsCopy(language).walkthrough;
  const route = firstStepsCopy(language).route;
  const [index, setIndex] = React.useState(0);
  const cards = 4;
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
          <h2 className="av2-headline av2-headline--title">{copy.shapes_title}</h2>
          <p className="walkthrough__body">{copy.shapes_body}</p>
          <ul className="walkthrough__list">
            {SHAPE_ORDER.map((shape) => (
              <li key={shape}>
                <ShapeToken kind={shape} size="lg" />
                <span>{copy.shapes[shape]}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {index === 2 && (
        <div className="walkthrough__card">
          <h2 className="av2-headline av2-headline--title">{copy.progress_title}</h2>
          <p className="walkthrough__body">{copy.progress_body}</p>
          <div className="walkthrough__sample" aria-hidden="true">
            <span className="walkthrough__sample-row">
              <ShapeToken kind="story" size="sm" />
              <ShapeToken kind="reward" size="sm" />
              <span className="walkthrough__eyes">
                <ShapeToken kind="action" size="sm" />
              </span>
              <span className="walkthrough__ghost" />
              <span className="walkthrough__ghost" />
            </span>
            <AtelierMark size={32} progress={{ scene: 'done', recall: 'done', respond: 'active', resolution: 'todo' }} />
          </div>
          <ul className="walkthrough__points">
            {copy.progress_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </div>
      )}

      {index === 3 && (
        <div className="walkthrough__card">
          <h2 className="av2-headline av2-headline--title">{copy.day_title}</h2>
          <ol className="walkthrough__route">
            {ROUTE_STAGES.map((stage, position) => (
              <li key={stage}>
                <span className="walkthrough__num">{position + 1}</span>
                <span>{route[stage]}</span>
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
        .walkthrough__list,
        .walkthrough__points,
        .walkthrough__route {
          display: flex;
          flex-direction: column;
          gap: 14px;
          margin: 0;
          padding: 0;
          list-style: none;
        }
        .walkthrough__list li,
        .walkthrough__route li {
          display: flex;
          align-items: center;
          gap: 14px;
          line-height: 1.4;
        }
        .walkthrough__points li {
          padding-left: 14px;
          border-left: 3px solid var(--av2-line);
          line-height: 1.45;
        }
        .walkthrough__sample {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 14px;
          border-radius: var(--av2-r-card);
          background: var(--av2-card);
        }
        .walkthrough__sample-row {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .walkthrough__eyes {
          display: inline-flex;
          padding: 3px;
          border-radius: 4px;
          outline: 2px solid var(--av2-ink);
        }
        .walkthrough__ghost {
          width: 12px;
          height: 12px;
          border-radius: 2px;
          background: var(--av2-line);
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
