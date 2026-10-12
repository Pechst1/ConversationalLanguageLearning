/**
 * La troupe vivante · one jointed cast member, acting.
 *
 *   <VivantFigure id="romy" expression="malice" gesture="signature" loop size={200} />
 *
 * An addition beside `CastRig`, which keeps drawing the cast everywhere it does: this one is the
 * same drawing cut at the joints, with ten faces and six gestures per character. Motion is CSS
 * generated for the figure (only what this render needs, unless the page provides it all with
 * `css="none"`), so `still`, Reduce Motion or no JavaScript all show the gesture's clearest pose.
 */
import React from 'react';
import type { CSSProperties } from 'react';
import type { RigCrop } from '../rig-kit';
import type { ExpressionId, FaceDef, FigureDef, GestureId } from './kit';
import { EXPRESSIONS, GESTURES, faceValues, figureCss, gestureFaces } from './kit';
import { figureFor } from './registry';

export interface VivantFigureProps {
  id: string;
  /** a figure not (yet) in the registry: a preview, a test */
  figure?: FigureDef;
  expression?: ExpressionId;
  gesture?: GestureId | null;
  /** play the gesture over and over (a sheet, a gallery) instead of once */
  loop?: boolean;
  /** no motion at all: the gesture's clearest pose, the face as it is */
  still?: boolean;
  crop?: RigCrop;
  size?: number;
  /** `all` draws every face and lets classes pick one (a canvas switching without React) */
  faces?: 'one' | 'all';
  /** `none` when the page already carries the figure's whole stylesheet (`figureCss`) */
  css?: 'scoped' | 'none';
  label?: string;
  className?: string;
  style?: CSSProperties;
}

export function VivantFigure({
  id,
  figure,
  expression = 'neutre',
  gesture = null,
  loop = false,
  still = false,
  crop = 'full',
  size = 200,
  faces = 'one',
  css = 'scoped',
  label,
  className,
  style,
}: VivantFigureProps) {
  const fig = figure ?? figureFor(id);
  if (!fig) return null;
  const g = gesture ? fig.gestures[gesture] : null;
  // the faces this render carries: the figure's own first, then the gesture's
  const list: Array<[string, FaceDef]> = [[expression, fig.expressions[expression]]];
  const add = (fid: string, def: FaceDef) => {
    if (!list.some(([x]) => x === fid)) list.push([fid, def]);
  };
  if (faces === 'all') {
    EXPRESSIONS.forEach((e) => add(e, fig.expressions[e]));
    GESTURES.forEach((gid) => {
      const gf = gestureFaces(fig, gid);
      if (gf.act) add(gf.act[0], gf.act[1]);
      if (gf.then) add(gf.then[1], gf.then[2]);
    });
  } else if (gesture) {
    const gf = gestureFaces(fig, gesture);
    if (gf.act) add(gf.act[0], gf.act[1]);
    if (gf.then) add(gf.then[1], gf.then[2]);
  }
  const rendered = list.map(([fid, def]) => ({ id: fid, values: faceValues(fig, def) }));
  const box = fig.rig.crops[crop] ?? fig.rig.crops.full;
  const height = Math.round((size * box[3]) / box[2]);
  const name = label ?? fig.name;
  const classes = [
    'tv',
    `tv--${fig.key}`,
    `tv--${fig.idle.kind}`,
    `tv-e--${expression}`,
    g ? `tv-g--${gesture} tv--acting` : '',
    loop ? 'tv--loop' : '',
    still ? 'tv--still' : '',
    faces === 'all' ? 'tv--all' : '',
    className ?? '',
  ].filter(Boolean).join(' ');
  const vars = {
    '--tv-blink': `${fig.blink}s`,
    '--tv-idle': `${fig.idle.seconds}s`,
    '--tv-lift': `${-Math.abs(fig.idle.amount)}px`,
    '--tv-turn': `${fig.idle.amount}deg`,
    ...style,
  } as CSSProperties;
  const Art = fig.Art;
  return (
    <svg
      viewBox={box.join(' ')}
      width={size}
      height={height}
      className={classes}
      style={vars}
      role={name ? 'img' : undefined}
      aria-label={name || undefined}
      aria-hidden={name ? undefined : true}
      data-vivant={fig.key}
      data-expression={expression}
      data-gesture={gesture || undefined}
      focusable="false"
    >
      {css === 'scoped' ? <style dangerouslySetInnerHTML={{ __html: figureCss(fig, { expression, gesture }) }} /> : null}
      <Art faces={rendered} base={expression} />
    </svg>
  );
}

export default VivantFigure;
