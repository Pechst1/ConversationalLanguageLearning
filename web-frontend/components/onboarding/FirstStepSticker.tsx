/**
 * GENTLE-ONBOARDING — the «sticker»: the first time a kind of step appears, one
 * small yellow note pinned above it says what this step is and what to do.
 *
 * Distinct on purpose (owner, 2026-10-12: «in a distinct manner»): a slightly
 * tilted yellow card with the step's own shape, a «Zum ersten Mal» kicker and
 * one «Verstanden». It never covers the step and never blocks it: the step
 * below works whether the note is read or not. Once dismissed it is remembered
 * for that kind on this device (`lib/first-steps.ts`).
 */

import React from 'react';

import { ShapeToken } from '@/components/atelier-v2/ui';
import {
  FIRST_STEP_SHAPE,
  deviceStore,
  firstStepsCopy,
  rememberSticker,
  stickerSeen,
  type FirstStepKey,
} from '@/lib/first-steps';

/** Whether `key` still has its sticker to show; `false` until device memory is read. */
export function useFirstStepSticker(key: FirstStepKey | null): [boolean, () => void] {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    setOpen(key ? !stickerSeen(deviceStore(), key) : false);
  }, [key]);
  const dismiss = React.useCallback(() => {
    if (key) rememberSticker(deviceStore(), key);
    setOpen(false);
  }, [key]);
  return [open, dismiss];
}

export function FirstStepSticker({
  stepKey,
  language,
}: {
  stepKey: FirstStepKey | null;
  language: string;
}) {
  const [open, dismiss] = useFirstStepSticker(stepKey);
  if (!stepKey || !open) return null;
  const copy = firstStepsCopy(language);
  const text = copy.stickers[stepKey];
  return (
    <aside className="first-sticker" data-first-step={stepKey} aria-label={`${copy.kicker}: ${text.title}`} lang={language}>
      <p className="first-sticker__kicker">
        <ShapeToken kind={FIRST_STEP_SHAPE[stepKey]} size="sm" />
        <span>{copy.kicker}</span>
      </p>
      <p className="first-sticker__title">{text.title}</p>
      <p className="first-sticker__body">{text.body}</p>
      <button type="button" className="first-sticker__ok" onClick={dismiss}>
        {copy.got_it}
      </button>
      <style jsx>{`
        .first-sticker {
          position: relative;
          margin: 4px 2px 18px;
          padding: 14px 16px 12px;
          background: var(--av2-yellow);
          color: var(--av2-on-yellow);
          border-radius: 6px;
          box-shadow: 0 6px 0 -2px var(--av2-yellow-deep);
          transform: rotate(-0.8deg);
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .first-sticker::before {
          /* the strip of tape that pins it */
          content: '';
          position: absolute;
          top: -8px;
          left: 50%;
          width: 56px;
          height: 16px;
          transform: translateX(-50%) rotate(2deg);
          background: var(--av2-card);
          opacity: 0.75;
          border-radius: 2px;
        }
        .first-sticker p {
          margin: 0;
        }
        .first-sticker__kicker {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: var(--av2-t-label);
          font-weight: 800;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }
        .first-sticker__title {
          font-family: var(--av2-serif);
          font-style: italic;
          font-size: 22px;
          line-height: 1.15;
        }
        .first-sticker__body {
          font-size: var(--av2-t-body);
          line-height: 1.45;
        }
        .first-sticker__ok {
          align-self: flex-end;
          min-height: var(--av2-tap);
          padding: 0 14px;
          border: 0;
          border-radius: var(--av2-r-pill);
          background: var(--av2-ink);
          color: var(--av2-on-ink);
          font-weight: 700;
          cursor: pointer;
        }
        .first-sticker__ok:focus-visible {
          outline: 2px solid var(--av2-focus);
          outline-offset: 2px;
        }
        @media (prefers-reduced-motion: reduce) {
          .first-sticker {
            transform: none;
          }
        }
      `}</style>
    </aside>
  );
}

export default FirstStepSticker;
