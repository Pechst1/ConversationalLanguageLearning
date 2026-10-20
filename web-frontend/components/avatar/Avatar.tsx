/**
 * Ton personnage · the learner's character, drawn.
 *
 *   <Avatar config={avatar} expression="joie" gesture="salut" size={220} />
 *   <AvatarDisc config={avatar} size={44} />   — the round face; a «+» when there is none yet
 *
 * A jointed figure of la troupe vivante (`avatar-figure.tsx`), so it blinks, idles, makes the ten
 * faces and plays the six gestures like Romy or Gus, and stops for Reduce Motion.
 */
import React, { useMemo } from 'react';
import type { CSSProperties } from 'react';

import type { RigCrop } from '@/components/cast/rig-kit';
import { VivantFigure } from '@/components/cast/vivant/VivantFigure';
import type { ExpressionId, GestureId } from '@/components/cast/vivant/kit';
import type { AvatarConfig } from '@/lib/avatar';

import { AVATAR_KEY, avatarFigure } from './avatar-figure';

export interface AvatarProps {
  config: AvatarConfig | null | undefined;
  expression?: ExpressionId;
  gesture?: GestureId | null;
  loop?: boolean;
  still?: boolean;
  crop?: RigCrop;
  size?: number;
  /** accessible name; empty marks the drawing decorative */
  label?: string;
  className?: string;
  style?: CSSProperties;
}

/** A stable key for a record, so the figure is only rebuilt when the character changes. */
function recordKey(config: AvatarConfig | null | undefined): string {
  return config ? JSON.stringify(config) : '';
}

export function Avatar({
  config,
  expression = 'neutre',
  gesture = null,
  loop = false,
  still = false,
  crop = 'full',
  size = 200,
  label = '',
  className,
  style,
}: AvatarProps) {
  const key = recordKey(config);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const figure = useMemo(() => avatarFigure(config ?? null, label || 'Moi'), [key, label]);
  return (
    <VivantFigure
      id={AVATAR_KEY}
      figure={figure}
      expression={expression}
      gesture={gesture}
      loop={loop}
      still={still}
      crop={crop}
      size={size}
      label={label}
      className={['av-figure', className ?? ''].filter(Boolean).join(' ')}
      style={style}
    />
  );
}

export interface AvatarDiscProps {
  config: AvatarConfig | null | undefined;
  size?: number;
  /** still by default: a disc in a list must not bob */
  still?: boolean;
  label?: string;
  className?: string;
}

/** The learner's face in a round disc, or a «+» to make one. */
export function AvatarDisc({ config, size = 44, still = true, label = '', className }: AvatarDiscProps) {
  const classes = ['av-disc', config ? '' : 'av-disc--empty', className ?? ''].filter(Boolean).join(' ');
  return (
    <span className={classes} style={{ width: size, height: size }} data-avatar-disc={config ? 'face' : 'plus'}>
      {config ? (
        <Avatar config={config} crop="head" size={size} still={still} label={label} />
      ) : (
        <svg viewBox="0 0 24 24" width={Math.round(size * 0.46)} height={Math.round(size * 0.46)} aria-hidden="true" focusable="false">
          <path d="M12 4v16M4 12h16" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" />
        </svg>
      )}
    </span>
  );
}

export default Avatar;
