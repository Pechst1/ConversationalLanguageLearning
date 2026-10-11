/**
 * WP-116 phase 4 · the drawn mouth follows the voice.
 *
 * While `voice` speaks the line `key`, this returns the mouth shape at the
 * line's playback position, sampled on animation frames; otherwise `'auto'`
 * (the mood's own mouth). Under Reduce Motion the mouth stays still: the speaking
 * ring already says who talks.
 */
import { useEffect, useMemo, useState } from 'react';

import type { LineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { mouthSteps, visemeAt } from '@/lib/visemes-fr';
import type { Viseme } from './rig-kit';

function reducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function useMouth(voice: LineVoice | null | undefined, key: string | null | undefined, text: string | null | undefined): Viseme | 'auto' {
  const speaking = Boolean(voice && key && voice.speakingKey === key && voice.progress);
  const steps = useMemo(() => mouthSteps(text || ''), [text]);
  const [mouth, setMouth] = useState<Viseme | 'auto'>('auto');
  useEffect(() => {
    if (!speaking || !voice?.progress || reducedMotion()) {
      setMouth('auto');
      return undefined;
    }
    const progress = voice.progress;
    let frame = 0;
    let last: Viseme | 'auto' = 'auto';
    const tick = () => {
      const at = progress();
      const next: Viseme | 'auto' = at === null ? 'auto' : visemeAt(steps, at);
      if (next !== last) {
        last = next;
        setMouth(next);
      }
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => {
      window.cancelAnimationFrame(frame);
      setMouth('auto');
    };
  }, [speaking, steps, voice?.progress]);
  return speaking ? mouth : 'auto';
}
