/**
 * WP-116 · a drawn face for the round discs the app already uses (CastPortrait,
 * Feedback's Portrait, the Trombinoscope, the voice call). Returns `null` when the
 * person has no rig, or when their look depends on a choice the learner has not
 * made yet (Camille before T1 Day B), so the caller keeps its initial.
 */
import React from 'react';
import { drawnCastIdFor } from '@/lib/cast-faces';
import { castVariant, NEEDS_VARIANT } from '@/lib/cast-variants';
import type { PortraitMood } from '@/lib/onboarding-portraits';
import { CastRig } from './CastRig';
import { rigMoodFor } from './cast-registry';

export function drawnFaceId(...seeds: unknown[]): string | null {
  const id = drawnCastIdFor(...seeds);
  if (!id) return null;
  if (NEEDS_VARIANT.has(id) && !castVariant(id)) return null;
  return id;
}

export function CastFace({
  seeds,
  mood = 'neutral',
  size,
  still = false,
}: {
  seeds: unknown[];
  mood?: PortraitMood | 'surprised';
  size: number;
  still?: boolean;
}) {
  const id = drawnFaceId(...seeds);
  if (!id) return null;
  return (
    <CastRig
      id={id}
      mood={rigMoodFor(mood)}
      crop="head"
      size={size}
      variant={castVariant(id) ?? undefined}
      still={still}
      label=""
      className="cast-face"
    />
  );
}

export default CastFace;
