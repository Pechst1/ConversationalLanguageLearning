/**
 * The plate band on a pin's card and on a quartier's: the painted plate in its frame,
 * or nothing when there is no plate or it does not load (#283: no broken-image glyph
 * in an empty frame). Both cards print it the same way, so it is one component.
 */

import React from 'react';

import { useImageFailed } from '@/lib/use-image-failed';

export function CartePlate({ url }: { url: string | null | undefined }) {
  const { failed, onError } = useImageFailed(url);
  if (failed || !url) return null;
  return (
    <div className="carte-card__plate" aria-hidden="true">
      {/* eslint-disable-next-line @next/next/no-img-element -- a static plate, already sized */}
      <img src={url} alt="" loading="lazy" decoding="async" onError={onError} />
    </div>
  );
}

export default CartePlate;
