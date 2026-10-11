/**
 * «Le bureau» (WP-121/122 follow-up) — the DESK step: one of the Revue's other desks,
 * dealt after the ending on an ordinary day. Advanced, never answered here: each desk
 * grades on its own routes, and «Passer» / the desk's own end continue the day.
 *
 *   relecture   `CarteRelecture` with the client's `relectureAnswer` (a pair already
 *               stored from La Carte is fetched first and shown);
 *   radio       the Radio bulletin (`RadioBulletin`): listen first, read, the dictée,
 *               «C'est entendu» continues the day;
 *   correcteur  `CorrecteurDesk` on a new draft of the step's dossier; «Dans le Relevé»
 *               at the result continues the day instead of leaving it.
 *
 * A desk that cannot open (the flag went off, the offer was taken) says so in one quiet
 * line and keeps «Continuer» enabled: a desk is an offer, never a gate.
 */

import React, { useCallback, useEffect, useState } from 'react';

import { Action, StateBlock } from '@/components/atelier-v2/ui';
import { CarteRelecture, carteCopy } from '@/components/carte';
import { CorrecteurDesk, correcteurCopy, normalizeLanguage } from '@/components/correcteur';
import { RadioBulletin } from '@/components/radio';
import { carteClient } from '@/lib/carte-api';
import type { RelecturePair } from '@/lib/carte-types';
import { correcteurClient, type CorrecteurClient } from '@/lib/correcteur-api';
import type { CrDraft } from '@/lib/correcteur-types';
import { radioClient, type RadioClient } from '@/lib/radio-api';
import type { RadioBulletin as RadioBulletinWire, RadioLanguage } from '@/lib/radio-types';
import type { ControlLanguage, DeskStep } from '@/types/daily-journey';

import { deskCopy, deskKicker, deskStepView } from './desk-step-model';

export type DeskStepViewProps = {
  step: DeskStep;
  busy: boolean;
  onContinue: () => void;
  language?: ControlLanguage | null;
  /** Injection seams (tests, the gallery). */
  clients?: {
    relecturePair?: (sessionId: string) => Promise<RelecturePair | null>;
    relectureAnswer?: (sessionId: string, answerFr: string) => Promise<RelecturePair>;
    radio?: RadioClient;
    correcteur?: CorrecteurClient;
  };
};

type Loaded =
  | { kind: 'loading' }
  | { kind: 'unavailable' }
  | { kind: 'relecture'; pair: RelecturePair | null }
  | { kind: 'radio'; bulletin: RadioBulletinWire; client: RadioClient }
  | { kind: 'correcteur'; draft: CrDraft; client: CorrecteurClient };

export function DeskStepView({ step, busy, onContinue, language, clients }: DeskStepViewProps) {
  const view = deskStepView(step);
  const copy = deskCopy(language);
  const chrome: RadioLanguage = language === 'en' || language === 'de' ? language : 'fr';
  const [loaded, setLoaded] = useState<Loaded>({ kind: 'loading' });

  useEffect(() => {
    let alive = true;
    const settle = (next: Loaded) => alive && setLoaded(next);
    (async () => {
      try {
        if (view.desk === 'relecture') {
          const pair = await (clients?.relecturePair ?? carteClient().relecturePair)(view.offer.sessionId).catch(() => null);
          settle({ kind: 'relecture', pair });
        } else if (view.desk === 'radio') {
          const client = clients?.radio ?? radioClient();
          settle({ kind: 'radio', bulletin: await client.bulletin(view.dossierId), client });
        } else if (view.desk === 'correcteur') {
          const client = clients?.correcteur ?? correcteurClient();
          settle({ kind: 'correcteur', draft: await client.draft(view.dossierId), client });
        } else {
          settle({ kind: 'unavailable' });
        }
      } catch {
        settle({ kind: 'unavailable' });
      }
    })();
    return () => {
      alive = false;
    };
    // One load per step: the step's id names its target.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step.id]);

  const answer = useCallback(
    (answerFr: string) => {
      if (view.desk !== 'relecture') return Promise.reject(new Error('not a relecture'));
      return (clients?.relectureAnswer ?? carteClient().relectureAnswer)(view.offer.sessionId, answerFr);
    },
    [clients, view],
  );

  let body: React.ReactNode;
  if (loaded.kind === 'loading') {
    body = (
      <p className="av2-label" role="status" aria-busy="true">
        {copy.loading}
      </p>
    );
  } else if (loaded.kind === 'relecture' && view.desk === 'relecture') {
    body = <CarteRelecture offer={view.offer} pair={loaded.pair} copy={carteCopy(chrome)} onAnswer={answer} onBack={onContinue} />;
  } else if (loaded.kind === 'radio') {
    body = (
      <RadioBulletin
        bulletin={loaded.bulletin}
        client={loaded.client}
        language={chrome}
        onExit={onContinue}
        onHeard={() => onContinue()}
      />
    );
  } else if (loaded.kind === 'correcteur') {
    const draft = loaded.draft;
    body = (
      <CorrecteurDesk
        draft={draft}
        copy={correcteurCopy(normalizeLanguage(chrome))}
        onSubmit={(marks) => loaded.client.marks(draft.id, marks)}
        onReleve={onContinue}
      />
    );
  } else {
    body = <StateBlock tone="empty" title={copy.unavailable} />;
  }

  return (
    <section className="av2-desk" data-desk={view.desk} aria-label={deskKicker(view, language)}>
      <header className="av2-desk__head">
        <p className="av2-label" lang="fr">
          {deskKicker(view, language)}
        </p>
        {view.desk !== 'none' && <p className="av2-body">{copy.lead[view.desk]}</p>}
      </header>
      {body}
      <div className="av2-desk__foot">
        <Action tone={loaded.kind === 'unavailable' ? 'primary' : 'quiet'} inline={loaded.kind !== 'unavailable'} disabled={busy} onClick={onContinue}>
          {loaded.kind === 'unavailable' ? copy.done : copy.skip}
        </Action>
      </div>
    </section>
  );
}

export default DeskStepView;
