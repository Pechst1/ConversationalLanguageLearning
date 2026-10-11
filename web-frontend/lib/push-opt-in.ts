/**
 * WP-80 — when to ask for push, and what to say. Pure: no Capacitor, no
 * network, so `node --test lib/push-opt-in.test.js` covers it.
 *
 * The OS permission prompt is asked once, and only after a moment that earns
 * it: the learner has just finished a day. Before the OS dialog there is one
 * screen in the learner's language, with a face on it («Marin vous prévient
 * quand la suite arrive»). Only «Oui» triggers the OS prompt; «Plus tard» is
 * remembered, and the pre-prompt does not come back — the Réglages toggle is
 * where a learner changes their mind.
 */

export type PushCapability = 'native' | 'web' | 'none';
/** Normalised across Capacitor (`prompt-with-rationale`) and the browser (`default`). */
export type PushPermission = 'prompt' | 'granted' | 'denied' | 'unknown';
export type PushOptInAnswer = 'yes' | 'later';
export type PushOptInLanguage = 'en' | 'de' | 'fr';

export const PUSH_OPT_IN_STORAGE_KEY = 'atelier:push-opt-in:v1';
/** The key the pre-WP-80 séance prompt wrote. A device that saw it was asked. */
export const LEGACY_NATIVE_PROMPT_KEY = 'pilot:native-push-prompted:v1';

export function normalizePermission(value: unknown): PushPermission {
  switch (value) {
    case 'prompt':
    case 'prompt-with-rationale':
    case 'default':
      return 'prompt';
    case 'granted':
      return 'granted';
    case 'denied':
      return 'denied';
    default:
      return 'unknown';
  }
}

export type OptInInputs = {
  /** The journey is `completed` or `ended_early` and its recap is on screen. */
  dayFinished: boolean;
  capability: PushCapability;
  permission: PushPermission;
  /** A remembered answer on this device, or `null`. */
  answered: PushOptInAnswer | null;
};

/**
 * Offer the pre-prompt only when there is something to ask: a finished day, a
 * build that can deliver a push, an OS that has not been asked, and a learner
 * who has not answered us already.
 */
export function shouldOfferPushOptIn(inputs: OptInInputs): boolean {
  return (
    inputs.dayFinished
    && inputs.capability !== 'none'
    && inputs.permission === 'prompt'
    && inputs.answered === null
  );
}

type StorageLike = Pick<Storage, 'getItem' | 'setItem'> | null | undefined;

export function readOptInAnswer(storage: StorageLike): PushOptInAnswer | null {
  try {
    if (!storage) return null;
    const value = storage.getItem(PUSH_OPT_IN_STORAGE_KEY);
    if (value === 'yes' || value === 'later') return value;
    if (storage.getItem(LEGACY_NATIVE_PROMPT_KEY) === 'true') return 'yes';
  } catch {
    // Private mode or blocked storage: behave as "not answered". The OS
    // permission state still stops a second system dialog.
  }
  return null;
}

export function rememberOptInAnswer(storage: StorageLike, answer: PushOptInAnswer): void {
  try {
    storage?.setItem(PUSH_OPT_IN_STORAGE_KEY, answer);
  } catch {
    // Nothing to do: the answer lives for this page load only.
  }
}

export type PushOptInCopy = {
  line: string;
  yes: string;
  later: string;
  /** Screen-reader label of the card. */
  label: string;
};

/** One card, one language: the learner's. The character's name is a name. */
export function pushOptInCopy(language: string | null | undefined, characterName = 'Marin'): PushOptInCopy {
  const name = characterName.trim() || 'Marin';
  switch ((language || 'en').slice(0, 2).toLowerCase()) {
    case 'fr':
      return {
        line: `${name} vous prévient quand la suite arrive.`,
        yes: 'Oui',
        later: 'Plus tard',
        label: 'Notifications',
      };
    case 'de':
      return {
        line: `${name} sagt dir Bescheid, wenn es weitergeht.`,
        yes: 'Ja',
        later: 'Später',
        label: 'Mitteilungen',
      };
    default:
      return {
        line: `${name} lets you know when the story continues.`,
        yes: 'Yes',
        later: 'Later',
        label: 'Notifications',
      };
  }
}
