import { useId, useMemo, type CSSProperties } from 'react';
import { cn } from '@/lib/utils';

export type SealVariant = 'row' | 'stack' | 'nested' | 'quad' | 'orbit' | 'frieze';

/* ---------- the forms locked into an emblem (varies per day) ---------- */
const CORE_SHAPES: Record<SealVariant, JSX.Element> = {
  row: (
    <>
      <circle className="shp c-circle" cx="40" cy="62" r="18" />
      <rect className="shp c-square" x="48" y="44" width="34" height="34" />
      <polygon className="shp c-tri" points="80,44 100,78 60,78" />
    </>
  ),
  stack: (
    <>
      <polygon className="shp c-tri" points="58,14 78,50 38,50" />
      <rect className="shp c-square" x="40" y="46" width="36" height="36" />
      <circle className="shp c-circle" cx="58" cy="88" r="17" />
    </>
  ),
  nested: (
    <>
      <circle className="shp c-circle" cx="58" cy="58" r="36" />
      <polygon className="shp c-tri" points="58,32 82,80 34,80" />
      <rect className="shp c-square" x="49" y="52" width="18" height="18" />
    </>
  ),
  quad: (
    <>
      <rect className="shp c-block" x="30" y="30" width="24" height="24" />
      <circle className="shp c-circle" cx="74" cy="42" r="13" />
      <rect className="shp c-square" x="30" y="62" width="24" height="24" />
      <polygon className="shp c-tri" points="74,62 88,86 60,86" />
    </>
  ),
  // creative additions — more daily variety, same house inks.
  orbit: (
    <>
      <circle className="shp c-circle" cx="58" cy="58" r="20" />
      <rect className="shp c-square" x="22" y="22" width="18" height="18" />
      <polygon className="shp c-tri" points="84,30 100,58 68,58" />
      <rect className="shp c-block" x="52" y="84" width="16" height="16" />
    </>
  ),
  frieze: (
    <>
      <circle className="shp c-circle" cx="26" cy="58" r="13" />
      <rect className="shp c-square" x="45" y="45" width="26" height="26" />
      <polygon className="shp c-tri" points="80,45 100,71 60,71" />
    </>
  ),
};

export function CoreForms({ variant = 'row' }: { variant?: SealVariant }) {
  return (
    <svg viewBox="0 0 116 116" aria-hidden="true">
      {CORE_SHAPES[variant] || CORE_SHAPES.row}
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

const SEAL_CYCLE: SealVariant[] = ['row', 'stack', 'nested', 'quad', 'orbit', 'frieze'];

/** Deterministic seal variant for an edition number, so a given day's seal is stable. */
export function sealForEdition(no: number): { variant: SealVariant; name: string } {
  const variant = SEAL_CYCLE[((no % SEAL_CYCLE.length) + SEAL_CYCLE.length) % SEAL_CYCLE.length];
  return { variant, name: SEAL_NAMES[variant] };
}

/* ============================================================
   THE SEAL — the printer's-colophon pressmark. The one place the
   ink-block shadow belongs. Variable + collectible by day.
   ============================================================ */
export function Seal({
  variant = 'row',
  no,
  date = '',
  stamp = false,
  size = 'md',
  tone = 'ink',
}: {
  variant?: SealVariant;
  no?: number;
  date?: string;
  stamp?: boolean;
  size?: 'md' | 'lg';
  tone?: 'ink' | 'gilt';
}) {
  const uid = useId().replace(/:/g, '');
  const ringLabel =
    no != null ? `Nº ${no}${date ? `  ·  ${date.toUpperCase()}` : ''}` : date ? date.toUpperCase() : '';
  return (
    <div className={cn('seal', size, tone === 'gilt' && 'gilt', stamp && 'stamp')}>
      <div className="seal-medallion">
        <svg className="ring" viewBox="0 0 200 200" aria-hidden="true">
          <defs>
            <path id={`rt${uid}`} d="M 20,100 A 80,80 0 0 1 180,100" />
            <path id={`rb${uid}`} d="M 23,100 A 77,77 0 0 0 177,100" />
          </defs>
          <circle cx="100" cy="100" r="66" fill="none" stroke="var(--ink)" strokeWidth="1.5" />
          <circle cx="13.5" cy="100" r="2.6" fill="var(--ink)" />
          <circle cx="186.5" cy="100" r="2.6" fill="var(--ink)" />
          <text fontSize="11.5" textAnchor="middle">
            <textPath href={`#rt${uid}`} startOffset="50%">ATELIER — LE FEUILLETON</textPath>
          </text>
          <text className="fine" textAnchor="middle">
            <textPath href={`#rb${uid}`} startOffset="50%">{ringLabel}</textPath>
          </text>
        </svg>
        <div className="core">
          <CoreForms variant={variant} />
        </div>
      </div>
    </div>
  );
}

/* compact archive seal — forms in a ring, Nº beneath */
export function SealMini({
  no,
  variant = 'row',
  state = 'earned',
  tone = 'ink',
}: {
  no?: number;
  variant?: SealVariant;
  state?: 'earned' | 'future' | 'empty';
  tone?: 'ink' | 'gilt';
}) {
  return (
    <div className={cn('seal-mini', state, tone === 'gilt' && 'gilt')}>
      <div className="disc">
        {state === 'earned' && (
          <div className="core">
            <CoreForms variant={variant} />
          </div>
        )}
      </div>
      <div className="no">{state === 'earned' ? `Nº ${no}` : state === 'future' ? '—' : ''}</div>
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
