/**
 * WP-80 — the push pre-prompt, after a finished day.
 *
 * One card: a face, one line in the learner's language («Marin vous prévient
 * quand la suite arrive»), «Oui» / «Plus tard». The OS dialog is asked only on
 * «Oui». Nothing renders until the device says there is something to ask, so
 * a build without push, a learner who already answered, or an OS that was
 * already asked sees nothing at all.
 */

import React from 'react';

import { Action, Surface } from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/onboarding/Portrait';
import { enablePush, pushAvailability, type PushAvailability } from '@/lib/push';
import {
  pushOptInCopy,
  readOptInAnswer,
  rememberOptInAnswer,
  shouldOfferPushOptIn,
  type PushOptInAnswer,
} from '@/lib/push-opt-in';

export type PushOptInProps = {
  /** The learner's language (the journey's control language). */
  language: string | null | undefined;
  /** Only a finished day earns the question. */
  dayFinished: boolean;
  characterId?: string;
  characterName?: string;
};

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function PushOptIn({
  language,
  dayFinished,
  characterId = 'marin_leveque',
  characterName = 'Marin',
}: PushOptInProps) {
  const [availability, setAvailability] = React.useState<PushAvailability | null>(null);
  const [answered, setAnswered] = React.useState<PushOptInAnswer | null>(() => readOptInAnswer(storage()));
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!dayFinished || answered !== null) return undefined;
    let alive = true;
    void pushAvailability().then((value) => {
      if (alive) setAvailability(value);
    });
    return () => {
      alive = false;
    };
  }, [dayFinished, answered]);

  if (
    !availability
    || !shouldOfferPushOptIn({
      dayFinished,
      capability: availability.capability,
      permission: availability.permission,
      answered,
    })
  ) {
    return null;
  }

  const copy = pushOptInCopy(language, characterName);
  const answer = async (value: PushOptInAnswer) => {
    if (busy) return;
    setBusy(true);
    rememberOptInAnswer(storage(), value);
    if (value === 'yes') await enablePush(availability.capability);
    setBusy(false);
    setAnswered(value);
  };

  return (
    <Surface className="journey-push-opt-in" aria-label={copy.label}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <CastPortrait characterId={characterId} name={characterName} mood="happy" size="md" />
        <p className="av2-body av2-body--lg" lang={(language || 'en').slice(0, 2)}>
          {copy.line}
        </p>
      </div>
      <div className="av2-recap__actions">
        <Action tone="primary" onClick={() => void answer('yes')} disabled={busy}>
          {copy.yes}
        </Action>
        <Action tone="secondary" onClick={() => void answer('later')} disabled={busy}>
          {copy.later}
        </Action>
      </div>
    </Surface>
  );
}

export default PushOptIn;
