/**
 * Le Quartier · today's episode played in a walkable Paris: the quai de Valmy at night in the
 * rain, Le Mistral, the cast (components/quartier, lib/quartier).
 *
 * The story is today's journey (`lib/quartier/journey-story.ts`). When it is a day the quarter
 * has blocking for (T1 days a and b) the scene plays here, every answer read by the engine; the
 * rest of the day (the words, the grammar) follows in the Feuilleton's own steps, over the quarter.
 * Any other day, or one left in the middle of its talk, is the Feuilleton's to read.
 *
 * Behind `quartierVisible` in launch-flags.json in a production build; a development build
 * always has it. The street is WebGL, so it never renders on the server.
 */
import dynamic from 'next/dynamic';
import Head from 'next/head';
import { useRouter } from 'next/router';
import React from 'react';

import { useDailyJourney } from '@/components/atelier-v2/journey/useDailyJourney';
import type { DailyJourneyController } from '@/components/atelier-v2/journey/useDailyJourney';
import { readAnswerMode } from '@/components/atelier-v2/journey/voice-answer';
import type { DayNote, QuartierDay } from '@/components/quartier/QuartierScreen';
import { useAppSession } from '@/lib/app-auth';
import { JOURNEY_RESUME_HREF } from '@/lib/journey-resume';
import { QUARTIER_VISIBLE } from '@/lib/launch-flags';
import { levelBand } from '@/lib/language-rule';
import { LEARNER_LANGUAGE_STORAGE_KEY, readLearnerLevel } from '@/lib/learner-language';
import { JourneyStory, stagedPageOf, todayOf } from '@/lib/quartier/journey-story';
import type { Today } from '@/lib/quartier/journey-story';
import type { Level, Native } from '@/lib/quartier/stage';
import { remainingSteps } from '@/services/daily-journey';
import type { JourneySnapshot } from '@/types/daily-journey';

const QuartierScreen = dynamic(() => import('@/components/quartier/QuartierScreen').then((m) => m.QuartierScreen), {
  ssr: false,
  loading: () => <div style={{ position: 'fixed', inset: 0, background: '#14110d' }} />,
});

/** The rest of the day, in the Feuilleton's own steps. */
const JourneySession = dynamic(() => import('@/components/atelier-v2/journey/JourneySession').then((m) => m.JourneySession), {
  ssr: false,
});

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production' && !QUARTIER_VISIBLE) {
    return { notFound: true };
  }
  return { props: {} };
}

/** The learner's language and level as the last profile load cached them; no language: the phone's. */
function learner(): { native?: Native; level: Level } {
  if (typeof window === 'undefined') return { level: 'a2' };
  let language: string | null = null;
  try {
    language = window.localStorage.getItem(LEARNER_LANGUAGE_STORAGE_KEY);
  } catch {
    // storage refused: the phone's language decides
  }
  const band = levelBand(readLearnerLevel());
  return {
    native: language === 'de' || language === 'en' ? language : undefined,
    level: band === 'A1' || band === 'A2' || band === null ? 'a2' : 'b1',
  };
}

function phoneNative(): Native {
  if (typeof navigator === 'undefined') return 'en';
  return /^de\b/i.test(navigator.language || '') ? 'de' : 'en';
}

const COPY = {
  en: {
    signIn: 'Sign in to play today’s episode here.',
    loadFailed: 'Today’s episode could not be loaded.',
    disabled: 'The daily episode is not open on your account yet. The quarter is yours to walk.',
    nothing: 'No new episode today. The quarter is yours to walk.',
    preparing: 'Your day is being written. It will be here in a moment.',
    handoff: {
      day: 'Today’s episode is read in the Feuilleton.',
      midway: 'You are in the middle of today’s conversation. Finish it in the Feuilleton.',
      unavailable: 'Today’s episode is not ready yet. The Feuilleton can try again.',
    },
    next: (n: number) => (n === 1 ? 'The scene is played. One step of the day is left.' : `The scene is played. ${n} steps of the day are left.`),
    finish: 'The scene is played. The day only needs finishing.',
    done: 'Today’s episode is done.',
  },
  de: {
    signIn: 'Melde dich an, um die heutige Folge hier zu spielen.',
    loadFailed: 'Die heutige Folge konnte nicht geladen werden.',
    disabled: 'Die tägliche Folge ist für dein Konto noch nicht offen. Das Viertel gehört dir.',
    nothing: 'Heute gibt es keine neue Folge. Das Viertel gehört dir.',
    preparing: 'Dein Tag wird geschrieben. Gleich ist er da.',
    handoff: {
      day: 'Die heutige Folge liest du im Feuilleton.',
      midway: 'Du bist mitten im heutigen Gespräch. Führ es im Feuilleton zu Ende.',
      unavailable: 'Die heutige Folge ist noch nicht fertig. Das Feuilleton kann es noch einmal versuchen.',
    },
    next: (n: number) => (n === 1 ? 'Die Szene ist gespielt. Ein Schritt des Tages bleibt.' : `Die Szene ist gespielt. ${n} Schritte des Tages bleiben.`),
    finish: 'Die Szene ist gespielt. Der Tag muss nur noch abgeschlossen werden.',
    done: 'Die heutige Folge ist zu Ende.',
  },
};

type Copy = (typeof COPY)['en'];

/** The later of two reads of the same journey; the first when they are not the same journey. */
function newer(a: JourneySnapshot | null, b: JourneySnapshot | null): JourneySnapshot | null {
  return a && b && a.id === b.id && b.revision > a.revision ? b : a;
}

/** The day once its scene is played: what is left of it, or how it ended and what comes next. */
function DayAfter({
  journey,
  copy,
  busy,
  onGoOn,
  onPick,
}: {
  journey: JourneySnapshot | null;
  copy: Copy;
  busy: boolean;
  onGoOn: () => void;
  onPick: (premiseId: string) => void;
}) {
  if (!journey) return <p className="qz-loading-label">…</p>;
  if (journey.status === 'completed' || journey.status === 'ended_early') {
    const recap = journey.recap;
    const teaser = recap?.teaser?.text_fr ?? recap?.teaser_fr ?? null;
    const tomorrow = recap?.tomorrow ?? null;
    return (
      <>
        {teaser ? (
          <section className="qz-recap">
            <h2>La suite</h2>
            <ul>
              <li lang="fr">{teaser}</li>
            </ul>
          </section>
        ) : null}
        {tomorrow?.options.length ? (
          <section className="qz-recap">
            <h2>Demain</h2>
            <div className="qz-chips" role="group" aria-label="Demain">
              {tomorrow.options.map((o) => (
                <button key={o.premise_id} type="button" className="qz-chip" lang="fr" aria-pressed={tomorrow.picked === o.premise_id} disabled={busy} onClick={() => onPick(o.premise_id)}>
                  {tomorrow.picked === o.premise_id ? '✓ ' : ''}
                  {o.label_fr}
                </button>
              ))}
            </div>
          </section>
        ) : null}
      </>
    );
  }
  const left = remainingSteps(journey).length;
  return (
    <>
      <p className="qz-cando">{left ? copy.next(left) : copy.finish}</p>
      <button type="button" className="qz-primary" onClick={onGoOn}>
        Continuer
      </button>
    </>
  );
}

/** The card the quarter shows instead of the episode, when today is not one to play here. */
function noteOf(
  today: Today,
  c: DailyJourneyController,
  copy: Copy,
  feuilleton: () => void,
  after: React.ReactNode,
): DayNote | null {
  const phase = c.phase;
  if (phase.kind === 'loading') return null;
  if (phase.kind === 'load_failed') return { title: 'Hors ligne', text: copy.loadFailed, action: { label: 'Réessayer', run: () => void c.actions.refresh() } };
  if (phase.kind === 'disabled') return { kicker: 'Le Quartier', title: 'Bonsoir', text: copy.disabled };
  if (phase.kind === 'offer') {
    const s = phase.scenario;
    if (!s) return { title: 'Aujourd’hui', text: copy.nothing };
    return {
      kicker: c.envelope?.headline?.edition_no ? `Épisode ${c.envelope.headline.edition_no}` : undefined,
      title: s.title_fr,
      text: s.objective_native,
      action: { label: c.busy ? '…' : 'Ouvrir', run: () => !c.busy && void c.actions.start() },
    };
  }
  switch (today.kind) {
    case 'play':
      return null;
    case 'start':
    case 'preparing':
      // the controller looks again for a while; after that, or when a look failed, the learner asks
      return {
        title: 'Ta journée s’écrit',
        text: copy.preparing,
        action: {
          label: c.busy ? '…' : 'Vérifier à nouveau',
          run: () => !c.busy && void (phase.kind === 'preparing' && phase.retryAllowed ? c.actions.retryGeneration() : c.actions.refresh()),
        },
      };
    case 'handoff':
      return { title: 'Le Feuilleton', text: copy.handoff[today.why], action: { label: 'Ouvrir le Feuilleton', run: feuilleton } };
    case 'practice':
      return { title: 'La suite de ta journée', body: after };
    case 'done':
      return { title: 'À demain', text: copy.done, body: after };
    default:
      return null;
  }
}

export default function QuartierPage() {
  const router = useRouter();
  const [who] = React.useState(learner);
  const copy = COPY[who.native ?? phoneNative()];
  const { status } = useAppSession();
  const signedIn = status === 'authenticated';
  const controller = useDailyJourney({ enabled: signedIn, preferredInputMode: readAnswerMode('voice') });
  // the journey as the scene's own calls left it: the controller reads it again only on a refresh
  const [kept, setKept] = React.useState<JourneySnapshot | null>(null);
  const journey = newer(controller.journey, kept);
  const today = todayOf(journey);
  const [story, setStory] = React.useState<JourneyStory | null>(null);
  const [practice, setPractice] = React.useState(false);
  // between the hook and the journey as the engine left it
  const [settling, setSettling] = React.useState(false);

  const leave = React.useCallback(() => {
    if (window.history.length > 1) router.back();
    else void router.push('/');
  }, [router]);
  const feuilleton = React.useCallback(() => void router.push(JOURNEY_RESUME_HREF), [router]);

  // today's story, once its page is one the quarter stages: one per journey. Its scene plays here
  // while the day stands before it, and the people talk through it whatever the day's state
  const journeyRef = React.useRef(journey);
  journeyRef.current = journey;
  const staged = stagedPageOf(journey) !== null;
  React.useEffect(() => {
    const j = journeyRef.current;
    const page = stagedPageOf(j);
    if (!j || !page) return;
    setStory((now) =>
      now && now.snapshot.id === j.id
        ? now
        : new JourneyStory(j, page, {
            onSnapshot: setKept,
            // the journey moved on without the scene (another device, a question it is past): the Feuilleton has where it stands
            onLost: () => void router.replace(JOURNEY_RESUME_HREF),
          }),
    );
  }, [staged, journey?.id, router]);

  const refresh = controller.actions.refresh;
  const onPlayed = React.useCallback(() => {
    setSettling(true);
    void refresh().finally(() => setSettling(false));
  }, [refresh]);

  const after = (
    <DayAfter
      journey={settling ? null : journey}
      copy={copy}
      busy={controller.busy}
      onGoOn={() => setPractice(true)}
      onPick={(id) => void controller.actions.pickTomorrow(id)}
    />
  );

  let day: QuartierDay;
  if (!signedIn) {
    day =
      status === 'loading'
        ? { story: null }
        : { story: null, note: { title: 'Bonsoir', text: copy.signIn, action: { label: 'Se connecter', run: () => void router.push(`/auth/signin?callbackUrl=${encodeURIComponent('/quartier')}`) } } };
  } else {
    day = {
      story,
      note: today.kind === 'play' && story ? null : noteOf(today, controller, copy, feuilleton, after),
      end: after,
      onPlayed,
    };
  }

  return (
    <>
      <Head>
        <title>Le Quartier</title>
      </Head>
      <QuartierScreen day={day} native={who.native} level={who.level} onExit={leave} hidden={practice} />
      {practice && journey ? (
        <div style={{ position: 'fixed', inset: 0, zIndex: 40, overflowY: 'auto', WebkitOverflowScrolling: 'touch', background: '#f4efe4' }}>
          <JourneySession
            controller={controller}
            onExit={() => {
              setPractice(false);
              void refresh();
            }}
            onPractice={(href) => void router.push(href)}
            onForge={(href) => void router.push(href)}
          />
        </div>
      ) : null}
    </>
  );
}
