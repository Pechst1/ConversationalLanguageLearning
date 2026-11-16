/**
 * Le Déclic (grammar pilot, owner's choice of 9 November 2026): the feedback lands on the rule.
 *
 * A tapped answer flies into the sentence; a typed one is already there. At the verdict the letters that carry the rule print in
 * the red the rule card teaches. A miss shows what was written with the part at fault struck, then
 * replaces it in place, so the correction is read in its sentence and not in a card below it.
 *
 * Display only: the answer, the check, the verdict and the feel of the moment all stay the page's.
 * Tapping anywhere finishes the motion, and under reduced motion the marks are simply there.
 */

import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import { EASE_OVER, flyWords, PRINT_KEYFRAMES, useScene } from '@/lib/motion';
import { ruleDiff, type DiffWord } from '@/lib/rule-diff';

/** How long the struck answer stands before the correction replaces it. */
const STRUCK_MS = 650;

export type DeclicVerdict = 'right' | 'wrong' | null;

function Words({ words, tone }: { words: DiffWord[]; tone: 'dc-mk' | 'dc-x' }) {
  return (
    <>
      {words.map((word, index) => (
        <React.Fragment key={index}>
          <span className="dc-w">
            {word.segments.map((segment, part) =>
              segment.mark ? (
                <span key={part} className={tone}>{segment.text}</span>
              ) : (
                <React.Fragment key={part}>{segment.text}</React.Fragment>
              ),
            )}
          </span>
          {word.space}
        </React.Fragment>
      ))}
    </>
  );
}

export function DeclicPrompt({
  prompt,
  answer,
  choices,
  target,
  verdict,
  ruleFrom,
}: {
  prompt: string;
  answer?: string;
  choices: string[];
  /** The right answer, once the verdict says it. */
  target?: string | null;
  verdict: DeclicVerdict;
  /**
   * What the corrected line's rule is read against, when that is not the answer and the options: a
   * spot's faulty line, so a slip of the learner's own («xx» for «Hier») is never marked as the rule.
   */
  ruleFrom?: string[];
}) {
  const rootRef = useRef<HTMLSpanElement | null>(null);
  const scene = useScene();
  const [fixed, setFixed] = useState(false);

  const parts = String(prompt || '').split(/_{2,}/);
  const chosen = String(answer || '');
  const right = String(target || '');
  const canFix = verdict === 'wrong' && Boolean(right);
  const struck = canFix && !fixed;

  const words = useMemo(() => {
    const othersThan = (form: string) => choices.filter((choice) => choice !== form);
    if (verdict === 'right') return ruleDiff(chosen, othersThan(chosen));
    if (struck) return ruleDiff(chosen, [right]);
    // What was written counts too: a typed answer is not among the options.
    if (canFix) return ruleDiff(right, ruleFrom ?? [chosen, ...othersThan(right)]);
    return ruleDiff(chosen);
  }, [verdict, struck, canFix, chosen, right, choices, ruleFrom]);

  // One tap anywhere finishes whatever is moving.
  useEffect(() => {
    const skip = () => scene.finish();
    document.addEventListener('pointerdown', skip, true);
    return () => document.removeEventListener('pointerdown', skip, true);
  }, [scene]);

  // The tap: the answer flies from its card to its place in the sentence.
  useLayoutEffect(() => {
    if (verdict || !chosen || !rootRef.current) return;
    const root = rootRef.current;
    const card = root.closest('.ep-recognize')?.querySelector('.av2-choice[data-state="selected"] [lang]');
    scene.resume();
    // The underline joins words that are still in the air, so it waits for them.
    const blank = root.querySelector('.dc-blank');
    blank?.setAttribute('data-flying', 'true');
    void flyWords(scene, card, Array.from(root.querySelectorAll<HTMLElement>('.dc-w'))).then(() => blank?.removeAttribute('data-flying'));
  }, [chosen]); // eslint-disable-line react-hooks/exhaustive-deps

  // The verdict: the marks print. A skip during the struck answer carries over to the correction.
  useLayoutEffect(() => {
    if (!verdict || !rootRef.current) return;
    if (!fixed) scene.resume();
    rootRef.current.querySelectorAll('.dc-mk, .dc-x').forEach((mark, index) => {
      void scene.animate(mark, PRINT_KEYFRAMES, { duration: 280, delay: 40 + index * 70, easing: EASE_OVER });
    });
  }, [verdict, fixed]); // eslint-disable-line react-hooks/exhaustive-deps

  // A miss: the struck answer stands for a moment, then the correction takes its place.
  useEffect(() => {
    setFixed(false);
    if (!canFix) return undefined;
    let live = true;
    void scene.wait(STRUCK_MS).then(() => {
      if (live) setFixed(true);
    });
    return () => {
      live = false;
    };
  }, [canFix, scene]);

  if (parts.length < 2) return <>{prompt}</>;
  return (
    <span ref={rootRef}>
      {parts[0]}
      <span className="ep-blank dc-blank" data-set={chosen ? 'true' : undefined} data-verdict={verdict || undefined}>
        {chosen ? <Words words={words} tone={struck ? 'dc-x' : 'dc-mk'} /> : ' '}
      </span>
      {parts.slice(1).join('___')}
    </span>
  );
}

/**
 * The reason under a miss: what the sentence does not already say. The longer hint opens from
 * «Why?», so the first view stays one short block above the copy step.
 */
export function DeclicWhy({ why, hint, label }: { why: string; hint?: string | null; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="dc-why">
      {why && <span>{why}</span>}
      {hint && open && <span className="dc-why__hint">{hint}</span>}
      {hint && !open && (
        <button type="button" className="dc-why__open" onClick={() => setOpen(true)}>{label}</button>
      )}
    </span>
  );
}
