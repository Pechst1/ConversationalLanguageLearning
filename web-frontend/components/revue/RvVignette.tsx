/**
 * WP-120 §4.1 · RvVignette — the stamp a learner brings back from a Papier.
 *
 * Composed, not generated: an authored frame (a ring in av2 ink, blue or red by
 * what the learner made, a thin inner ring, the week number on the ring in
 * Instrument Sans, the place beneath in Garamond, a small yellow mark when the
 * learner's part was kept in the dispatch) around the dossier's pictogram, which
 * the server drew once in the house grammar and which is sanitised again here
 * (`sanitisePictogram`). Sizes: pin 28 px (the map), seal 64 px (the Relevé),
 * large 160 px (the close screen, with `stamping` for the 300 ms press).
 */

import React, { useId } from 'react';

import {
  PICTOGRAM_VIEWBOX,
  VIGNETTE_SIZE_PX,
  sanitisePictogram,
  vignetteLabel,
  weekNumber,
  type VignetteRing,
  type VignetteSize,
} from './vignette-model';

export type RvVignetteProps = {
  week: string;
  placeLabelFr: string;
  ring: VignetteRing;
  keptContribution: boolean;
  pictogramSvg: string;
  size?: VignetteSize;
  /** The close screen's press (300 ms; none under reduced motion). */
  stamping?: boolean;
  /** Overrides the French accessible name. */
  label?: string;
};

// The frame lives in a 120-unit box: band r 58 → 44, inner ring r 41.5, the
// pictogram's radius-40 circle scaled to 36.8 at the centre.
const BAND_MID = 51;

export function RvVignette({
  week,
  placeLabelFr,
  ring,
  keptContribution,
  pictogramSvg,
  size = 'seal',
  stamping = false,
  label,
}: RvVignetteProps) {
  const arcId = `rv-vignette-arc-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const px = VIGNETTE_SIZE_PX[size];
  const no = weekNumber(week);
  const shapes = sanitisePictogram(pictogramSvg);
  const name = label ?? vignetteLabel({ week, placeLabelFr, ring, keptContribution });
  const className = ['rv-vignette', `rv-vignette--${size}`, stamping ? 'rv-vignette--stamping' : ''].filter(Boolean).join(' ');

  return (
    <figure className={className} data-ring={ring} data-size={size} data-kept={keptContribution ? '' : undefined}>
      <svg
        className="rv-vignette__stamp"
        viewBox="0 0 120 120"
        width={px}
        height={px}
        role="img"
        aria-label={name}
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle className="rv-vignette__band" cx="60" cy="60" r="58" />
        <circle className="rv-vignette__face" cx="60" cy="60" r="44" />
        <circle className="rv-vignette__inner" cx="60" cy="60" r="41.5" fill="none" />
        <svg
          className="rv-vignette__picto"
          x="14"
          y="14"
          width="92"
          height="92"
          viewBox={PICTOGRAM_VIEWBOX}
          aria-hidden="true"
          dangerouslySetInnerHTML={{ __html: shapes }}
        />
        {no != null && size === 'large' && (
          <>
            <defs>
              <path id={arcId} d={`M ${60 - BAND_MID} 60 A ${BAND_MID} ${BAND_MID} 0 0 1 ${60 + BAND_MID} 60`} />
            </defs>
            <text className="rv-vignette__week" aria-hidden="true">
              <textPath href={`#${arcId}`} startOffset="50%" textAnchor="middle" dominantBaseline="central">
                {`semaine ${no}`}
              </textPath>
            </text>
          </>
        )}
        {no != null && size === 'seal' && (
          <text className="rv-vignette__week" x="60" y={60 - BAND_MID} textAnchor="middle" dominantBaseline="central" aria-hidden="true">
            {no}
          </text>
        )}
        {keptContribution && <circle className="rv-vignette__kept" cx="60" cy={60 + BAND_MID} r={size === 'pin' ? 8 : 5} />}
      </svg>
      {size !== 'pin' && placeLabelFr && (
        <figcaption className="rv-vignette__place" lang="fr" aria-hidden="true">
          {placeLabelFr}
        </figcaption>
      )}
    </figure>
  );
}

export default RvVignette;
