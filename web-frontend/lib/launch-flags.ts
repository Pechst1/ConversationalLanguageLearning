import launchFlags from '../launch-flags.json';

export const STORY_FEATURE_VISIBLE: boolean = Boolean(launchFlags.storyFeatureVisible);

/**
 * Le Quartier: today's scene played in a walkable 3D Paris (`/quartier`). Launched (owner,
 * 17 Nov; P12): `quartierVisible` is on in launch-flags.json, so every build serves the page and
 * Home offers it beside the page. Switching the flag off closes the door again in a production
 * build; `NEXT_PUBLIC_QUARTIER_VISIBLE=true` then opens it on one build only, which a release
 * refuses (`scripts/native-export-policy.mjs`), as it refuses a release without the page while
 * the flag is on.
 */
export const QUARTIER_VISIBLE: boolean =
  Boolean((launchFlags as Record<string, unknown>).quartierVisible) || process.env.NEXT_PUBLIC_QUARTIER_VISIBLE === 'true';

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

/** This device's override of `grammarPilot` (`on`/`off`), for the owner's phone. */
export const GRAMMAR_PILOT_STORAGE_KEY = 'atelier.grammarPilot';

/**
 * The grammar pilot (owner's choice of 9 November 2026): Le Déclic on the Forge's choice, typed and
 * spot drills, and Le Montage on the rules that have a script (`lib/rule-montage.ts`). A development build has it, so the walk plays it; a production build waits
 * for `grammarPilot` in `launch-flags.json`, or `atelier.grammarPilot` = `on` on one device. Read at
 * call time so a device toggle or a test can change it.
 */
export function grammarPilotOn(): boolean {
  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage?.getItem(GRAMMAR_PILOT_STORAGE_KEY);
      if (stored === 'on') return true;
      if (stored === 'off') return false;
    } catch {
      /* storage refused: the build default stays */
    }
  }
  return Boolean((launchFlags as Record<string, unknown>).grammarPilot) || process.env.NODE_ENV === 'development';
}
