/**
 * Le Quartier · the troupe as paper: drawn figures and the season's objects as standalone SVG.
 *
 * The 3D quarter does not model the cast. It stands the troupe vivante's own drawings in the
 * street as paper cut-outs, so every face and gesture is the one the app already draws, and the
 * season's objects (the key with its cicada, the envelope) are the same drawings the Feuilleton
 * shows. This module renders them to self-contained SVG strings (their stylesheet inside, frozen
 * on the clearest pose) that the engine turns into textures. It is the engine's only React, and it
 * runs the same in the browser and in Node, so a build script can bake the same pictures.
 */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { avatarFigure } from '@/components/avatar/avatar-figure';
import { CastRig } from '@/components/cast/CastRig';
import { PlotItem } from '@/components/cast/items/PlotItem';
import { rigFor } from '@/components/cast/cast-registry';
import { VivantFigure } from '@/components/cast/vivant/VivantFigure';
import type { ExpressionId, GestureId } from '@/components/cast/vivant/kit';
import { figureFor } from '@/components/cast/vivant/registry';
import { randomAvatar } from '@/lib/avatar';
import type { SeasonItemId } from '@/lib/season-items';

import { seeded } from './geo';

export interface FigureArt {
  /** standalone markup, with the xmlns an <img> needs */
  svg: string;
  /** viewBox width over height, so the paper keeps the drawing's proportions */
  aspect: number;
}

export interface FigureArtOptions {
  expression?: ExpressionId;
  gesture?: GestureId | null;
  /** pixels across the drawing's width; the texture is rasterised from this */
  size?: number;
}

const standalone = (markup: string) => (markup.includes('xmlns=') ? markup : markup.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"'));

/** A jointed figure of the troupe, full length. */
export function figureArt(id: string, options: FigureArtOptions = {}): FigureArt | null {
  const fig = figureFor(id);
  if (!fig) return rigArt(id, options.size);
  const box = fig.rig.crops.full;
  const size = options.size ?? 256;
  const markup = renderToStaticMarkup(
    <VivantFigure
      id={fig.key}
      expression={options.expression ?? 'neutre'}
      gesture={options.gesture ?? null}
      still
      crop="full"
      size={size}
      label=""
    />,
  );
  return { svg: standalone(markup), aspect: box[2] / box[3] };
}

/** Someone with a drawn rig but no jointed figure yet (Camille, Odile): one still pose. */
export function rigArt(id: string, size = 256, variant?: string): FigureArt | null {
  const rig = rigFor(id);
  if (!rig) return null;
  const box = rig.crops.full;
  const markup = renderToStaticMarkup(<CastRig id={rig.id} crop="full" size={size} still label="" variant={variant} />);
  return { svg: standalone(markup), aspect: box[2] / box[3] };
}

/** One of the season's objects, as the Feuilleton draws it. */
export function itemArt(id: SeasonItemId, size = 256): FigureArt | null {
  const markup = renderToStaticMarkup(<PlotItem id={id} size={size} still label="" />);
  if (!markup) return null;
  return { svg: standalone(markup), aspect: 1 };
}

/** Someone of the neighbourhood: the avatar kit's figure, rolled from a seed (the same seed, the same person). */
export function passerbyArt(seed: number, size = 256): FigureArt {
  const R = seeded(seed);
  const fig = avatarFigure(randomAvatar(R.next), 'Passant');
  const box = fig.rig.crops.full;
  const markup = renderToStaticMarkup(<VivantFigure id={fig.key} figure={fig} expression="neutre" still crop="full" size={size} label="" />);
  return { svg: standalone(markup), aspect: box[2] / box[3] };
}
