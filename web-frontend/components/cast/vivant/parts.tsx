/**
 * La troupe vivante · the pieces every figure is built from: joints, hands, blinking eyes, mouths
 * that can talk, and the small effects around a head. See `kit.ts` for the motion.
 */
import React from 'react';
import type { ReactNode } from 'react';
import type { ArmDef, FaceValues, FigureDef, FxKind, HandShape, MouthValues, Pt, Side, VEye } from './kit';
import { handArt } from './kit';
import { INK } from '../rig-kit';

/**
 * A joint: its children are drawn in the figure's own coordinates and turn about `at`. The
 * nested translate puts the pivot at the animated group's origin, so the CSS only ever writes
 * `rotate()` whatever the crop.
 */
export function Joint({ name, at, children, part }: { name: string; at: Pt; children?: ReactNode; part?: boolean }) {
  const cls = part ? `tv-p tv-p--${name}` : `tv-j tv-j--${name}`;
  return (
    <g transform={`translate(${at[0]} ${at[1]})`}>
      <g className={cls}>
        <g transform={`translate(${-at[0]} ${-at[1]})`}>{children}</g>
      </g>
    </g>
  );
}

/** A named moving part (a prop, a light): moves about `at`, and fades on its own track. */
export function Part({ id, at, children }: { id: string; at: Pt; children?: ReactNode }) {
  return (
    <Joint name={id} at={at} part>
      <g className={`tv-po tv-po--${id}`}>{children}</g>
    </Joint>
  );
}

/** Shown only while a gesture or a face asks for it (hidden without any CSS). */
export function Shown({ id, children }: { id: string; children?: ReactNode }) {
  return (
    <g className={`tv-show tv-show--${id}`} opacity={0}>
      {children}
    </g>
  );
}

/** A resting prop a gesture may hide. */
export function Resting({ id, children }: { id: string; children?: ReactNode }) {
  return <g className={`tv-rest tv-rest--${id}`}>{children}</g>;
}

const SHAPES: HandShape[] = ['fist', 'open', 'point', 'thumb', 'two', 'pinch', 'flat'];

/**
 * The kit's hands about a palm centre: every shape is drawn, hidden, and shown by the gesture's
 * window. A thin rim in the skin's shade keeps a hand readable against a face.
 */
export function HandShapes({ side, at, r, skin, shade, only }: { side: Side; at: Pt; r: number; skin: string; shade: string; only?: HandShape[] }) {
  const mirror = side === 'L' ? ' scale(-1 1)' : '';
  return (
    <g transform={`translate(${at[0]} ${at[1]})${mirror}`}>
      {(only ?? SHAPES).map((shape) => {
        const art = handArt(shape, r);
        return (
          <g key={shape} className={`tv-hand tv-hand--${side}-${shape}`} opacity={0}>
            {art.fingers.map(([d, w], i) => (
              <path key={`o${i}`} d={d} fill="none" stroke={shade} strokeWidth={w + 2.4} strokeLinecap="round" />
            ))}
            <circle r={art.palm + 1.2} fill={shade} />
            <circle r={art.palm} fill={skin} />
            {art.fingers.map(([d, w], i) => (
              <path key={`f${i}`} d={d} fill="none" stroke={skin} strokeWidth={w} strokeLinecap="round" />
            ))}
            {art.creases ? <path d={art.creases} fill="none" stroke={shade} strokeWidth={1.3} strokeLinecap="round" /> : null}
          </g>
        );
      })}
    </g>
  );
}

/** The rig's own hand, shown at rest and whenever no other shape is asked for. */
export function RestHand({ side, children }: { side: Side; children?: ReactNode }) {
  return <g className={`tv-hand tv-hand--${side}-rest`}>{children}</g>;
}

/**
 * Something a figure is given to hold out for one gesture (the season's objects, see
 * components/cast/items/offer.tsx): drawn about the palm of `side`, in the hand's own layer just
 * under the fingers, kept upright, and shown only while the gesture's `offer` window is open.
 */
export type Offer = { side: Side; art: ReactNode };

export const OfferContext = React.createContext<Offer | null>(null);

function OfferSlot({ side, arm }: { side: Side; arm: ArmDef }) {
  const offer = React.useContext(OfferContext);
  if (!offer || offer.side !== side) return null;
  return (
    <Joint name={`${side.toLowerCase()}hp`} at={arm.palm}>
      <Shown id="offer">
        <g transform={`translate(${arm.palm[0]} ${arm.palm[1]})`}>{offer.art}</g>
      </Shown>
    </Joint>
  );
}

/**
 * One arm in one layer. A figure stacks several layers that share the same joints (sleeve
 * behind the camera, hand in front of it), so the drawing order of the original survives. The
 * layer that draws the hand also carries the hand's offer slot.
 */
export function ArmLayer({
  side,
  arm,
  upper,
  fore,
  hand,
  held,
}: {
  side: Side;
  arm: ArmDef;
  upper?: ReactNode;
  fore?: ReactNode;
  hand?: ReactNode;
  /** kept upright whatever the arm does (a cup, a camera) */
  held?: ReactNode;
}) {
  const l = side.toLowerCase();
  return (
    <Joint name={`${l}u`} at={arm.shoulder}>
      {upper}
      <Joint name={`${l}f`} at={arm.elbow}>
        {fore}
        <Joint name={`${l}h`} at={arm.palm}>
          {held ? <Joint name={`${l}hp`} at={arm.palm}>{held}</Joint> : null}
          {hand ? <OfferSlot side={side} arm={arm} /> : null}
          {hand}
        </Joint>
      </Joint>
    </Joint>
  );
}

/**
 * The blink lid over an open eye: hidden and scaled to nothing at rest, also without CSS (a
 * zero scale alone still leaves a hairline under a tilted head).
 */
export function Blink({ e, skin, line = 2.6 }: { e: VEye; skin: string; line?: number }) {
  if (!e.blinks) return null;
  const [x, y] = e.blinkTop;
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="tv-blink" transform="scale(1 0)" opacity={0}>
        <g transform={`translate(${-x} ${-y})`}>
          <path d={e.blinkLid} fill={skin} />
          <path d={e.blinkLine} fill="none" stroke={INK} strokeWidth={line} strokeLinecap="round" />
        </g>
      </g>
    </g>
  );
}

/** Lower lids for the narrowed states (smug), in the skin, with their line. */
export function LowerLid({ e, skin, line = 2.4 }: { e: VEye; skin: string; line?: number }) {
  if (!e.lower) return null;
  return (
    <>
      <path d={e.lower} fill={skin} />
      <path d={e.lowerLine} fill="none" stroke={INK} strokeWidth={line * 0.8} strokeLinecap="round" />
    </>
  );
}

/**
 * The mouth(s) of a face: one, or a talking cycle (a, e, o, m, then the face's own) whose
 * frames the CSS steps through; without CSS only the face's own mouth shows.
 */
export function Mouths({ mouths, transform }: { mouths: MouthValues[]; transform: string }) {
  const talking = mouths.length > 1;
  return (
    <g transform={transform} className={talking ? 'tv-talk' : undefined}>
      {mouths.map((m, i) => (
        <g key={`${m.key}-${i}`} className={talking ? `tv-mouth tv-mouth--${i}` : undefined} opacity={talking && i < mouths.length - 1 ? 0 : undefined}>
          <path d={m.d} fill={m.fill} />
          {m.teeth ? <path d={m.teeth} fill="#ffffff" /> : null}
          {m.tongue ? <path d={m.tongue} fill="#d8321a" /> : null}
          {m.line ? <path d={m.line} fill="none" stroke={INK} strokeWidth={0.7} strokeLinecap="round" /> : null}
        </g>
      ))}
    </g>
  );
}

/** Eye pieces an Art draws in its own colours, the pupil cluster inside the wandering gaze. */
export function EyeSet({ e, skin, iris, lidLine = 2.6, arcLine = 4.2, lash }: { e: VEye; skin: string; iris?: string; lidLine?: number; arcLine?: number; lash?: string }) {
  return (
    <>
      <path display={e.sD} d={e.sclera} fill="#ffffff" />
      <g className="tv-gaze">
        {iris ? <path display={e.sD} d={e.iris} fill={iris} /> : null}
        <path display={e.sD} d={e.pupil} fill={INK} />
        <path display={e.sD} d={e.glint} fill="#ffffff" />
        {e.spark ? <path display={e.sD} d={e.spark} fill="#ffffff" /> : null}
      </g>
      <path d={e.lid} fill={skin} />
      <path d={e.lidLine} fill="none" stroke={INK} strokeWidth={lidLine} strokeLinecap="round" />
      <LowerLid e={e} skin={skin} line={lidLine} />
      {lash ? <path display={e.sD} d={lash} fill="none" stroke={INK} strokeWidth={2.8} strokeLinecap="round" /> : null}
      <path d={e.arc} fill="none" stroke={INK} strokeWidth={arcLine} strokeLinecap="round" strokeLinejoin="round" />
      <path d={e.tear} fill="#1d3a8a" />
      <Blink e={e} skin={skin} line={lidLine} />
    </>
  );
}

const STAR = 'M0,-6 Q0.9,-0.9 6,0 Q0.9,0.9 0,6 Q-0.9,0.9 -6,0 Q-0.9,-0.9 0,-6 Z';
const HEART = 'M0,3.6 C-5.6,-0.6 -5.4,-5.4 -2.6,-5.6 C-1.2,-5.7 -0.3,-4.8 0,-3.8 C0.3,-4.8 1.2,-5.7 2.6,-5.6 C5.4,-5.4 5.6,-0.6 0,3.6 Z';
const DROP = 'M0,-7 C2.6,-2.6 4.6,0.4 4.6,2.8 A4.6,4.6 0 1 1 -4.6,2.8 C-4.6,0.4 -2.6,-2.6 0,-7 Z';
const ZED = 'M-3.6,-3.6 L3.6,-3.6 L-3.6,3.6 L3.6,3.6';
const QUESTION = 'M-3.4,-4.2 Q-3.4,-8.4 0.3,-8.4 Q4,-8.4 4,-4.8 Q4,-2 0.6,-0.6 L0.6,2.2';
const VEIN = 'M-5,-1.6 Q-1.6,-1.6 -1.6,-5 M1.6,-5 Q1.6,-1.6 5,-1.6 M5,1.6 Q1.6,1.6 1.6,5 M-1.6,5 Q-1.6,1.6 -5,1.6';

const at = (p: Pt) => `translate(${p[0]} ${p[1]})`;

/** The small drawn effects of a face, placed on the figure's head anchors. */
export function Fx({ kinds, fig }: { kinds?: FxKind[]; fig: FigureDef }) {
  if (!kinds?.length) return null;
  const a = fig.fx;
  return (
    <g className="tv-fx">
      {kinds.map((k) => {
        switch (k) {
          case 'blush':
            return (
              <g key={k}>
                {[a.cheekL, a.cheekR].map((c, i) => (
                  <g key={i} transform={at(c)}>
                    <ellipse rx={9} ry={5} fill="#e5604a" opacity={0.42} />
                    <path d="M-5,2.4 L-2.6,-2.4 M-0.8,2.4 L1.6,-2.4 M3.4,2.4 L5.8,-2.4" fill="none" stroke="#d8321a" strokeWidth={1.3} strokeLinecap="round" opacity={0.7} />
                  </g>
                ))}
              </g>
            );
          case 'sweat':
            return (
              <g key={k} transform={at(a.temple)}>
                <g className="tv-fx-drip">
                  <path d={DROP} fill="#5b86c8" />
                  <ellipse cx={-1.4} cy={2.2} rx={1.2} ry={1.8} fill="#f8f3e8" />
                </g>
              </g>
            );
          case 'tears':
            return (
              <g key={k}>
                {[a.eyeL, a.eyeR].map((c, i) => (
                  <g key={i} transform={at(c)}>
                    <path className="tv-fx-stream" d={`M${i ? 4 : -4},4 C${i ? 7 : -7},12 ${i ? 3 : -3},18 ${i ? 6 : -6},26`} fill="none" stroke="#1d3a8a" strokeWidth={3.4} strokeLinecap="round" opacity={0.85} />
                  </g>
                ))}
              </g>
            );
          case 'sparkle':
            return (
              <g key={k}>
                <g transform={at(a.side)}><path className="tv-fx-twinkle" d={STAR} fill="#c49a0a" /></g>
                <g transform={`${at(a.crown)} translate(30 6) scale(0.6)`}><path className="tv-fx-twinkle tv-fx-late" d={STAR} fill="#f3c318" /></g>
                <g transform={`${at(a.side)} translate(-8 26) scale(0.45)`}><path className="tv-fx-twinkle tv-fx-later" d={STAR} fill="#c49a0a" /></g>
              </g>
            );
          case 'hearts':
            return (
              <g key={k}>
                <g transform={at(a.side)}><path className="tv-fx-float" d={HEART} fill="#d8321a" /></g>
                <g transform={`${at(a.crown)} translate(26 -4) scale(0.75)`}><path className="tv-fx-float tv-fx-late" d={HEART} fill="#d8321a" /></g>
              </g>
            );
          case 'zzz':
            return (
              <g key={k} transform={at(a.side)}>
                <path className="tv-fx-float" d={ZED} fill="none" stroke={INK} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                <g transform="translate(9 -12) scale(0.75)"><path className="tv-fx-float tv-fx-late" d={ZED} fill="none" stroke={INK} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" /></g>
              </g>
            );
          case 'vein':
            return (
              <g key={k} transform={at(a.temple)}>
                <path className="tv-fx-pulse" d={VEIN} fill="none" stroke="#d8321a" strokeWidth={2.2} strokeLinecap="round" />
              </g>
            );
          case 'steam':
            return (
              <g key={k} transform={at(a.crown)}>
                {[-16, 16].map((x, i) => (
                  <g key={x} transform={`translate(${x} 0)`}>
                    <g className={`tv-fx-puff${i ? ' tv-fx-late' : ''}`}>
                      <circle r={5} fill="#c9c2b2" />
                      <circle cx={4} cy={-4} r={3.6} fill="#c9c2b2" />
                    </g>
                  </g>
                ))}
              </g>
            );
          case 'shock':
            return (
              <g key={k} transform={at(a.crown)} className="tv-fx-pop">
                <path d="M-40,14 L-50,8 M-34,-2 L-42,-12 M-20,-12 L-24,-24 M40,14 L50,8 M34,-2 L42,-12 M20,-12 L24,-24" fill="none" stroke={INK} strokeWidth={2.4} strokeLinecap="round" />
              </g>
            );
          case 'question':
            return (
              <g key={k} transform={at(a.side)}>
                <g className="tv-fx-bob">
                  <path d={QUESTION} fill="none" stroke={INK} strokeWidth={2.4} strokeLinecap="round" />
                  <circle cx={0.6} cy={5.6} r={1.5} fill={INK} />
                </g>
              </g>
            );
          case 'glint':
            return (
              <g key={k} transform={at(a.side)}>
                <path className="tv-fx-twinkle" d={STAR} fill="#ffffff" />
              </g>
            );
          default:
            return null;
        }
      })}
    </g>
  );
}

/** The faces a render carries, each in its own group (one, or all of them for a canvas). */
export interface RenderedFace {
  id: string;
  values: FaceValues;
}

/** Every face a render carries, each with its effects; the first is the figure's own. */
export function Faces({ faces, fig, children }: { faces: RenderedFace[]; fig: FigureDef; children: (v: FaceValues) => ReactNode }) {
  return (
    <>
      {faces.map((f, i) => (
        <g key={f.id} className={`tv-face tv-face--${f.id}`} opacity={i === 0 ? undefined : 0}>
          {children(f.values)}
          <Fx kinds={f.values.def.fx} fig={fig} />
        </g>
      ))}
    </>
  );
}

/**
 * The head: placed where the rig puts it, turned about the neck by gestures, posed by the face
 * (tilt and nudge), idling inside. Children are drawn in the rig's head frame.
 */
export function Head({ fig, base, children }: { fig: FigureDef; base: string; children?: ReactNode }) {
  const [hx, hy] = fig.rig.head;
  const pose = fig.expressions[base as keyof FigureDef['expressions']];
  return (
    <g transform={`translate(${hx} ${hy})`}>
      <Joint name="head" at={[fig.neck[0] - hx, fig.neck[1] - hy]}>
        <g className="tv-hp" transform={`rotate(${pose?.tilt ?? 0}) translate(${pose?.dx ?? 0} ${pose?.dy ?? 0})`}>
          <g className="tv-idle">{children}</g>
        </g>
      </Joint>
    </g>
  );
}

/** What hangs behind the body but turns with the head (Romy's long hair). */
export function BehindHead({ fig, children }: { fig: FigureDef; children?: ReactNode }) {
  return (
    <Joint name="head" at={fig.neck}>
      {children}
    </Joint>
  );
}

/** The upper body, leaning about the hips; the legs stay planted. */
export function Body({ fig, children }: { fig: FigureDef; children?: ReactNode }) {
  return (
    <Joint name="body" at={fig.hips}>
      {children}
    </Joint>
  );
}

/** A piece that sways on its own (hair, an earring, a key): ±deg about `at`. */
export function Sway({ at: p, deg, seconds, delay = 0, children }: { at: Pt; deg: number; seconds: number; delay?: number; children?: ReactNode }) {
  const style = { '--tv-sw-a': `${deg}deg`, '--tv-sw-t': `${seconds}s`, '--tv-sw-d': `${delay}s` } as React.CSSProperties;
  return (
    <g transform={`translate(${p[0]} ${p[1]})`}>
      <g className="tv-sw" style={style}>
        <g transform={`translate(${-p[0]} ${-p[1]})`}>{children}</g>
      </g>
    </g>
  );
}

/**
 * Where an arm is drawn: `back` in the original order (behind the head), `front` over the head
 * for the moments a hand reaches the face. The front copy is hidden until a gesture or a face
 * asks for it; both share the same joints, so they always agree.
 */
export function Place({ side, place, children }: { side: Side; place: 'back' | 'front'; children?: ReactNode }) {
  return (
    <g className={`tv-${place} tv-${place}--${side}`} opacity={place === 'front' ? 0 : undefined}>
      {children}
    </g>
  );
}
