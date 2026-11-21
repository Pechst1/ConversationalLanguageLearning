/* Round 3 (owner, 2026-10-14) — «Fertig für heute».

   The day's last step, after the scene, the grammar and the words: the seal,
   one headline, what the day held (1 Szene · 15 Wörter · 12 Übungen; «2 Akte» on a
   day of acts, and under it the story's words read, Phase 2's number), tomorrow's
   open question (the line Home prints, `TomorrowLine`), and the troupe's curtain
   call over it. One ink button back to La Une. P7 (pilot, 17 Nov): no «Noch 5
   neue Wörter» and no «N words a day … sooner» line here any more (they came
   after every deck, endlessly); more words a day are offered in Settings.

   Reached before the day is done (an old link, a tap from the plan), it says
   which step comes next and opens it instead. */

import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { Action, AtelierV2Root, ShapeToken, Skeleton } from '@/components/atelier-v2/ui';
import { rewardView } from '@/components/atelier-v2/journey/journey-recap-model';
import { PushOptIn } from '@/components/atelier-v2/journey/PushOptIn';
import { tomorrowLine } from '@/components/atelier-v2/journey/season-return-model';
import { TomorrowLine } from '@/components/atelier-v2/journey/TomorrowLine';
import { Seal } from '@/components/ui/Seal';
import { GoldGlyph } from '@/components/gold/GoldGlyph';
import { GoldPill } from '@/components/gold/GoldPill';
import { useGold } from '@/lib/gold';
import { rimFraction, tirageLine } from '@/lib/gold-model';
import { emitCameo } from '@/lib/cameo';
import { castIdFor } from '@/lib/cast-faces';
import { daySessionCopy, sessionNextAction, storyReadLine, tallyStory } from '@/lib/day-session';
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
  // P7 (pilot, 17 Nov): no «N words a day … sooner» banner and no «Encore 5 nouveaux
  // mots» after the day; more words a day are chosen in Settings, where the pace is.
  // The same line Home's finished card prints; an early stop or a recap with no teaser has none.
  const tomorrow = session?.done ? tomorrowLine(journey?.recap) : null;
  // Phase 2 «Folge in Akten»: «2 Akte» on a day of acts, and the story's words read.
  const story = session ? tallyStory(session.tally, language) : null;
  const storyRead = session ? storyReadLine(session.tally, language) : null;
  const home = () => void router.push('/atelier');
  // O-2: le tirage du jour, where the switch shows l'or.
  const gold = useGold();
  const tirage = gold.visible && session?.done ? tirageLine(gold.view) : null;

  // #727: the screen speaks the envelope's language (`control_language`: French from B1).
  // Until the day is read the page does not know it, and the profile hook's first answer
  // is its hydration-safe `en`; printing the chrome then put «Done for today · Back to
  // La Une» on a B1 learner's French screen. So no words until the envelope answers; if
  // the day cannot be read at all, the learner's chrome language (`useChromeLanguage`) stands.
  if (!envelope && !failed) {
    return (
      <>
        <Head>
          <title>L’Atelier</title>
        </Head>
        <AtelierV2Root as="main" language={language} className="av2-fertig">
          <div className="av2-fertig__body" data-fertig="pending" aria-busy="true">
            <div className="av2-finish">
              <Skeleton height={120} radius={60} />
              <Skeleton height={40} />
            </div>
            <Skeleton height={88} />
            <div className="av2-fertig__spacer" />
            <Skeleton height={56} />
          </div>
        </AtelierV2Root>
      </>
    );
  }

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
                gold={tirage ? rimFraction(gold.view) : null}
                goldLabel={tirage}
              />
            )}
            <h1 className="av2-headline av2-headline--screen">{copy.finish_title}</h1>
            {tirage && (
              <div className="av2-gold-tirage" data-gold-tirage="">
                <GoldGlyph size={16} />
                <span>{tirage}</span>
                <GoldPill />
              </div>
            )}
          </div>
          {session && (
            <ul className="av2-tally" aria-label={copy.finish_title}>
              <li className="av2-tally__item">
                <ShapeToken kind="story" size="lg" />
                <span className="av2-tally__n">{story?.n ?? session.tally.scenes}</span>
                <span className="av2-tally__l">{story?.label ?? copy.tally_scene}</span>
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
          {storyRead && (
            <p className="av2-body av2-tally__story" data-story-words="">
              {storyRead}
            </p>
          )}
          <TomorrowLine line={tomorrow} language={language} />
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
            <Action tone="done" onClick={home}>
              {copy.back_home}
            </Action>
          )}
        </div>
      </AtelierV2Root>
    </>
  );
}
