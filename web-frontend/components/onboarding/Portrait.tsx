/**
 * WP-77 — a character's face, round, in one of three moods.
 *
 * Falls back to the av2 initial disc (the character's accent colour) when the
 * character has no drawn portrait or the image fails to load, so a missing
 * file is never a broken-image icon.
 */

import React from 'react';

import { characterAccent } from '@/components/atelier-v2/ui';
import { portraitInitial, portraitSrc, type PortraitMood } from '@/lib/onboarding-portraits';

export type CastPortraitProps = {
  characterId: string;
  /** The character's display name: the fallback initial and the accent. */
  name?: string;
  mood?: PortraitMood;
  size?: 'sm' | 'md' | 'lg';
  /** Empty (the default) marks the image decorative — a name sits beside it. */
  alt?: string;
};

const PX = { sm: 40, md: 64, lg: 112 } as const;

export function CastPortrait({ characterId, name, mood = 'neutral', size = 'md', alt = '' }: CastPortraitProps) {
  const src = portraitSrc(characterId, mood);
  const [failed, setFailed] = React.useState(false);
  React.useEffect(() => setFailed(false), [src]);

  const px = PX[size];
  const accent = characterAccent(name || characterId.replace(/_/g, ' '));
  const style = {
    width: px,
    height: px,
    ...(accent ? { ['--av2-char' as string]: accent } : null),
  } as React.CSSProperties;

  return (
    <span className="ob-portrait" data-size={size} data-mood={mood} style={style}>
      {src && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element -- static export: no image optimiser
        <img
          key={src}
          src={src}
          alt={alt}
          width={px}
          height={px}
          decoding="async"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="ob-portrait__initial" aria-hidden={alt ? undefined : true}>
          {portraitInitial(name, characterId)}
        </span>
      )}
      <style jsx>{`
        .ob-portrait {
          position: relative;
          display: inline-flex;
          flex: none;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          border-radius: 50%;
          background: var(--av2-char, var(--av2-line));
          box-shadow: 0 0 0 2px var(--av2-paper), 0 0 0 3px var(--av2-line);
        }
        .ob-portrait img {
          display: block;
          width: 100%;
          height: 100%;
          object-fit: cover;
          animation: ob-portrait-in 0.18s ease-out;
        }
        .ob-portrait__initial {
          font-family: var(--av2-serif);
          font-size: ${Math.round(px * 0.42)}px;
          font-weight: 600;
          line-height: 1;
          color: var(--av2-paper);
        }
        @keyframes ob-portrait-in {
          from {
            opacity: 0.4;
            transform: scale(0.96);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .ob-portrait img {
            animation: none;
          }
        }
      `}</style>
    </span>
  );
}

export default CastPortrait;
