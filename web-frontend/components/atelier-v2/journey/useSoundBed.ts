/**
 * WP-145 «Ambiance» — the scene's sound bed, from the scene's place and its voice.
 *
 * A sibling of `useLineVoice`: the scene step passes the place it is set in
 * (the journey scenario's `location_id`, else the place its first plate shows)
 * and whether a line is playing; the bed itself lives in `lib/sound-bed.ts`.
 * The stage (`components/cast/PanelStage`) is not touched.
 *
 *   * the scene opens: the bed is rendered while the page is idle, nothing sounds;
 *   * the learner's first gesture in the scene: the shared AudioContext is made
 *     or resumed inside that gesture and the bed fades in;
 *   * a line plays: the bed ducks 12 dB, and comes back after;
 *   * the page hides: the bed stops and the context is suspended; it comes back
 *     when the page does (or on the next gesture, on iOS);
 *   * the scene closes: the bed fades out.
 *
 * Gated by «Sons» and «Ambiance» (`ambianceEnabled`): with either off this hook
 * creates nothing and renders nothing.
 */

import { useEffect } from 'react';

import { ambianceEnabled, bedForPlace, prepareBed, soundBed } from '@/lib/sound-bed';

/** The events that count as the learner's gesture (iOS unlocks audio on touchend/click). */
export const BED_GESTURE_EVENTS = ['pointerup', 'touchend', 'click', 'keydown'] as const;

export function useSoundBed({
  place,
  speaking,
  active = true,
}: {
  /** The scene's location id (`le_mistral`, `quai_de_valmy`…), or null for the quiet default. */
  place: string | null | undefined;
  /** A character's line is playing now. */
  speaking: boolean;
  /** False keeps the bed closed (a step that is not a scene). */
  active?: boolean;
}): void {
  const bed = bedForPlace(place);

  // Open on mount, close on unmount; the gesture and page listeners live as long as the scene.
  useEffect(() => {
    if (!active || typeof window === 'undefined' || !ambianceEnabled()) return undefined;
    const controller = soundBed();
    controller.open(bedForPlace(place));
    const onGesture = () => {
      controller.gesture();
    };
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') controller.hide();
      else controller.show();
    };
    const onPageHide = () => controller.hide();
    for (const type of BED_GESTURE_EVENTS) window.addEventListener(type, onGesture, true);
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', onPageHide);
    return () => {
      for (const type of BED_GESTURE_EVENTS) window.removeEventListener(type, onGesture, true);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', onPageHide);
      controller.close();
    };
    // The place is followed by the effect below; reopening on a place change would wait for a new gesture.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  useEffect(() => {
    if (!active || typeof window === 'undefined' || !ambianceEnabled()) return undefined;
    soundBed().setBed(bed);
    return prepareBed(bed);
  }, [active, bed]);

  useEffect(() => {
    if (!active || typeof window === 'undefined') return;
    soundBed().setSpeaking(Boolean(speaking));
  }, [active, speaking]);
}
