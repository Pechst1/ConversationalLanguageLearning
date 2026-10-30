/**
 * One answer to «what if this picture does not load?» (#283).
 *
 * A painted plate can be missing (not painted yet, a stale URL, offline), and an
 * `<img>` that fails prints the browser's broken-image glyph, often in an empty
 * frame. Each surface used to write its own `failed` state, so each new thumbnail
 * could forget it (Home's «À la une» card did). A picture is printed through this
 * hook: spread `onError` on the `<img>`, and when `failed` the surface prints
 * nothing in its place (or its own drawing).
 *
 * The failure is remembered for the URL that failed, not for the component: a
 * different `src` (tomorrow's story in the same card) gets its own chance.
 */

import { useState } from 'react';

export function useImageFailed(src: string | null | undefined): { failed: boolean; onError: () => void } {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  return {
    failed: !src || failedSrc === src,
    onError: () => setFailedSrc(src || null),
  };
}
