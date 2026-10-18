/**
 * Les objets de la saison, in hand: how each carrier holds out the object their part turns on,
 * in their own «montre» (components/cast/vivant).
 *
 *   <VivantFigure id="romy" gesture="montre" offer={itemOffer('romy', 'polaroid')} />
 *
 * Each object is drawn about the point a hand holds it (`ITEM_ART[id].grip`), at the figures'
 * scale; a hold only says where that point sits from the palm, how the object leans and how big
 * it is in that hand. An open palm carries it on top (Gus, Lila), a fist grips it by an edge or a
 * corner (Romy, Marchand), Marin's big hand pinches the corner of the envelope. Margaux's
 * «montre» already brings her own key out of the apron (figures/margaux.tsx): she holds out
 * anything else in the same hand.
 *
 * The object stays in the hand while the gesture's props would show; `handoverAt` says when the
 * hand lets go, so the card that keeps it (CameoLayer) can arrive just then.
 */
import React from 'react';

import type { SeasonItemId } from '@/lib/season-items';

import type { ExpressionId, FigureDef, Side } from '../vivant/kit';
import { actionWindow } from '../vivant/kit';
import type { VivantOffer } from '../vivant/VivantFigure';
import { withOffer } from '../vivant/VivantFigure';
import { ITEM_ART, ItemDrawing, PLOT_ITEM_CSS } from './PlotItem';

type Hold = { side: Side; at: [number, number]; r: number; s: number; face?: ExpressionId };

/** The hand each figure holds out in its «montre», and how it carries an object there; `own` is
 * the object that gesture already holds. */
const HOLDS: Record<string, { base: Hold; own?: SeasonItemId; items?: Partial<Record<SeasonItemId, Partial<Hold>>> }> = {
  // the left hand out of the apron pocket, in front of her
  margaux: { base: { side: 'L', at: [0, -2], r: -4, s: 1.15 }, own: 'cle_cigale' },
  // the open right palm, fingers to the viewer's right: the clipboard stands on it, the chain
  // hangs over it
  gus: { base: { side: 'R', at: [-17, -1], r: 3, s: 1.2 }, items: { chaine: { at: [0, -5], r: 0, s: 1.3 } } },
  // the open right hand beside her pointing pencil
  lila: { base: { side: 'R', at: [7, -1], r: 8, s: 1.25 }, items: { lettre_berlin: { at: [17, 2], r: -4, s: 1.2 } } },
  // the right fist, where the microphone goes: the Polaroid by its white margin
  romy: { base: { side: 'R', at: [0, 3], r: -6, s: 1.35 } },
  // the right fist, where the registered letter goes: the notebook by its corner
  marchand: { base: { side: 'R', at: [13, 3], r: -8, s: 1.2 } },
  // the big right hand, where the soup goes: the envelope by its corner, and a smile through it
  marin: { base: { side: 'R', at: [22, 9], r: -6, s: 1.05, face: 'joie' } },
};

/** The figure's face while it holds the object out, from the object's mood. */
const FACE: Record<string, ExpressionId> = { neutre: 'neutre', ravie: 'joie', surprise: 'surprise', fachee: 'fache', emue: 'emu' };

/** What a figure holds out for this object, or nothing when it has no hand for it. */
export function itemOffer(figure: string, id: SeasonItemId, mood?: string): VivantOffer | null {
  const holds = HOLDS[figure];
  const art = ITEM_ART[id];
  if (!holds || !art || holds.own === id) return null;
  const hold = { ...holds.base, ...(holds.items?.[id] ?? {}) };
  const [gx, gy] = art.grip;
  return {
    side: hold.side,
    face: hold.face ?? (mood ? FACE[mood] : undefined),
    css: PLOT_ITEM_CSS,
    art: (
      <g transform={`translate(${hold.at[0]} ${hold.at[1]}) rotate(${hold.r}) scale(${hold.s}) translate(${-gx} ${-gy})`}>
        <ItemDrawing id={id} />
      </g>
    ),
  };
}

/**
 * When the figure's hand lets the object go, in ms from the start of its «montre»: the end of
 * the offer's window (or of the gesture's own prop, for the object it already holds); `null`
 * when it does not hold it at all.
 */
export function handoverAt(fig: FigureDef | null | undefined, id: SeasonItemId): number | null {
  if (!fig) return null;
  const offer = itemOffer(fig.key, id);
  const held = HOLDS[fig.key]?.own === id;
  if (!offer && !held) return null;
  const g = (offer ? withOffer(fig, offer) : fig).gestures.montre;
  if (!g) return null;
  const windows = Object.values(g.show ?? {});
  const win = windows.find((w): w is [number, number] => Array.isArray(w));
  const end = win ? win[1] : actionWindow(g)[1];
  return Math.round(g.seconds * end * 1000);
}
