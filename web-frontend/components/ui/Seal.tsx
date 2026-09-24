import React, { useId, useMemo, type CSSProperties } from 'react';
import { cn } from '@/lib/utils';

export type SealVariant = 'row' | 'stack' | 'nested' | 'quad' | 'orbit' | 'frieze';

/* ---------- the logo's four shapes, arranged per edition ----------
   WP-D4 (owner, 2026-09-22): every seal holds the logo's four shapes — blue
   circle, yellow square, red triangle, ink square — filled, with no stroke,
   each sitting on its own `*-deep` press so the forms read as the 3D buttons
   do. `quad` is the logo itself; the others are the same four, rearranged.
   Coordinates are in the well's 116-unit box. */
type Tone = 'circle' | 'square' | 'tri' | 'block';
type Form =
  | { tone: 'circle'; cx: number; cy: number; r: number }
  | { tone: 'square' | 'block'; x: number; y: number; s: number }
  | { tone: 'tri'; points: [number, number][] };

const FORMS: Record<SealVariant, Form[]> = {
  quad: [
    { tone: 'block', x: 26, y: 24, s: 26 },
    { tone: 'circle', cx: 77, cy: 37, r: 13 },
    { tone: 'square', x: 26, y: 60, s: 26 },
    { tone: 'tri', points: [[77, 60], [92, 86], [62, 86]] },
  ],
  row: [
    { tone: 'circle', cx: 20, cy: 56, r: 10 },
    { tone: 'square', x: 34, y: 46, s: 20 },
    { tone: 'tri', points: [[68, 46], [79, 66], [57, 66]] },
    { tone: 'block', x: 84, y: 46, s: 20 },
  ],
  stack: [
    { tone: 'tri', points: [[58, 14], [74, 40], [42, 40]] },
    { tone: 'square', x: 30, y: 46, s: 24 },
    { tone: 'circle', cx: 75, cy: 58, r: 12 },
    { tone: 'block', x: 48, y: 78, s: 20 },
  ],
  nested: [
    { tone: 'circle', cx: 58, cy: 56, r: 36 },
    { tone: 'tri', points: [[58, 30], [82, 76], [34, 76]] },
    { tone: 'square', x: 47, y: 52, s: 22 },
    { tone: 'block', x: 53, y: 58, s: 10 },
  ],
  orbit: [
    { tone: 'circle', cx: 58, cy: 56, r: 18 },
    { tone: 'square', x: 18, y: 22, s: 18 },
    { tone: 'tri', points: [[90, 20], [101, 40], [79, 40]] },
    { tone: 'block', x: 50, y: 84, s: 16 },
  ],
  frieze: [
    { tone: 'circle', cx: 27, cy: 33, r: 11 },
    { tone: 'square', x: 38, y: 42, s: 20 },
    { tone: 'tri', points: [[72, 54], [84, 76], [60, 76]] },
    { tone: 'block', x: 80, y: 80, s: 16 },
  ],
};

/** The press sits this many units under each shape (the 3D button's depth). */
const PRESS = 3;

function FormShape({ form, press }: { form: Form; press: boolean }) {
  const cls = cn('av2-seal__form', `av2-seal__form--${form.tone}`, press && 'is-press');
  const dy = press ? PRESS : 0;
  if (form.tone === 'circle') return <circle className={cls} cx={form.cx} cy={form.cy + dy} r={form.r} />;
  if (form.tone === 'tri') {
    return <polygon className={cls} points={form.points.map(([x, y]) => `${x},${y + dy}`).join(' ')} />;
  }
  return <rect className={cls} x={form.x} y={form.y + dy} width={form.s} height={form.s} rx={2} />;
}

export function CoreForms({ variant = 'row' }: { variant?: SealVariant }) {
  const forms = FORMS[variant] || FORMS.quad;
  return (
    <svg viewBox="0 0 116 116" aria-hidden="true" focusable="false">
      {forms.map((form, index) => (
        <g key={`${form.tone}-${index}`}>
          <FormShape form={form} press />
          <FormShape form={form} press={false} />
        </g>
      ))}
    </svg>
  );
}

/* ---------- the daily-seal catalogue (name + composition) ---------- */
export const SEAL_NAMES: Record<SealVariant, string> = {
  row: 'En ligne',
  stack: 'La colonne',
  nested: 'En abyme',
  quad: 'Le quatuor',
  orbit: "L'orbite",
  frieze: 'La frise',
};

/* Kept in step with `app/services/seals.py::SEAL_CYCLE` (a backend test reads
   this line), so the server's calendar and this component press the same seal. */
const SEAL_CYCLE: SealVariant[] = ['row', 'stack', 'nested', 'quad', 'orbit', 'frieze'];

export function isSealVariant(value: unknown): value is SealVariant {
  return typeof value === 'string' && (SEAL_CYCLE as string[]).includes(value);
}

/** Deterministic seal variant for an edition number, so a given day's seal is stable. */
export function sealForEdition(no: number): { variant: SealVariant; name: string } {
  const variant = SEAL_CYCLE[((no % SEAL_CYCLE.length) + SEAL_CYCLE.length) % SEAL_CYCLE.length];
  return { variant, name: SEAL_NAMES[variant] };
}

/** «Nº 47 · 22 sept.» — the seal's lower line. */
export function sealCaption(no?: number | null, date?: string | null): string {
  return [no != null ? `Nº ${no}` : '', date || ''].filter(Boolean).join(' · ');
}

/* ---------- WP-S7: one ring per rule held today ----------
   Rings are filled annuli (an even-odd path, never a stroke) in the reward
   yellow, outside the disc, in a box whose unit is the disc's radius (100).
   At most SEAL_MAX_RINGS are drawn; the accessible name says the real count. */
export const SEAL_MAX_RINGS = 4;
const RING_FIRST = 106;
const RING_PITCH = 9;
const RING_WIDTH = 4.5;

function annulus(inner: number, outer: number): string {
  const circle = (r: number, sweep: 0 | 1) =>
    `M ${-r},0 a ${r},${r} 0 1,${sweep} ${2 * r},0 a ${r},${r} 0 1,${sweep} ${-2 * r},0 Z`;
  return `${circle(outer, 0)} ${circle(inner, 1)}`;
}

/** The ring paths for `count` held rules (capped). Pure: a test reads it. */
export function sealRingPaths(count: number): string[] {
  const n = Math.max(0, Math.min(SEAL_MAX_RINGS, Math.floor(Number(count) || 0)));
  return Array.from({ length: n }, (_, index) => {
    const inner = RING_FIRST + index * RING_PITCH;
    return annulus(inner, inner + RING_WIDTH);
  });
}

function SealRings({ count }: { count: number }) {
  const paths = sealRingPaths(count);
  if (!paths.length) return null;
  return (
    <svg className="av2-seal__rings" viewBox="-140 -140 280 280" aria-hidden="true" focusable="false">
      {paths.map((d, index) => (
        <path key={index} className="av2-seal__ring" d={d} fillRule="evenodd" style={{ animationDelay: `${0.45 + index * 0.12}s` }} />
      ))}
    </svg>
  );
}

/* ============================================================
   THE SEAL — WP-D4, rebuilt in the av2 language (owner, 2026-09-22).
   A card-face disc on the large press (0 8px 0 --av2-line-2), no ink
   border and no offset shadow; the text around it is sentence case,
   Instrument Sans 600 in --av2-muted; the centre is a paper well
   holding the logo's four shapes. Styles: `styles/atelier-v2.css`
   (`.av2-seal`), so it must render inside an `.av2` root.
   `stamp` presses it once; Reduce Motion removes the press.
   ============================================================ */
export function Seal({
  variant = 'row',
  no,
  date = '',
  stamp = false,
  size = 'md',
  tone = 'ink',
  label,
  rings = 0,
  ringsLabel,
}: {
  variant?: SealVariant;
  no?: number | null;
  date?: string;
  stamp?: boolean;
  size?: 'md' | 'lg';
  tone?: 'ink' | 'gilt';
  /** Accessible name; defaults to «Sceau Nº 47 · 22 sept.». */
  label?: string;
  /** WP-S7: rules held today — one ring each around the disc. */
  rings?: number;
  /** WP-S7: the rings' accessible words («2 rings: rules held today»). */
  ringsLabel?: string | null;
}) {
  const uid = useId().replace(/:/g, '');
  const caption = sealCaption(no, date);
  const ringCount = Math.max(0, Math.min(SEAL_MAX_RINGS, Math.floor(Number(rings) || 0)));
  const baseLabel = label || ['Sceau', caption].filter(Boolean).join(' ');
  return (
    <div
      className="av2-seal"
      data-size={size}
      data-tone={tone}
      data-stamp={stamp ? 'true' : undefined}
      data-variant={variant}
      data-rings={ringCount || undefined}
      role="img"
      aria-label={ringCount && ringsLabel ? `${baseLabel} · ${ringsLabel}` : baseLabel}
    >
      <div className="av2-seal__disc">
        <SealRings count={ringCount} />
        <svg className="av2-seal__words" viewBox="0 0 200 200" aria-hidden="true" focusable="false">
          <defs>
            <path id={`st${uid}`} d="M 22,100 A 78,78 0 0 1 178,100" />
            <path id={`sb${uid}`} d="M 12,100 A 88,88 0 0 0 188,100" />
          </defs>
          <text className="av2-seal__line" textAnchor="middle">
            <textPath href={`#st${uid}`} startOffset="50%">
              Atelier · le feuilleton
            </textPath>
          </text>
          {caption && (
            <text className="av2-seal__line" textAnchor="middle">
              <textPath href={`#sb${uid}`} startOffset="50%">
                {caption}
              </textPath>
            </text>
          )}
        </svg>
        <div className="av2-seal__well">
          <CoreForms variant={variant} />
        </div>
      </div>
    </div>
  );
}

export type SealMiniState = 'earned' | 'done' | 'relache' | 'today' | 'future' | 'missed' | 'empty';

/* compact collection seal — WP-D5's «Vos sceaux» grid.
   earned  a card disc on the small press (0 3px 0 --av2-line-2), the seal's four shapes
   done    a practised day with no seal (an early stop): the ink «done» square
   relache the yellow reward square in a dashed disc
   today   a dashed red disc
   future  a dotted disc
   missed  a flat disc in --av2-line (legacy `empty` reads the same) */
export function SealMini({
  no,
  variant = 'row',
  state = 'earned',
  label,
  caption,
}: {
  no?: number | null;
  variant?: SealVariant;
  state?: SealMiniState;
  /** Accessible name for the day. */
  label?: string;
  /** The line under the disc; defaults to «Nº 47» on an earned seal. */
  caption?: string | null;
  /** Legacy prop, ignored: the av2 seal has one tone. */
  tone?: 'ink' | 'gilt';
}) {
  const shown = state === 'empty' ? 'missed' : state;
  const line = caption !== undefined ? caption : shown === 'earned' && no != null ? `Nº ${no}` : '';
  return (
    <div className="av2-seal-mini" data-state={shown} role={label ? 'img' : undefined} aria-label={label}>
      <div className="av2-seal-mini__disc">
        {shown === 'earned' && (
          <div className="av2-seal-mini__well">
            <CoreForms variant={variant} />
          </div>
        )}
        {(shown === 'done' || shown === 'relache') && (
          <svg className="av2-seal-mini__token" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
            <rect
              className={cn('av2-seal__form', 'is-press', shown === 'done' ? 'av2-seal__form--block' : 'av2-seal__form--square')}
              x="12"
              y="14"
              width="16"
              height="16"
              rx="2"
            />
            <rect
              className={cn('av2-seal__form', shown === 'done' ? 'av2-seal__form--block' : 'av2-seal__form--square')}
              x="12"
              y="12"
              width="16"
              height="16"
              rx="2"
            />
          </svg>
        )}
      </div>
      {line ? <div className="av2-seal-mini__no">{line}</div> : null}
    </div>
  );
}

/* ---------- per-exercise reactive form (drill scorekeeper) ---------- */
function ShapeFor({ shape }: { shape: 'circle' | 'square' | 'triangle' }) {
  if (shape === 'square') {
    return (
      <svg className="shape" viewBox="0 0 38 38" aria-hidden="true">
        <rect x="6" y="6" width="26" height="26" />
      </svg>
    );
  }
  if (shape === 'triangle') {
    return (
      <svg className="shape" viewBox="0 0 38 38" aria-hidden="true">
        <polygon points="19,5 34,32 4,32" />
      </svg>
    );
  }
  return (
    <svg className="shape" viewBox="0 0 38 38" aria-hidden="true">
      <circle cx="19" cy="19" r="15" />
    </svg>
  );
}

export function ReactForm({
  shape = 'circle',
  state = 'neutral',
}: {
  shape?: 'circle' | 'square' | 'triangle';
  state?: 'neutral' | 'grin' | 'sad';
}) {
  return (
    <div className={cn('rf', shape)} data-state={state}>
      <ShapeFor shape={shape} />
      <div className="mk" aria-hidden="true">
        <span className="eye l" />
        <span className="eye r" />
        <svg className="grin" viewBox="-8 -4 16 8">
          <path d="M-5 -1 Q0 3.4 5 -1" />
        </svg>
        <svg className="sad" viewBox="-8 -4 16 8">
          <path d="M-5 2 Q0 -2.6 5 2" />
        </svg>
      </div>
    </div>
  );
}

/* ---------- the logo token (minted by a perfect screen) ---------- */
export function CoreLogo() {
  return (
    <svg viewBox="0 0 62 62" aria-hidden="true">
      <rect className="shp c-block" x="8" y="8" width="18" height="18" />
      <circle className="shp c-circle" cx="45" cy="17" r="9" />
      <rect className="shp c-square" x="8" y="36" width="18" height="18" />
      <polygon className="shp c-tri" points="45,36 56,54 34,54" />
    </svg>
  );
}

export function LogoToken({ pop = false, size }: { pop?: boolean; size?: 'sm' }) {
  return (
    <div className={cn('logo-token', size, pop && 'pop')}>
      <div className="lt">
        <CoreLogo />
      </div>
    </div>
  );
}

/* ---------- restrained confetti (off under reduced motion) ---------- */
export function Confetti({ count = 22 }: { count?: number }) {
  const inks = ['var(--blue)', 'var(--yellow)', 'var(--red)', 'var(--ink)'];
  const kinds = ['sq', 'ci', 'tri'];
  const pieces = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const k = kinds[i % 3];
        const c = inks[i % 4];
        return {
          k,
          c,
          left: Math.round(6 + Math.random() * 88),
          dur: (0.9 + Math.random() * 0.7).toFixed(2),
          del: (Math.random() * 0.25).toFixed(2),
          r: Math.round(140 + Math.random() * 260) * (i % 2 ? 1 : -1),
        };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [count],
  );
  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((p, i) => (
        <i
          key={i}
          className={p.k}
          style={
            {
              left: `${p.left}%`,
              color: p.c,
              background: p.k === 'tri' ? undefined : p.c,
              '--dur': `${p.dur}s`,
              '--del': `${p.del}s`,
              '--r': `${p.r}deg`,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
