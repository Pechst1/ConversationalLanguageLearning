/**
 * Les appels — the ringing card on the Atelier home.
 *
 * Asks `/appels/today` once per visit. A ringing call shows «Romy t'appelle» with
 * «Décrocher» (opens /appel) and «Plus tard» (the voicemail); a missed call offers
 * its message once. Nothing while the feature is off, there is no call, or the
 * request fails: the home never waits on it.
 */

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

import { Action } from '@/components/atelier-v2/ui';
import { appelsClient, appelsCopy, callerPortrait, type Call } from '@/lib/appels-api';

export function IncomingCall({ language }: { language: string }) {
  const router = useRouter();
  const copy = appelsCopy(language);
  const [call, setCall] = useState<Call | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    appelsClient()
      .today()
      .then((found) => {
        if (alive) setCall(found);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  if (!call || (call.status !== 'ringing' && call.status !== 'missed')) return null;
  const portrait = callerPortrait(call);
  const missed = call.status === 'missed';

  return (
    <section className="ap-card" data-status={call.status} aria-live="polite">
      <div className="ap-card__face" data-ringing={missed ? undefined : ''}>
        {portrait ? <img src={portrait} alt="" /> : null}
      </div>
      <div className="ap-card__body">
        <p className="ap-card__title">{missed ? copy.voicemail_title(call.caller.name) : copy.calling(call.caller.name)}</p>
        {!missed && <p className="ap-card__hint">{copy.calling_hint}</p>}
        <div className="ap-card__actions">
          {missed ? (
            <Action tone="primary" inline onClick={() => void router.push('/appel')}>
              {copy.play}
            </Action>
          ) : (
            <>
              <Action tone="primary" inline onClick={() => void router.push('/appel')}>
                {copy.answer}
              </Action>
              <Action
                inline
                pending={busy}
                pendingLabel={copy.decline}
                onClick={() => {
                  setBusy(true);
                  appelsClient()
                    .decline(call.id)
                    .then(setCall)
                    .catch(() => undefined)
                    .finally(() => setBusy(false));
                }}
              >
                {copy.decline}
              </Action>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

export default IncomingCall;
