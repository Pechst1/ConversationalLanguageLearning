/**
 * S4 stage 2 — the one error screen: the error boundary, 404 and 500 draw it.
 *
 * A `StateBlock` in the screen's chrome language (the learner's own up to A2,
 * French from B1, as every other chrome), one sentence, one way back to La Une
 * and, after a crash, the event id the silent reporter sent with the report.
 *
 * The language is read from the cache the profile load left behind, never from
 * the network: an error screen must not depend on the API that may have failed.
 */
import React from 'react';
import { useRouter } from 'next/router';

import { AtelierV2Root, StateBlock } from '@/components/atelier-v2/ui';
import { appErrorCopy, errorToState, HOME_HREF, type AppErrorKind } from '@/lib/app-errors';
import { chromeLanguage } from '@/lib/language-rule';
import { readLearnerLanguage, readLearnerLevel } from '@/lib/learner-language';

export function useErrorScreenLanguage(): string {
  // `en` on the server and the first client render, then the cached language.
  const [language, setLanguage] = React.useState<string>('en');
  React.useEffect(() => setLanguage(chromeLanguage(readLearnerLanguage(), readLearnerLevel())), []);
  return language;
}

type ErrorScreenProps = {
  /** `crashed` is the boundary's own; the rest are `errorToState` kinds. */
  kind: AppErrorKind | 'crashed';
  eventId?: string | null;
  /** After a crash the whole app is reloaded at La Une, so nothing broken is kept. */
  reload?: boolean;
};

export function ErrorScreen({ kind, eventId, reload = false }: ErrorScreenProps) {
  const router = useRouter();
  const language = useErrorScreenLanguage();
  const copy = appErrorCopy(language);
  const text = kind === 'crashed' ? copy.crashed : errorToState(kind, language);
  const goHome = () => {
    if (reload || !router) window.location.assign(HOME_HREF);
    else void router.push(HOME_HREF);
  };
  return (
    <AtelierV2Root language={language} className="app-error-screen">
      <StateBlock
        tone="error"
        title={text.title}
        body={(
          <>
            {text.body}
            {eventId && (
              <>
                <br />
                <span className="av2-label" data-event-id={eventId}>{copy.reference} · {eventId}</span>
              </>
            )}
          </>
        )}
        action={{ label: copy.actions.home, onSelect: goHome, tone: 'primary' }}
      />
    </AtelierV2Root>
  );
}

export default ErrorScreen;
