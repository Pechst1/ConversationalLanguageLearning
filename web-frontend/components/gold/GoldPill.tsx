/* Package O-2 — the counter pill, le grain and the ×2 (docs/ATELIER_GOLD_ECONOMY_PLAN.md §11, §14).

   Card ground, pill radius, the gold square, Instrument Sans 600 in tabular
   numerals. Each paying answer lifts a small square into the pill and rolls the
   digits once; a delayed recall splits the square in two and says «Tu t'en
   souvenais.». Tapping the pill opens «D'où vient ton or». Renders nothing
   while l'or is not on this learner's screen. Must sit inside an `.av2` root. */

import React, { useEffect, useRef, useState } from 'react';

import { pulseAppHaptic } from '@/lib/haptics';
import { isNativePlatform } from '@/lib/native-platform';
import { useGold } from '@/lib/gold';
import { GOLD_REMEMBERED_FR, GOLD_SHEET_TITLE_FR, type GoldGrain } from '@/lib/gold-model';
import { cn } from '@/lib/utils';

import { GoldGlyph } from './GoldGlyph';
import { GoldSheet } from './GoldSheet';

/** The digits, each rolling in on its own column (180 ms, 40 ms apart) when the number changes. */
function RollingNumber({ value }: { value: number }) {
  const digits = String(Math.max(0, Math.floor(value)));
  return (
    <span className="av2-gold-pill__n" aria-hidden="true">
      {digits.split('').map((digit, index) => (
        <span
          key={`${digits.length - index}-${digit}`}
          className="av2-gold-pill__digit"
          style={{ animationDelay: `${(digits.length - 1 - index) * 40}ms` }}
        >
          {digit}
        </span>
      ))}
    </span>
  );
}

function Grain({ grain }: { grain: GoldGrain }) {
  return (
    <span className="av2-gold-grain" data-delayed={grain.delayed || undefined} aria-hidden="true">
      <span className="av2-gold-grain__leaf" data-pending={grain.pending || undefined} />
      {grain.delayed && <span className="av2-gold-grain__leaf av2-gold-grain__leaf--twin" />}
    </span>
  );
}

export function GoldPill({ className }: { className?: string }) {
  const { view, grain, visible } = useGold();
  const [shownGrain, setShownGrain] = useState<GoldGrain | null>(null);
  const [open, setOpen] = useState(false);
  const lastGrain = useRef<number>(grain?.id ?? 0);

  useEffect(() => {
    if (!grain || grain.id === lastGrain.current) return undefined;
    lastGrain.current = grain.id;
    setShownGrain(grain);
    if (isNativePlatform()) {
      pulseAppHaptic('selection');
      if (grain.delayed) window.setTimeout(() => pulseAppHaptic('selection'), 140);
    }
    const timer = window.setTimeout(() => setShownGrain(null), grain.delayed ? 2400 : 900);
    return () => window.clearTimeout(timer);
  }, [grain]);

  if (!visible || !view) return null;
  const balance = view.balance ?? 0;
  const label = `${balance} feuilles d’or. ${GOLD_SHEET_TITLE_FR}`;

  return (
    <>
      <button
        type="button"
        className={cn('av2-gold-pill', className)}
        data-grain={shownGrain ? shownGrain.id : undefined}
        onClick={() => setOpen(true)}
        aria-label={label}
        data-gold-pill=""
      >
        <GoldGlyph />
        <RollingNumber value={balance} />
        {shownGrain && <Grain key={shownGrain.id} grain={shownGrain} />}
        {shownGrain && (
          <span className="av2-gold-pill__plus" key={`plus-${shownGrain.id}`} aria-hidden="true">
            +{shownGrain.amount}
          </span>
        )}
      </button>
      {shownGrain?.delayed && (
        <span className="av2-gold-remembered" role="status" key={`r-${shownGrain.id}`}>
          {GOLD_REMEMBERED_FR}
        </span>
      )}
      {/* The live region a screen reader hears; the motion itself is decorative. */}
      <span className="sr-only" role="status">
        {shownGrain ? `+${shownGrain.amount} feuilles d’or` : ''}
      </span>
      <GoldSheet open={open} onClose={() => setOpen(false)} view={view} />
    </>
  );
}
