/* Package O-2 — the gold leaf glyph (§3): filled when printed, dashed while à l'épreuve, faded when pulped. */

import React from 'react';

/** The gold leaf: the house mark's yellow square on its press; dashed while à l'épreuve. */
export function GoldGlyph({ state = 'settled', size = 14 }: { state?: 'settled' | 'pending' | 'void'; size?: number }) {
  return (
    <svg className="av2-gold-glyph" data-state={state} width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      {state === 'settled' ? (
        <>
          <rect className="av2-gold-glyph__press" x="2" y="3.5" width="12" height="12" rx="2" />
          <rect className="av2-gold-glyph__face" x="2" y="1.5" width="12" height="12" rx="2" />
        </>
      ) : (
        <rect className="av2-gold-glyph__proof" x="2.75" y="2.25" width="10.5" height="10.5" rx="2" />
      )}
    </svg>
  );
}
