/**
 * WP-116 · one drawn cast member.
 *
 *   <CastRig id="romy_tremblay" mood="ravie" crop="head" size={64} />
 *
 * The rig blinks on its own and idles (a bob, a bounce, a sway or a nod) unless it
 * is `still`, the learner has asked for reduced motion, or the parent drives
 * `blink` itself. All motion is CSS (`styles/cast-rig.css`), never SMIL, so
 * reduced motion and `still` stop it. `mouth` is for lip-sync: the parent sets the
 * viseme from the audio's playback position.
 */
import React, { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { rigFor } from './cast-registry';
import { rigValues } from './rig-kit';
import type { HeldMouth, Outfit, RigCrop, RigMood, Viseme } from './rig-kit';

export interface CastRigProps {
  id: string;
  mood?: RigMood;
  mouth?: Viseme | HeldMouth | 'auto';
  /** Controlled blink. Leave undefined to let the rig blink by itself. */
  blink?: boolean;
  crop?: RigCrop;
  /** Rendered width in px; the height follows the crop. */
  size?: number;
  hold?: string;
  variant?: string;
  /**
   * WP-119 · what the figure wears (Toi only). A rig that does not list the outfit
   * in `RigDef.outfits` draws as if it were absent.
   */
  outfit?: Outfit;
  /** No idle and no blinking: the learner is reading or typing. */
  still?: boolean;
  /** Accessible name; defaults to the character's name. Empty string hides it. */
  label?: string;
  className?: string;
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** A blink every 2.8–5.6 s, 130 ms long, unless switched off. */
export function useAutoBlink(enabled: boolean): boolean {
  const [shut, setShut] = useState(false);
  useEffect(() => {
    if (!enabled || prefersReducedMotion()) return undefined;
    let open: ReturnType<typeof setTimeout> | undefined;
    let next: ReturnType<typeof setTimeout>;
    const schedule = () => {
      next = setTimeout(() => {
        setShut(true);
        open = setTimeout(() => {
          setShut(false);
          schedule();
        }, 130);
      }, 2800 + Math.random() * 2800);
    };
    schedule();
    return () => {
      clearTimeout(next);
      if (open) clearTimeout(open);
    };
  }, [enabled]);
  return enabled && shut;
}

export function CastRig({
  id,
  mood = 'neutre',
  mouth = 'auto',
  blink,
  crop = 'bust',
  size = 120,
  hold,
  variant,
  outfit,
  still = false,
  label,
  className,
}: CastRigProps) {
  const rig = rigFor(id);
  const autoBlink = useAutoBlink(blink === undefined && !still && Boolean(rig) && !rig?.faceless);
  if (!rig) return null;
  const worn = outfit && rig.outfits?.includes(outfit) ? outfit : undefined;
  const values = rigValues(rig, { mood, mouth, blink: blink ?? autoBlink, hold, variant, outfit: worn });
  const box = rig.crops[crop] ?? rig.crops.full;
  const height = Math.round((size * box[3]) / box[2]);
  const Art = rig.Art;
  const name = label ?? rig.name;
  const style = {
    '--cast-idle': `${rig.idle.seconds}s`,
    '--cast-lift': `${-Math.abs(rig.idle.amount)}px`,
    '--cast-turn': `${rig.idle.amount}deg`,
  } as CSSProperties;
  const classes = ['cast-rig', `cast-rig--${rig.idle.kind}`, still ? 'cast-rig--still' : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  return (
    <svg
      viewBox={box.join(' ')}
      width={size}
      height={height}
      className={classes}
      style={style}
      role={name ? 'img' : undefined}
      aria-label={name || undefined}
      aria-hidden={name ? undefined : true}
      data-cast={rig.id}
      data-mood={mood}
      data-mouth={values.mouth || undefined}
      focusable="false"
    >
      <Art v={values} />
    </svg>
  );
}

export default CastRig;
