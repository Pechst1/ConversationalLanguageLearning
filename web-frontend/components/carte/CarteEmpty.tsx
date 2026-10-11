/**
 * WP-120 phase C · the empty map: no Papier filed yet. One sentence of promise and
 * a quiet way to the Papier (no primary press: the map is an archive).
 */

import React from 'react';

import { StateBlock } from '@/components/atelier-v2/ui';

import type { CarteCopy } from './carte-copy';

export function CarteEmpty({ copy, onOpenPapier }: { copy: CarteCopy; onOpenPapier?: () => void }) {
  return (
    <div className="carte-empty">
      <StateBlock
        tone="empty"
        title={copy.empty_title}
        body={copy.empty_body}
        action={onOpenPapier ? { label: copy.empty_action, onSelect: onOpenPapier, tone: 'secondary' } : undefined}
      />
    </div>
  );
}

export default CarteEmpty;
