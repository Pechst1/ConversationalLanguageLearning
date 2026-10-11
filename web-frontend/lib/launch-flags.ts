import launchFlags from '../launch-flags.json';

export const STORY_FEATURE_VISIBLE: boolean = Boolean(launchFlags.storyFeatureVisible);

/** WP-158: this device's override of `spokenReply` (`on`/`off`), for the owner's phone. */
export const SPOKEN_REPLY_STORAGE_KEY = 'atelier.spokenReply';

/**
 * WP-158 «Parler» in the story reply. Off by default (`spokenReply` in
 * `launch-flags.json`, or `atelier.spokenReply` = `on` on one device). The
 * server must also say `spoken_reply` on the prompt
 * (`ATELIER_SPOKEN_REPLY_ENABLED`) before the control appears: the build decides
 * the device ships it, the server decides the deployment pays for it. Read at
 * call time so a test (or a device toggle) can change it.
 */
export function spokenReplyLaunched(): boolean {
  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage?.getItem(SPOKEN_REPLY_STORAGE_KEY);
      if (stored === 'on') return true;
      if (stored === 'off') return false;
    } catch {
      /* storage refused: the build default stays */
    }
  }
  return Boolean((launchFlags as Record<string, unknown>).spokenReply);
}
