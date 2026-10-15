/* Round 3 (owner, 2026-10-14) — «Fertig für heute».

   The day's last step, after the scene, the words and the grammar: the seal,
   one headline, what the day held (1 Szene · 20 Wörter · 12 Übungen), and the
   troupe's curtain call over it. One ink button back to La Une. Only now the
   quiet «Noch 10 Wörter»: continuing past the day's dose is the learner's choice.

   Reached before the day is done (an old link, a tap from the plan), it says
   which step comes next and opens it instead. */

import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { Action, AtelierV2Root, ShapeToken } from '@/components/atelier-v2/ui';
import { rewardView } from '@/components/atelier-v2/journey/journey-recap-model';
import { PushOptIn } from '@/components/atelier-v2/journey/PushOptIn';
import { Seal } from '@/components/ui/Seal';
import { emitCameo } from '@/lib/cameo';
import { castIdFor } from '@/lib/cast-faces';
import { daySessionCopy, sessionMore, sessionNextAction } from '@/lib/day-session';
import { useChromeLanguage } from '@/lib/learner-language';
import { dailyJourneyService } from '@/services/daily-journey';
import type { TodayEnvelope } from '@/types/daily-journey';

function CurtainCall({ lead }: { lead: string | null }) {
  useEffect(() => {
    emitCameo({ type: 'finale', lead });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function FertigPage() {
  const router = useRouter();
  const fallbackLanguage = useChromeLanguage();
  const [envelope, setEnvelope] = useState<TodayEnvelope | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    dailyJourneyService
      .today()
      .then((body) => live && setEnvelope(body))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, []);

  const language = envelope?.control_language ?? fallbackLanguage;
  const copy = daySessionCopy(language);
  const session = envelope?.session ?? null;
  const journey = envelope?.journey ?? null;
  const view = journey ? rewardView(journey, journey.recap ?? null, language) : null;
  const seal = session?.done && journey?.status === 'completed' ? view?.seal ?? null : null;
  const next = sessionNextAction(session, language);
  const more = sessionMore(session, language);
  const home = () => void router.push('/atelier');

  return (
    <>
      <Head>
        <title>{copy.finish_title} · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="av2-fertig" aria-label={copy.finish_title}>
        <div className="av2-fertig__body" data-fertig={session?.done ? 'done' : 'open'}>
          {session?.done && journey && (
            <CurtainCall lead={castIdFor(journey.scenario?.character_id, journey.scenario?.character_name)} />
          )}
          <div className="av2-finish">
            {seal && (
              <Seal
                stamp
                size="lg"
                variant={seal.variant}
                no={seal.no}
                date={seal.date ?? ''}
                rings={seal.rings}
                ringsLabel={seal.ringsLabel}
              />
            )}
            <h1 className="av2-headline av2-headline--screen">{copy.finish_title}</h1>
          </div>
          {session && (
            <ul className="av2-tally" aria-label={copy.finish_title}>
              <li className="av2-tally__item">
                <ShapeToken kind="story" size="lg" />
                <span className="av2-tally__n">{session.tally.scenes}</span>
                <span className="av2-tally__l">{copy.tally_scene}</span>
              </li>
              <li className="av2-tally__item">
                <ShapeToken kind="reward" size="lg" />
                <span className="av2-tally__n">{session.tally.words}</span>
                <span className="av2-tally__l">{copy.tally_words}</span>
              </li>
              <li className="av2-tally__item">
                <ShapeToken kind="action" size="lg" />
                <span className="av2-tally__n">{session.tally.exercises}</span>
                <span className="av2-tally__l">{copy.tally_exercises}</span>
              </li>
            </ul>
          )}
          {session?.done && journey && (
            <PushOptIn
              language={language}
              dayFinished
              characterId={journey.recap?.teaser?.character_id || undefined}
              characterName={journey.recap?.teaser?.character_name || undefined}
            />
          )}
          <div className="av2-fertig__spacer" />
          {next ? (
            <Action tone="primary" onClick={() => void router.push(next.href)}>
              {next.label}
              {next.meta ? <span className="av2-btn__meta">· {next.meta}</span> : null}
            </Action>
          ) : (
            <Action tone="done" onClick={home} disabled={!envelope && !failed}>
              {copy.back_home}
            </Action>
          )}
          {more && (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <button
                type="button"
                className="av2-btn av2-btn--quiet av2-btn--inline"
                onClick={() => void router.push(more.href)}
                data-more-words=""
              >
                {more.label}
              </button>
            </div>
          )}
        </div>
      </AtelierV2Root>
    </>
  );
}
