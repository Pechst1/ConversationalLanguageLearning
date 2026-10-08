/**
 * WP-91 «Les personnages parlent à voix haute» — does a reply speak by itself?
 *
 * Stored exactly like the WP-76 «Sons» toggle (`lib/sound.ts`): one
 * `localStorage` key on this device, `on`/`off`, read after mount. The default
 * mirrors it too, for the same reasons:
 *   * **on in the iOS app** — a phone app in short sessions, the audio session
 *     is `ambient`, so the ringer switch silences it;
 *   * **off on the web** — a tab that starts talking in an office is a surprise.
 *
 * Independent of Reduce Motion (that setting is about movement, not sound) and
 * of «Sons» (the tones for right and wrong). Tapping a face always speaks,
 * whatever this says: the setting only governs speaking *unasked*.
 */

import { isNativePlatform } from '@/lib/native-platform';

export const VOICES_PREFERENCE_KEY = 'atelier.voices';

/** The default before the learner has chosen: on in the app, off on the web. */
export function defaultVoicesAloud(native: boolean = isNativePlatform()): boolean {
  return native;
}

export function readVoicesPreference(): boolean | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(VOICES_PREFERENCE_KEY);
    if (stored === 'on') return true;
    if (stored === 'off') return false;
  } catch {
    /* storage can be blocked; the default applies */
  }
  return null;
}

export function voicesAloud(): boolean {
  if (typeof window === 'undefined') return false;
  return readVoicesPreference() ?? defaultVoicesAloud();
}

export function setVoicesAloud(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(VOICES_PREFERENCE_KEY, enabled ? 'on' : 'off');
  } catch {
    /* storage can be blocked; the default applies on the next read */
  }
}
