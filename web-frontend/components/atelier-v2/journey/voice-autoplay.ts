/**
 * WP-91 «Les voix» — a reply speaks once, by itself, as it arrives.
 *
 * The rule, kept pure so it can be pinned by a test:
 *  * only when «Les personnages parlent à voix haute» is on;
 *  * only once the reply has finished typing in (Reduced Motion shows it whole
 *    at once, so it speaks at once);
 *  * **never twice for the same line** in a session — a re-render, a remount,
 *    a step revisited, a reconnect replaying the result: the ledger has it.
 *
 * A tap on the face always speaks; this only governs speaking unasked.
 */

export type AutoplayLedger = {
  /** True the first time a key is claimed, false forever after. */
  claim: (key: string) => boolean;
  has: (key: string) => boolean;
};

export function createAutoplayLedger(limit = 400): AutoplayLedger {
  const played = new Set<string>();
  return {
    claim(key) {
      if (!key || played.has(key)) return false;
      played.add(key);
      if (played.size > limit) {
        const oldest = played.values().next().value;
        if (oldest !== undefined) played.delete(oldest);
      }
      return true;
    },
    has: (key) => played.has(key),
  };
}

/** The app's one ledger: a line played on one screen is not replayed on the next. */
export const sessionAutoplayLedger: AutoplayLedger = createAutoplayLedger();

/** The typed-in text has caught up with the reply. */
export function replyFinishedTyping(reply: string, typed: string): boolean {
  const whole = reply.trim();
  return whole.length > 0 && typed.trim().length >= whole.length;
}

/** A line's autoplay identity: where it was said, and what. */
export function autoplayKey(scope: string | null | undefined, lineKey: string, text: string): string {
  return `${scope || ''}|${lineKey}|${text.trim()}`;
}

/**
 * Speak this line now? Claims the key when the answer is yes, so asking again
 * — the next render, the next mount — is always no.
 */
export function shouldAutoplay({
  enabled,
  ready,
  key,
  ledger = sessionAutoplayLedger,
}: {
  enabled: boolean;
  ready: boolean;
  key: string | null | undefined;
  ledger?: AutoplayLedger;
}): boolean {
  if (!enabled || !ready || !key) return false;
  return ledger.claim(key);
}
