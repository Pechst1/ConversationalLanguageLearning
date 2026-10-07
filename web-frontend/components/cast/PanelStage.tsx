/**
 * WP-116 phase 3 · the drawn cast standing on a panel's plate.
 * WP-143 «One stage, one light» · the cast stands in the plate's light, and no face
 * is ever cropped.
 *
 * Who: the panel's speakers (one figure each, at most three), plus Toi seen from
 * behind in the corner when the learner speaks in the panel. Where: the speaker in
 * front and a little bigger, the others behind and raised. The stage is an absolute
 * layer (`inset: 0`) drawn inside the element that shows the plate (the reader's
 * `.fr-plate`, the Revue's `.rv-stage`), `position: relative`.
 *
 * Props (every one but `members` optional; WP-143 only added, never changed, props):
 *
 *   members    StageMember[]   who stands on the plate (≤ 3 shown; Toi is never one).
 *   you        boolean | { crop: 'bust' | 'half' }   Toi from behind in the corner.
 *   still      boolean         no idle, no blinking.
 *   talking    { id, mouth }   who is heard now; the others hold still (WP-116 ph. 4).
 *   surface    'story' | 'revue'   only `revue` lets Toi out of the coat (WP-119).
 *   entering   rig id          the figure that slides in (WP-119).
 *   ── WP-143 ──
 *   framing    'band' | 'fill' `band` (default): busts sized by the stage's height on
 *                              its bottom edge, the layout of WP-116. `fill`: a full-bleed
 *                              crop (WP-144's 9:16 page): whole figures on a ground line,
 *                              as tall as their heads allow side by side.
 *   focus      { x, y } 0–1    where the speakers gather: `x` shifts the group (both
 *                              framings). For the plate itself use `plateObjectPosition`
 *                              (lib/stage-frame) with the same focus, so a 9:16 crop of a
 *                              16:9 plate keeps the scene's centre and the heads in frame.
 *   aspect     number          the stage's width ÷ height when the caller knows it; else
 *                              measured (ResizeObserver), 4:3 until then.
 *   plateUrl   string | null   the plate the light is read from. Omitted: the stage reads
 *                              the `<img>` beside it in its parent (the reader's plate).
 *                              null: no plate, the neutral light.
 *   light      boolean         default true. false: the flat rigs of WP-116, no grade, rim,
 *                              shadow, grain or depth of field.
 *   onHeads    (heads) => void every figure's head box in % of the stage, after layout
 *                              (for anchoring balloons to speakers).
 *
 * The light (lib/stage-grade): the plate is read once into a 32×24 canvas and cached per
 * URL. From it come a per-channel grade and a saturation (an SVG filter on each rig), a
 * rim light in the plate's highlight on the side its light comes from, a cast shadow and
 * a contact shadow in its shadow tone on the other side, a paper grain over the cast as
 * strong as the plate's own texture, and a 0.6 px softening of the plate behind the
 * speakers (CSS, styles/cast-rig.css). Nothing moves; Reduce Motion only drops the fade
 * in of the light. No WebGL, no new art, no colour token: every colour is the plate's.
 *
 * The framing rule (lib/stage-frame): each figure's head box (its rig's `crops.head`) is
 * kept inside the stage, 2 % from every edge; a figure is moved, or shrunk if it must
 * be, never its head cut. Each figure carries `data-head="x y w h"` (% of the stage).
 *
 * WP-119 §8.2 · Toi's `outfit` (on a member whose id is Toi's) is drawn only when
 * `surface === 'revue'`. In the story the heavy coat stays canon (WP-118), so on
 * the default `story` surface the outfit is dropped. The applied outfit is on the
 * Toi figure as `data-outfit`.
 */
import React, { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';

import type { StageMood } from '@/lib/cast-faces';
import { castVariant } from '@/lib/cast-variants';
import { stageLayout, type FocusPoint, type HeadBox, type StageFraming } from '@/lib/stage-frame';
import { usePlateGrade, type StageGrade } from '@/lib/stage-grade';
import { CastRig } from './CastRig';
import { rigFaceFor, rigFor } from './cast-registry';
import { drawnFaceId } from './CastFace';
import type { Outfit, Viseme } from './rig-kit';

export type { FocusPoint, HeadBox, StageFraming } from '@/lib/stage-frame';

export type StageMember = {
  /** Any id the payloads use for the character («marin», «marin_leveque», a name). */
  id: string;
  /** WP-137 C-4: the four portrait moods, or `cold` (no smile). */
  mood?: StageMood | null;
  speaking?: boolean;
  /** WP-116 phase 4: the mouth while this member's line is heard. */
  mouth?: Viseme | 'auto';
  /** WP-119 · Toi's outfit; only the Revue stage draws it (see `toiOutfit`). */
  outfit?: Outfit;
  /** WP-119 §8.3 · an authored prop in the figure's hands («notebook»); a rig that has none ignores it. */
  hold?: string | null;
};

/**
 * WP-119 · how Toi is cropped. `bust` is the season panels' corner figure (46 %
 * high); `half` is the Revue's waist crop (58 % high, 180:260) so the dress reads.
 */
export type YouCrop = 'bust' | 'half';

export type StageSurface = 'story' | 'revue';

/** WP-143 · a figure's head on the stage, for `onHeads`. */
export type StageHead = { id: string; speaking: boolean; box: HeadBox };

/** The outfit Toi wears on this surface: the coat everywhere but the Revue. */
export function toiOutfit(members: StageMember[], surface: StageSurface = 'story'): Outfit {
  if (surface !== 'revue') return 'coat';
  const toi = members.find((member) => member.outfit && rigFor(member.id)?.id === 'user');
  return toi?.outfit ?? 'coat';
}

export function stageMembers(members: StageMember[]): Array<StageMember & { rigId: string }> {
  const seen = new Set<string>();
  const out: Array<StageMember & { rigId: string }> = [];
  for (const member of members) {
    const rigId = drawnFaceId(member.id);
    if (!rigId || rigId === 'user' || seen.has(rigId)) continue;
    seen.add(rigId);
    out.push({ ...member, rigId });
    if (out.length === 3) break;
  }
  return out;
}

/** The stage's aspect before it is measured (and on the server). */
const DEFAULT_ASPECT = 4 / 3;

const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

/** The stage's width ÷ height: the caller's, else measured. */
function useStageAspect(ref: React.RefObject<HTMLElement>, given: number | undefined): number {
  const [measured, setMeasured] = useState<number | null>(null);
  useIsomorphicLayoutEffect(() => {
    if (given) return undefined;
    const node = ref.current;
    if (!node) return undefined;
    const read = () => {
      const { width, height } = node.getBoundingClientRect();
      if (width > 0 && height > 0) setMeasured((old) => (old && Math.abs(old - width / height) < 0.005 ? old : width / height));
    };
    read();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(read);
    observer.observe(node);
    return () => observer.disconnect();
  }, [given, ref]);
  return given || measured || DEFAULT_ASPECT;
}

/** The plate beside the stage: the last `<img>` child of its parent that is not fading out. */
function useSiblingPlate(ref: React.RefObject<HTMLElement>, enabled: boolean): string | null {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled) return undefined;
    const host = ref.current?.parentElement;
    if (!host) return undefined;
    const read = () => {
      const images = Array.from(host.children).filter(
        (node): node is HTMLImageElement => node instanceof HTMLImageElement && !node.classList.contains('is-previous'),
      );
      const plate = images[images.length - 1];
      setSrc(plate ? plate.getAttribute('src') || null : null);
    };
    read();
    if (typeof MutationObserver === 'undefined') return undefined;
    const observer = new MutationObserver(read);
    observer.observe(host, { childList: true, subtree: true, attributes: true, attributeFilter: ['src', 'class'] });
    return () => observer.disconnect();
  }, [enabled, ref]);
  return src;
}

function rgba(hex: string, alpha: number): string {
  const value = hex.replace('#', '');
  const channel = (at: number) => parseInt(value.slice(at, at + 2), 16) || 0;
  return `rgba(${channel(0)}, ${channel(2)}, ${channel(4)}, ${alpha})`;
}

/** The custom properties the stage's CSS draws the light with (styles/cast-rig.css). */
export function stageLightStyle(grade: StageGrade): CSSProperties {
  // The cast shadow falls away from the light, a little down; lower light, longer shadow.
  const reach = 3 + (1 - grade.height) * 5;
  return {
    '--stage-shadow': rgba(grade.shadow, grade.shadowOpacity),
    '--stage-contact': rgba(grade.shadow, Math.min(0.6, grade.shadowOpacity + 0.15)),
    '--stage-shadow-x': `${(-grade.side * reach).toFixed(1)}px`,
    '--stage-shadow-y': `${(2 + grade.height * 2).toFixed(1)}px`,
    '--stage-grain': String(grade.grain),
  } as CSSProperties;
}

/** The SVG filter each rig is drawn through: the plate's grade, then its rim light. */
export function StageLightFilter({ id, grade }: { id: string; grade: StageGrade }) {
  const [sr, sg, sb] = grade.slope;
  const [ir, ig, ib] = grade.intercept;
  // The lit edge: the silhouette minus itself shifted away from the light (rig units).
  const dx = -grade.side * 3.5;
  const dy = Math.round(3.5 * grade.height * 10) / 10;
  return (
    <svg className="cast-stage__defs" width="0" height="0" aria-hidden="true" focusable="false">
      <filter id={id} x="-4%" y="-4%" width="108%" height="108%" colorInterpolationFilters="sRGB">
        <feComponentTransfer in="SourceGraphic" result="graded">
          <feFuncR type="linear" slope={sr} intercept={ir} />
          <feFuncG type="linear" slope={sg} intercept={ig} />
          <feFuncB type="linear" slope={sb} intercept={ib} />
        </feComponentTransfer>
        <feColorMatrix in="graded" type="saturate" values={String(grade.saturate)} result="toned" />
        <feOffset in="SourceAlpha" dx={dx} dy={dy} result="shifted" />
        <feComposite in="SourceAlpha" in2="shifted" operator="out" result="edge" />
        <feGaussianBlur in="edge" stdDeviation="1.4" result="soft" />
        <feComposite in="soft" in2="SourceAlpha" operator="in" result="band" />
        <feFlood floodColor={grade.rim} floodOpacity={grade.rimOpacity} result="rimColour" />
        <feComposite in="rimColour" in2="band" operator="in" result="rim" />
        <feBlend in="rim" in2="toned" mode="screen" />
      </filter>
    </svg>
  );
}

export function PanelStage({
  members,
  you = false,
  still = false,
  talking = null,
  surface = 'story',
  entering = null,
  framing = 'band',
  focus = null,
  aspect,
  plateUrl,
  light = true,
  onHeads,
}: {
  members: StageMember[];
  /**
   * The learner speaks in this panel: Toi stands in the corner, from behind.
   * WP-119: `{ crop: 'half' }` is the Revue's waist crop.
   */
  you?: boolean | { crop?: YouCrop };
  still?: boolean;
  /** WP-116 phase 4: who is heard right now and their mouth; the others hold still. */
  talking?: { id: string; mouth: Viseme | 'auto' } | null;
  /** WP-119 · where the stage stands; only `revue` lets Toi change out of the coat. */
  surface?: StageSurface;
  /** WP-119 · the rig id that slides in (260 ms; none under Reduce Motion, see cast-rig.css). */
  entering?: string | null;
  /** WP-143 · `band` (busts on the bottom edge) or `fill` (whole figures, a full-bleed crop). */
  framing?: StageFraming;
  /** WP-143 · where the speakers gather, 0–1 (`x` shifts the group). */
  focus?: FocusPoint | null;
  /** WP-143 · the stage's width ÷ height, when known (else measured). */
  aspect?: number;
  /** WP-143 · the plate the light is read from; omitted: the `<img>` beside the stage. */
  plateUrl?: string | null;
  /** WP-143 · false: the flat rigs, no stage light. */
  light?: boolean;
  /** WP-143 · every figure's head box (% of the stage) after layout. */
  onHeads?: (heads: StageHead[]) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const talkingRig = talking ? drawnFaceId(talking.id) : null;
  const cast = stageMembers(members);
  const outfit = toiOutfit(members, surface);
  const youCrop: YouCrop | null = you ? (typeof you === 'object' && you.crop === 'half' ? 'half' : 'bust') : null;
  const enteringRig = entering ? drawnFaceId(entering) : null;
  const ratio = useStageAspect(ref, aspect);
  const sibling = useSiblingPlate(ref, light && plateUrl === undefined);
  const grade = usePlateGrade(light ? (plateUrl === undefined ? sibling : plateUrl) : null);
  const lit = light ? grade : null;
  const filterId = `stage-light-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const castKey = cast.map((member) => `${member.rigId}:${member.speaking ? 1 : 0}`).join(',');
  const layout = useMemo(
    () =>
      stageLayout({
        members: cast.map((member) => ({ rigId: member.rigId, speaking: member.speaking })),
        aspect: ratio,
        rigOf: rigFor,
        framing,
        focus,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [castKey, ratio, framing, focus?.x, focus?.y],
  );
  const headsKey = layout.map((place) => `${place.rigId}:${Object.values(place.head).map((v) => v.toFixed(2)).join(' ')}`).join('|');
  useEffect(() => {
    if (!onHeads) return;
    onHeads(layout.map((place) => ({ id: place.rigId, speaking: place.front, box: place.head })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [headsKey]);
  if (!cast.length && !youCrop) return null;
  const pct = (value: number) => `${Math.round(value * 100) / 100}%`;
  return (
    <div
      ref={ref}
      className="cast-stage"
      aria-hidden="true"
      data-cast-stage={cast.map((member) => member.rigId).join(' ')}
      data-framing={framing}
      data-lit={lit ? (lit.sampled ? 'plate' : 'neutral') : undefined}
      data-dof={lit && cast.length ? '' : undefined}
      style={lit ? stageLightStyle(lit) : undefined}
    >
      {lit && <StageLightFilter id={filterId} grade={lit} />}
      {cast.map((member) => {
        const place = layout.find((entry) => entry.rigId === member.rigId);
        if (!place) return null;
        const face = rigFaceFor(member.mood ?? 'neutral');
        const heard = talkingRig === member.rigId ? talking?.mouth ?? 'auto' : 'auto';
        const head = place.head;
        return (
          <div
            key={member.rigId}
            className="cast-stage__figure"
            data-speaking={place.front ? '' : undefined}
            data-entering={enteringRig === member.rigId ? '' : undefined}
            data-crop={place.crop === 'full' ? 'full' : undefined}
            data-head={[head.x, head.y, head.w, head.h].map((v) => v.toFixed(1)).join(' ')}
            style={{
              left: pct(place.centre),
              height: pct(place.height),
              bottom: pct(place.bottom),
              zIndex: place.zIndex,
            }}
          >
            <CastRig
              id={member.rigId}
              mood={face.mood}
              crop={place.crop}
              size={180}
              variant={castVariant(member.rigId) ?? undefined}
              // The voice moves the mouth; between words a cold face holds its level line.
              mouth={heard !== 'auto' ? heard : face.mouth}
              // One mover at a time: while someone is heard, the others hold still.
              still={still || Boolean(talkingRig && talkingRig !== member.rigId)}
              hold={member.hold ?? undefined}
              filter={lit ? filterId : undefined}
              label=""
            />
          </div>
        );
      })}
      {youCrop === 'bust' && (
        <div
          className="cast-stage__figure cast-stage__figure--you"
          data-outfit={outfit}
          style={{ left: '88%', height: '46%', bottom: '-8%', zIndex: 4 }}
        >
          <CastRig id="user" crop="bust" size={120} still={still} outfit={outfit} filter={lit ? filterId : undefined} label="" />
        </div>
      )}
      {youCrop === 'half' && (
        // The waist crop: Toi's full drawing (viewBox 0 0 200 420) framed on x 10–190,
        // y 76–336, so the window is 180:260 and the bust's head stays where it was.
        <div
          className="cast-stage__figure cast-stage__figure--you"
          data-outfit={outfit}
          data-crop="half"
          style={{ left: '86%', height: '58%', bottom: '-6%', zIndex: 4, aspectRatio: '180 / 260', overflow: 'hidden' }}
        >
          <div style={{ position: 'absolute', left: '-5.556%', top: '-29.231%', width: '111.111%', height: '161.538%' }}>
            <CastRig id="user" crop="full" size={120} still={still} outfit={outfit} filter={lit ? filterId : undefined} label="" />
          </div>
        </div>
      )}
      {lit && <span className="cast-stage__grain" />}
    </div>
  );
}

export default PanelStage;
