/**
 * Motion for the grammar pilot: the Web Animations API on transform and opacity only, with no
 * library. A scene owns everything it starts, so one tap can finish it all and one unmount can
 * cancel it all. av2's global reduced-motion rule covers CSS animations only, so a script-driven
 * animation asks here first.
 */

import { useEffect, useRef } from 'react';

export const EASE_SOFT = 'cubic-bezier(.22,.9,.3,1)';
export const EASE_OVER = 'cubic-bezier(.3,1.35,.5,1)';

/** Reduced motion, or a place with no way to animate (the server, an old web view). */
export function motionIsStill(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return true;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export type Scene = {
  /** Resolves when the animation ends, is finished or is cancelled; at once when there is none. */
  animate: (element: Element | null | undefined, keyframes: Keyframe[], options?: KeyframeAnimationOptions) => Promise<void>;
  /** A hold, kept under reduced motion so a line can still be read. A finish ends it. */
  wait: (ms: number) => Promise<void>;
  /** The skip: everything running jumps to its end, and later steps run instantly until `resume`. */
  finish: () => void;
  /** The next stretch plays normally again. */
  resume: () => void;
  /** Cancels everything; nothing starts afterwards, until a `revive`. */
  dispose: () => void;
  /** The same scene in use again. */
  revive: () => void;
};

export function createScene(isStill: () => boolean = motionIsStill): Scene {
  const running = new Set<Animation>();
  const holds = new Set<() => void>();
  let fast = false;
  let disposed = false;
  const endHolds = () => {
    Array.from(holds).forEach((end) => end());
  };
  return {
    animate(element, keyframes, options = {}) {
      if (fast || disposed || isStill() || !element || typeof (element as any).animate !== 'function') return Promise.resolve();
      const animation = element.animate(keyframes, { duration: 240, easing: EASE_SOFT, fill: 'backwards', ...options });
      running.add(animation);
      const done = () => {
        running.delete(animation);
      };
      return animation.finished.then(done, done);
    },
    wait(ms) {
      if (fast || disposed || ms <= 0) return Promise.resolve();
      return new Promise((resolve) => {
        const end = () => {
          clearTimeout(timer);
          holds.delete(end);
          resolve();
        };
        const timer = setTimeout(end, ms);
        holds.add(end);
      });
    },
    finish() {
      fast = true;
      Array.from(running).forEach((animation) => {
        try {
          animation.finish();
        } catch {
          animation.cancel();
        }
      });
      endHolds();
    },
    resume() {
      fast = false;
    },
    dispose() {
      disposed = true;
      Array.from(running).forEach((animation) => animation.cancel());
      endHolds();
    },
    revive() {
      disposed = false;
      fast = false;
    },
  };
}

/**
 * A component's scene, ended when it leaves. React's strict mode unmounts and remounts once in
 * development with the same ref, so a scene that stayed disposed would never move or hold again.
 */
export function useScene(): Scene {
  const ref = useRef<Scene | null>(null);
  if (!ref.current) ref.current = createScene();
  const scene = ref.current;
  useEffect(() => {
    scene.revive();
    return () => scene.dispose();
  }, [scene]);
  return scene;
}

/**
 * Each word flies from where it is written on `from` to its own place in the sentence, so a
 * multi-word answer can cross a line break. The words stay hidden until they land. Copies live
 * on the body, fixed to the screen, and are gone when the flight is. Nothing moves if there is no
 * motion, or if the scene is skipping.
 */
export function flyWords(
  scene: Scene,
  from: Element | null | undefined,
  words: HTMLElement[],
  { center = false, isStill = motionIsStill }: { center?: boolean; isStill?: () => boolean } = {},
): Promise<void> {
  if (isStill() || !from || !words.length || typeof document === 'undefined') return Promise.resolve();
  const start = from.getBoundingClientRect();
  const sourceSize = parseFloat(getComputedStyle(from).fontSize) || 20;
  const rects = words.map((word) => word.getBoundingClientRect());
  const style = getComputedStyle(words[0]);
  const scale = sourceSize / (parseFloat(style.fontSize) || sourceSize);
  const gap = (parseFloat(style.fontSize) || 20) * 0.24 * scale;
  const total = rects.reduce((sum, rect) => sum + rect.width * scale + gap, -gap);
  let x = center ? start.left + (start.width - total) / 2 : start.left;
  const y = start.top + (start.height - rects[0].height * scale) / 2;
  return Promise.all(
    words.map((word, index) => {
      const rect = rects[index];
      const copy = document.createElement('span');
      copy.textContent = word.textContent;
      copy.setAttribute('aria-hidden', 'true');
      Object.assign(copy.style, {
        position: 'fixed',
        left: '0',
        top: '0',
        zIndex: '60',
        margin: '0',
        whiteSpace: 'nowrap',
        pointerEvents: 'none',
        transformOrigin: 'left top',
        // One by one: a computed `font` shorthand can come back empty, which would drop the serif.
        fontFamily: style.fontFamily,
        fontStyle: style.fontStyle,
        fontWeight: style.fontWeight,
        fontSize: style.fontSize,
        lineHeight: style.lineHeight,
        letterSpacing: style.letterSpacing,
        color: style.color,
      });
      document.body.append(copy);
      const origin = `translate(${x}px,${y}px) scale(${scale})`;
      x += rect.width * scale + gap;
      word.style.visibility = 'hidden';
      return scene
        .animate(
          copy,
          [{ transform: origin }, { transform: `translate(${rect.left}px,${rect.top}px) scale(1)` }],
          { duration: 260, delay: index * 26, easing: EASE_OVER, fill: 'both' },
        )
        .then(() => {
          copy.remove();
          word.style.visibility = '';
        });
    }),
  ).then(() => undefined);
}

/** The small drop a mark lands with. */
export const PRINT_KEYFRAMES: Keyframe[] = [
  { opacity: 0, transform: 'translateY(-0.42em) scale(1.3)' },
  { opacity: 1, transform: 'none' },
];
